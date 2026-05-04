"""Run.create 멱등 옵션과 partial.jsonl 통합 테스트."""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

from korean_social_simulation.run import Run
from korean_social_simulation.scenario import Scenario


def _make_inputs(tmp_path: Path):
    scenario = Scenario(title="t", stimulus="s")
    reactions = pd.DataFrame([{"sex": "female", "stance": "positive"}])
    sample = pd.DataFrame([{"sex": "female", "age": 28}])
    return tmp_path, scenario, reactions, sample


def test_create_with_run_id_then_allow_existing_returns_same(tmp_path: Path) -> None:
    root, scenario, reactions, sample = _make_inputs(tmp_path)
    run1 = Run.create(
        root=root,
        scenario=scenario,
        reactions=reactions,
        sample=sample,
        meta={"model": "x"},
        run_id="fixed-id",
    )
    run2 = Run.create(
        root=root,
        scenario=scenario,
        reactions=reactions,
        sample=sample,
        meta={"model": "x"},
        run_id="fixed-id",
        allow_existing=True,
    )
    assert run1.path == run2.path


def test_create_existing_without_flag_still_raises(tmp_path: Path) -> None:
    root, scenario, reactions, sample = _make_inputs(tmp_path)
    Run.create(
        root=root,
        scenario=scenario,
        reactions=reactions,
        sample=sample,
        meta={"model": "x"},
        run_id="fixed-id",
    )
    with pytest.raises(FileExistsError):
        Run.create(
            root=root,
            scenario=scenario,
            reactions=reactions,
            sample=sample,
            meta={"model": "x"},
            run_id="fixed-id",
        )


def test_create_pending_makes_dir_and_partial(tmp_path: Path) -> None:
    scenario = Scenario(title="t", stimulus="s")
    path = Run.create_pending(
        root=tmp_path,
        scenario=scenario,
        meta={"model": "x", "n": 5},
        run_id="pending-id",
    )
    assert path.exists()
    assert (path / "scenario.json").exists()
    assert (path / "reactions.partial.jsonl").exists()
    assert (path / "reactions.partial.jsonl").read_text() == ""


def test_create_pending_writes_status_running(tmp_path: Path) -> None:
    scenario = Scenario(title="t", stimulus="s")
    path = Run.create_pending(
        root=tmp_path,
        scenario=scenario,
        meta={"model": "x", "n": 5},
        run_id="pending-id-2",
    )
    import json as _json

    data = _json.loads((path / "scenario.json").read_text())
    assert data["status"] == "running"
    assert data["meta"]["n"] == 5


def test_append_partial_then_finalize(tmp_path: Path) -> None:
    scenario = Scenario(title="t", stimulus="s")
    path = Run.create_pending(
        root=tmp_path,
        scenario=scenario,
        meta={"model": "x", "n": 2},
        run_id="rid",
    )
    Run.append_partial(path, {"sex": "female", "stance": "positive", "intensity": 4})
    Run.append_partial(path, {"sex": "male", "stance": "negative", "intensity": 2})
    sample = pd.DataFrame([{"sex": "female", "age": 28}, {"sex": "male", "age": 45}])
    run = Run.finalize_pending(path, sample=sample)
    assert not (path / "reactions.partial.jsonl").exists()
    assert (path / "reactions.parquet").exists()
    assert len(run.df) == 2
    assert run.df["stance"].tolist() == ["positive", "negative"]


def test_finalize_marks_status_completed(tmp_path: Path) -> None:
    scenario = Scenario(title="t", stimulus="s")
    path = Run.create_pending(
        root=tmp_path,
        scenario=scenario,
        meta={"model": "x", "n": 1},
        run_id="rid2",
    )
    Run.append_partial(path, {"sex": "female", "stance": "positive"})
    sample = pd.DataFrame([{"sex": "female", "age": 28}])
    Run.finalize_pending(path, sample=sample)
    import json as _json

    data = _json.loads((path / "scenario.json").read_text())
    assert data["status"] == "completed"
