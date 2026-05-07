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


def test_create_pending_allow_existing_idempotent(tmp_path: Path) -> None:
    """``allow_existing=True`` 면 이미 존재하는 디렉터리에 대해 무손실 멱등 동작.

    배경: ``POST /api/runs`` 라우트가 ``Run.create_pending`` 을 동기 호출해
    ``scenario.json`` 을 미리 작성한 뒤 백그라운드 ``asimulate(run_id=...)`` 를 시작.
    asimulate 내부도 ``create_pending`` 을 호출하므로 두 번째 호출이 실패하면 안 됨.
    또한 두 번째 호출이 기존 partial.jsonl 의 누적 행을 덮어써서도 안 됨.
    """
    import json as _json

    scenario = Scenario(title="t", stimulus="s")
    path = Run.create_pending(
        root=tmp_path,
        scenario=scenario,
        meta={"model": "x", "n": 1},
        run_id="rid-idem",
    )
    Run.append_partial(path, {"sex": "female", "stance": "positive"})

    path2 = Run.create_pending(
        root=tmp_path,
        scenario=scenario,
        meta={"model": "x", "n": 1},
        run_id="rid-idem",
        allow_existing=True,
    )
    assert path == path2
    # partial.jsonl 의 누적 데이터가 보존되어야 한다.
    partial_text = (path / "reactions.partial.jsonl").read_text()
    assert "positive" in partial_text
    # scenario.json 도 그대로 남아있어야 한다 (meta status 유지).
    data = _json.loads((path / "scenario.json").read_text())
    assert data["run_id"] == "rid-idem"


def test_create_pending_existing_without_flag_raises(tmp_path: Path) -> None:
    """``allow_existing`` 없이 두 번 호출하면 FileExistsError."""
    scenario = Scenario(title="t", stimulus="s")
    Run.create_pending(
        root=tmp_path,
        scenario=scenario,
        meta={"model": "x"},
        run_id="rid-dup",
    )
    with pytest.raises(FileExistsError):
        Run.create_pending(
            root=tmp_path,
            scenario=scenario,
            meta={"model": "x"},
            run_id="rid-dup",
        )


def test_create_pending_status_override(tmp_path: Path) -> None:
    """``status`` 인자로 초기 상태를 지정할 수 있다 (예: 'starting')."""
    import json as _json

    scenario = Scenario(title="t", stimulus="s")
    path = Run.create_pending(
        root=tmp_path,
        scenario=scenario,
        meta={"model": "x"},
        run_id="rid-status",
        status="starting",
    )
    data = _json.loads((path / "scenario.json").read_text())
    assert data["status"] == "starting"


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
