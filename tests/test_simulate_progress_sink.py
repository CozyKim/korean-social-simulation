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
