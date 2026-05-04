"""Runs 목록·상세 — public 가시성 + 권한 게이트."""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
from fastapi.testclient import TestClient

from korean_social_simulation.run import Run
from korean_social_simulation.scenario import Scenario


def _login(client: TestClient) -> None:
    client.post("/api/auth/login", json={"token": "test-secret-token"})


def _make_run(runs_root: Path, run_id: str, *, public: bool = False) -> Path:
    scenario = Scenario(title=f"t-{run_id}", stimulus="s")
    Run.create(
        root=runs_root,
        scenario=scenario,
        reactions=pd.DataFrame([{"sex": "female", "stance": "positive"}]),
        sample=pd.DataFrame([{"sex": "female", "age": 28}]),
        meta={"model": "vllm-qwen", "n": 1},
        run_id=run_id,
    )
    meta_path = runs_root / run_id / "scenario.json"
    data = json.loads(meta_path.read_text())
    data["public"] = public
    data["status"] = "completed"
    meta_path.write_text(json.dumps(data, ensure_ascii=False, indent=2))
    return runs_root / run_id


def test_list_runs_anonymous_only_public(settings_env: Path, client: TestClient) -> None:
    runs_root = settings_env / "runs"
    _make_run(runs_root, "pub", public=True)
    _make_run(runs_root, "priv", public=False)
    r = client.get("/api/runs")
    assert r.status_code == 200
    ids = [item["run_id"] for item in r.json()]
    assert "pub" in ids
    assert "priv" not in ids


def test_list_runs_owner_sees_private(settings_env: Path, client: TestClient) -> None:
    runs_root = settings_env / "runs"
    _make_run(runs_root, "pub", public=True)
    _make_run(runs_root, "priv", public=False)
    _login(client)
    r = client.get("/api/runs")
    ids = [item["run_id"] for item in r.json()]
    assert {"pub", "priv"} <= set(ids)


def test_get_private_run_anonymous_404(settings_env: Path, client: TestClient) -> None:
    runs_root = settings_env / "runs"
    _make_run(runs_root, "priv", public=False)
    r = client.get("/api/runs/priv")
    assert r.status_code == 404


def test_get_public_run_returns_meta(settings_env: Path, client: TestClient) -> None:
    runs_root = settings_env / "runs"
    _make_run(runs_root, "pub", public=True)
    r = client.get("/api/runs/pub")
    assert r.status_code == 200
    assert r.json()["title"] == "t-pub"


def test_delete_run(settings_env: Path, client: TestClient) -> None:
    _make_run(settings_env / "runs", "rid")
    _login(client)
    r = client.delete("/api/runs/rid")
    assert r.status_code == 204
    assert not (settings_env / "runs" / "rid").exists()


def test_get_reactions_private_run_anonymous_404(settings_env: Path, client: TestClient) -> None:
    _make_run(settings_env / "runs", "priv", public=False)
    r = client.get("/api/runs/priv/reactions")
    assert r.status_code == 404


def test_get_reactions_public_streams_parquet(settings_env: Path, client: TestClient) -> None:
    _make_run(settings_env / "runs", "pub", public=True)
    r = client.get("/api/runs/pub/reactions")
    assert r.status_code == 200
    assert r.headers["content-type"] == "application/vnd.apache.parquet"
    assert len(r.content) > 0
