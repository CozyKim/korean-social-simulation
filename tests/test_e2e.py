"""end-to-end 시뮬: tiny 모집단 + fake LLM → run 디렉터리 검증."""

import contextlib
import json
from unittest.mock import patch
from unittest.mock import patch as _patch

import pandas as pd
import pytest
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import AIMessage
from langchain_core.outputs import ChatGeneration, ChatResult

from korean_social_simulation.scenario import Scenario


class _FakeChatStructured(BaseChatModel):
    """structured + text 둘 다 지원하는 fake."""

    extra_canned: dict = {}

    @property
    def _llm_type(self) -> str:
        return "fake-e2e"

    def _generate(self, messages, stop=None, run_manager=None, **kwargs):
        return ChatResult(generations=[ChatGeneration(message=AIMessage(content="요약"))])

    async def _agenerate(self, messages, stop=None, run_manager=None, **kwargs):
        return self._generate(messages, stop, run_manager, **kwargs)

    def with_structured_output(self, schema, **kwargs):  # type: ignore[override]
        canned = {
            "stance": "positive",
            "intensity": 4,
            "action_intent": "purchase",
            "key_drivers": ["맛"],
            "concerns": [],
            "quote": "사 먹어볼게요",
        }
        for name, (typ, _desc) in self.extra_canned.items():
            canned[name] = typ() if callable(typ) else 0

        class _Bound:
            async def ainvoke(self, _messages):
                return schema(**canned)

        return _Bound()


def _tiny_population(n: int = 1000) -> pd.DataFrame:
    rows = []
    for i in range(n):
        rows.append(
            {
                "uuid": f"u{i}",
                "sex": "남" if i % 2 == 0 else "여",
                "age": 20 + (i % 60),
                "province": ["서울특별시", "경기도", "부산광역시"][i % 3],
                "district": "테스트구",
                "occupation": "직장인",
                "education_level": "학사",
                "bachelors_field": "x",
                "marital_status": "x",
                "military_status": "x",
                "family_type": "x",
                "housing_type": "x",
                "country": "한국",
                "persona": f"p{i}",
                "professional_persona": "x",
                "sports_persona": "x",
                "arts_persona": "x",
                "travel_persona": "x",
                "culinary_persona": "x",
                "family_persona": "x",
                "cultural_background": "x",
                "skills_and_expertise": "x",
                "skills_and_expertise_list": "[]",
                "hobbies_and_interests": "x",
                "hobbies_and_interests_list": "[]",
                "career_goals_and_ambitions": "x",
            }
        )
    return pd.DataFrame(rows)


class _FakeDataset:
    """``to_pandas()`` 만 흉내내는 가짜 ``datasets.Dataset``."""

    def __init__(self, df: pd.DataFrame):
        self._df = df
        self._fingerprint = "fp_test"

    def to_pandas(self) -> pd.DataFrame:
        return self._df


@contextlib.contextmanager
def _patch_llm_and_data(monkeypatch, *, n: int = 500):
    """test_e2e의 LLM/데이터셋 mock + KSS_CACHE_DIR 격리를 한 번에 적용한다.

    pytest-asyncio 컨텍스트에서도 사용 가능하도록 contextmanager로 export.
    Args:
        n: tiny 모집단 크기 (기본 500). 호출자의 `n`(샘플 수)보다 충분히 크게 줘야
            stratified 샘플링이 성공한다.
    """
    import tempfile

    tmp_cache = tempfile.mkdtemp(prefix="kss-test-cache-")
    monkeypatch.setenv("KSS_CACHE_DIR", tmp_cache)
    fake_pop = _tiny_population(n)
    with (
        _patch(
            "korean_social_simulation.simulate.load_personas",
            return_value=(_FakeDataset(fake_pop), "fp_test"),
        ),
        _patch(
            "korean_social_simulation.simulate.get_llm",
            return_value=_FakeChatStructured(),
        ),
    ):
        yield


def test_e2e_simulation_creates_run_and_report(tmp_path, monkeypatch):
    monkeypatch.setenv("KSS_CACHE_DIR", str(tmp_path / "cache"))

    fake_pop = _tiny_population(500)
    with (
        patch(
            "korean_social_simulation.simulate.load_personas",
            return_value=(_FakeDataset(fake_pop), "fp_test"),
        ),
        patch(
            "korean_social_simulation.simulate.get_llm",
            return_value=_FakeChatStructured(),
        ),
    ):
        from korean_social_simulation.simulate import simulate

        run = simulate(
            scenario=Scenario(title="e2e", stimulus="x"),
            n=30,
            model="vllm-qwen",
            seed=1,
            runs_root=tmp_path / "runs",
            min_cell_threshold=0,
        )

    assert (run.path / "reactions.parquet").exists()
    assert (run.path / "scenario.json").exists()
    md = run.report(insights_model=None)
    assert md.exists()
    assert "e2e" in md.read_text(encoding="utf-8")


async def test_asimulate_runs_inside_running_event_loop(tmp_path, monkeypatch):
    """이미 실행 중인 이벤트 루프에서도 ``asimulate`` 는 동작한다."""
    monkeypatch.setenv("KSS_CACHE_DIR", str(tmp_path / "cache"))

    fake_pop = _tiny_population(500)
    with (
        patch(
            "korean_social_simulation.simulate.load_personas",
            return_value=(_FakeDataset(fake_pop), "fp_test"),
        ),
        patch(
            "korean_social_simulation.simulate.get_llm",
            return_value=_FakeChatStructured(),
        ),
    ):
        from korean_social_simulation.simulate import asimulate

        run = await asimulate(
            scenario=Scenario(title="async-e2e", stimulus="x"),
            n=10,
            model="vllm-qwen",
            seed=1,
            runs_root=tmp_path / "runs",
            min_cell_threshold=0,
        )

    md = await run.areport(insights_model=None)
    assert md.exists()
    assert "async-e2e" in md.read_text(encoding="utf-8")


async def test_simulate_in_running_loop_raises(tmp_path, monkeypatch):
    """동기 ``simulate()`` 는 이벤트 루프 안에서 호출되면 명확히 실패한다."""
    monkeypatch.setenv("KSS_CACHE_DIR", str(tmp_path / "cache"))

    from korean_social_simulation.simulate import simulate

    with pytest.raises(RuntimeError, match="asimulate"):
        simulate(
            scenario=Scenario(title="x", stimulus="x"),
            n=1,
            runs_root=tmp_path / "runs",
        )


def test_extra_fields_full_definition_is_persisted(tmp_path, monkeypatch):
    """``extra_fields`` 정의(이름·타입·설명)가 ``scenario.json`` 에 보존된다."""
    monkeypatch.setenv("KSS_CACHE_DIR", str(tmp_path / "cache"))

    fake_pop = _tiny_population(300)
    extra = {
        "purchase_likelihood": (int, "0~100, 구매 가능성"),
        "price_sensitivity": (int, "0~100, 가격 민감도"),
    }
    with (
        patch(
            "korean_social_simulation.simulate.load_personas",
            return_value=(_FakeDataset(fake_pop), "fp_test"),
        ),
        patch(
            "korean_social_simulation.simulate.get_llm",
            return_value=_FakeChatStructured(extra_canned=extra),
        ),
    ):
        from korean_social_simulation.simulate import simulate

        run = simulate(
            scenario=Scenario(title="extras", stimulus="x"),
            n=5,
            model="vllm-qwen",
            seed=1,
            runs_root=tmp_path / "runs",
            min_cell_threshold=0,
            extra_fields=extra,
        )

    data = json.loads((run.path / "scenario.json").read_text(encoding="utf-8"))
    persisted = data["meta"]["extra_fields"]
    assert persisted == {
        "purchase_likelihood": {"type": "int", "description": "0~100, 구매 가능성"},
        "price_sensitivity": {"type": "int", "description": "0~100, 가격 민감도"},
    }
