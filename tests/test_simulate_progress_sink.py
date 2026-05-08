"""asimulate 의 run_id / progress_sink 옵션 통합 테스트."""

from __future__ import annotations

from pathlib import Path

from korean_social_simulation import asimulate
from korean_social_simulation.scenario import Scenario


async def test_progress_sink_called_per_persona(monkeypatch, tmp_path: Path) -> None:
    """페르소나별로 progress_sink가 await되어 호출된다."""
    from tests.test_e2e import _patch_llm_and_data

    received: list[dict] = []

    async def sink(row: dict) -> None:
        received.append(row)

    with _patch_llm_and_data(monkeypatch, n=500):
        run = await asimulate(
            scenario=Scenario(title="t", stimulus="s"),
            n=3,
            model="vllm-qwen",
            seed=1,
            runs_root=tmp_path,
            min_cell_threshold=0,
            progress_sink=sink,
        )
    assert len(received) == 3
    assert all("stance" in r for r in received)
    assert run.path.exists()


async def test_explicit_run_id_creates_pending_dir_first(monkeypatch, tmp_path: Path) -> None:
    """run_id가 주어지면 디렉터리가 시뮬 시작 시점에 만들어진다."""
    from tests.test_e2e import _patch_llm_and_data

    fixed_id = "test-run-id"
    seen_during: list[bool] = []

    async def sink(row: dict) -> None:
        seen_during.append((tmp_path / fixed_id).exists())

    with _patch_llm_and_data(monkeypatch, n=500):
        await asimulate(
            scenario=Scenario(title="t", stimulus="s"),
            n=2,
            model="vllm-qwen",
            seed=1,
            runs_root=tmp_path,
            min_cell_threshold=0,
            run_id=fixed_id,
            progress_sink=sink,
        )
    assert all(seen_during)
    assert (tmp_path / fixed_id / "reactions.parquet").exists()
    assert not (tmp_path / fixed_id / "reactions.partial.jsonl").exists()


async def test_all_failed_still_finalizes_reactions_parquet(monkeypatch, tmp_path: Path) -> None:
    """100% LLM fail 시도 reactions.parquet 이 생성되고 status=failed.

    UI 가 페이지 새로고침 시 disk replay 분기로 fail row 들을 보여줄 수 있어야 한다.
    """
    import json
    from unittest.mock import patch as _patch

    import pandas as pd
    import pytest
    from langchain_core.language_models.fake_chat_models import FakeMessagesListChatModel

    from tests.test_e2e import _FakeDataset, _tiny_population

    class _AlwaysFailLLM(FakeMessagesListChatModel):
        responses: list = [None]

        @property
        def _llm_type(self) -> str:
            return "fake-fail"

        def with_structured_output(self, schema, **kwargs):  # type: ignore[override]
            class _Bound:
                async def ainvoke(self, _messages):
                    raise RuntimeError("LLM 호출 fail")

            return _Bound()

    fixed_id = "all-failed-rid"
    monkeypatch.setenv("KSS_CACHE_DIR", str(tmp_path / "cache"))
    fake_pop = _tiny_population(500)
    with (
        _patch(
            "korean_social_simulation.simulate.load_personas",
            return_value=(_FakeDataset(fake_pop), "fp_test"),
        ),
        _patch(
            "korean_social_simulation.simulate.get_llm",
            return_value=_AlwaysFailLLM(),
        ),
        pytest.raises(RuntimeError, match="All .* simulations failed"),
    ):
        await asimulate(
            scenario=Scenario(title="t", stimulus="s"),
            n=3,
            model="vllm-qwen",
            seed=1,
            runs_root=tmp_path,
            min_cell_threshold=0,
            run_id=fixed_id,
        )

    run_dir = tmp_path / fixed_id
    # reactions.parquet 가 생성됨 (모든 row 의 stance/quote 는 None, error 만 채워짐).
    assert (run_dir / "reactions.parquet").exists()
    df = pd.read_parquet(run_dir / "reactions.parquet")
    assert len(df) == 3
    assert df["error"].notna().all()
    # partial.jsonl 은 finalize 후 정리됨.
    assert not (run_dir / "reactions.partial.jsonl").exists()
    # status=failed (mark_failed 가 finalize 의 status=completed 를 덮어씀).
    meta = json.loads((run_dir / "scenario.json").read_text(encoding="utf-8"))
    assert meta["status"] == "failed"
    assert "all_failed" in meta["error"]


async def test_explicit_run_id_preserves_model_column(monkeypatch, tmp_path: Path) -> None:
    """pending run 경로에서도 reactions.parquet에 ``model`` 컬럼이 보존된다.

    POST /api/runs (FastAPI job manager) 경로 회귀 방지: simulate.py가 추가한
    ``df["model"] = model`` 가 ``Run.finalize_pending`` 후에도 유지되어야 한다.
    """
    import pandas as pd

    from tests.test_e2e import _patch_llm_and_data

    fixed_id = "model-col-rid"
    with _patch_llm_and_data(monkeypatch, n=500):
        run = await asimulate(
            scenario=Scenario(title="t", stimulus="s"),
            n=3,
            model="vllm-qwen",
            seed=1,
            runs_root=tmp_path,
            min_cell_threshold=0,
            run_id=fixed_id,
        )
    df = pd.read_parquet(run.path / "reactions.parquet")
    assert "model" in df.columns
    assert (df["model"] == "vllm-qwen").all()
