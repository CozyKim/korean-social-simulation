"""Run 데이터클래스 — 산출물 디렉터리 IO."""

import pandas as pd

from korean_social_simulation.run import Run
from korean_social_simulation.scenario import Scenario


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
