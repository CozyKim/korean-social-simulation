"""Run 데이터클래스 — 산출물 디렉터리 IO."""

import asyncio

import pandas as pd
import pytest

from korean_social_simulation.run import Run, _new_run_id
from korean_social_simulation.scenario import Scenario


def _minimal_meta() -> dict:
    return {
        "model": "fake",
        "n": 1,
        "seed": 42,
        "dataset_fingerprint": "fp",
        "sampler_version": "1",
    }


def test_run_creates_directory_structure(tmp_path):
    scenario = Scenario(title="신라면", stimulus="...")
    df = pd.DataFrame(
        [
            {
                "uuid": "u1",
                "sex": "남",
                "age": 30,
                "stance": "positive",
                "intensity": 4,
                "action_intent": "purchase",
                "key_drivers": ["맛"],
                "concerns": [],
                "quote": "좋네요",
                "latency_ms": 100,
                "error": None,
            }
        ]
    )
    run = Run.create(
        root=tmp_path,
        scenario=scenario,
        reactions=df,
        sample=df[["uuid", "sex", "age"]],
        meta={
            "model": "fake",
            "n": 1,
            "seed": 42,
            "dataset_fingerprint": "fp",
            "sampler_version": "1",
        },
    )
    assert run.path.exists()
    assert (run.path / "scenario.json").exists()
    assert (run.path / "reactions.parquet").exists()
    assert (run.path / "sample.parquet").exists()

    loaded = pd.read_parquet(run.path / "reactions.parquet")
    assert list(loaded["uuid"]) == ["u1"]


def test_run_load_round_trip(tmp_path):
    scenario = Scenario(title="t", stimulus="x")
    df = pd.DataFrame(
        [
            {
                "uuid": "u1",
                "stance": "neutral",
                "intensity": 3,
                "action_intent": "ignore",
                "key_drivers": ["x"],
                "concerns": [],
                "quote": "q",
                "latency_ms": 1,
                "error": None,
            }
        ]
    )
    run1 = Run.create(
        root=tmp_path,
        scenario=scenario,
        reactions=df,
        sample=df[["uuid"]],
        meta={
            "model": "fake",
            "n": 1,
            "seed": 1,
            "dataset_fingerprint": "fp",
            "sampler_version": "1",
        },
    )
    run2 = Run.load(run1.path)
    assert run2.scenario.title == scenario.title
    assert list(run2.df["uuid"]) == ["u1"]


def test_new_run_id_is_unique_within_same_second():
    """초 단위 충돌 방지 — microseconds + uuid suffix."""
    ids = {_new_run_id("foo") for _ in range(100)}
    assert len(ids) == 100


def test_run_create_refuses_to_overwrite_existing_dir(tmp_path):
    """같은 ``run_id`` 가 이미 있으면 FileExistsError로 보호한다."""
    scenario = Scenario(title="t", stimulus="x")
    df = pd.DataFrame([{"uuid": "u1"}])
    run1 = Run.create(
        root=tmp_path,
        scenario=scenario,
        reactions=df,
        sample=df,
        meta=_minimal_meta(),
        run_id="fixed-id",
    )
    assert run1.path.name == "fixed-id"

    with pytest.raises(FileExistsError, match="already exists"):
        Run.create(
            root=tmp_path,
            scenario=scenario,
            reactions=df,
            sample=df,
            meta=_minimal_meta(),
            run_id="fixed-id",
        )


def test_run_report_in_running_loop_raises(tmp_path):
    """이미 이벤트 루프가 도는 중에 동기 ``report()`` 를 부르면 명확히 실패."""
    scenario = Scenario(title="t", stimulus="x")
    df = pd.DataFrame([{"uuid": "u1"}])
    run = Run.create(
        root=tmp_path,
        scenario=scenario,
        reactions=df,
        sample=df,
        meta=_minimal_meta(),
    )

    async def _call() -> None:
        with pytest.raises(RuntimeError, match="async"):
            run.report(insights_model=None)

    asyncio.run(_call())
