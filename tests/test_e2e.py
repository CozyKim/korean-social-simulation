"""end-to-end 시뮬: tiny 모집단 + fake LLM → run 디렉터리 검증."""

from unittest.mock import patch

import pandas as pd
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import AIMessage
from langchain_core.outputs import ChatGeneration, ChatResult

from korean_social_simulation.scenario import Scenario


class _FakeChatStructured(BaseChatModel):
    """structured + text 둘 다 지원하는 fake."""

    @property
    def _llm_type(self) -> str:
        return "fake-e2e"

    def _generate(self, messages, stop=None, run_manager=None, **kwargs):
        return ChatResult(
            generations=[ChatGeneration(message=AIMessage(content="요약"))]
        )

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
