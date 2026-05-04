"""PATCH public 토글 + Vercel revalidate hook 호출 검증."""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
import respx
from fastapi.testclient import TestClient
from httpx import Response

from korean_social_simulation.run import Run
from korean_social_simulation.scenario import Scenario


def _login(client: TestClient) -> None:
    client.post("/api/auth/login", json={"token": "test-secret-token"})


def _make_run(runs_root: Path, run_id: str) -> None:
    Run.create(
        root=runs_root,
        scenario=Scenario(title="t", stimulus="s"),
        reactions=pd.DataFrame([{"sex": "female", "stance": "positive"}]),
        sample=pd.DataFrame([{"sex": "female", "age": 28}]),
        meta={"model": "vllm-qwen", "n": 1},
        run_id=run_id,
    )


def test_patch_requires_login(settings_env: Path, client: TestClient) -> None:
    _make_run(settings_env / "runs", "rid")
    r = client.patch("/api/runs/rid", json={"public": True})
    assert r.status_code == 401


def test_patch_toggles_public(settings_env: Path, client: TestClient) -> None:
    _make_run(settings_env / "runs", "rid")
    _login(client)
    r = client.patch("/api/runs/rid", json={"public": True})
    assert r.status_code == 200
    data = json.loads((settings_env / "runs" / "rid" / "scenario.json").read_text())
    assert data["public"] is True


@respx.mock
def test_patch_calls_revalidate_hook(monkeypatch, settings_env: Path) -> None:
    monkeypatch.setenv("VERCEL_REVALIDATE_HOOK_URL", "https://example.com/hook")
    from korean_social_simulation.api.main import create_app
    from korean_social_simulation.api.ratelimit import get_limiter

    get_limiter().reset()
    hook_route = respx.post("https://example.com/hook").mock(return_value=Response(200))
    app = create_app()

    _make_run(settings_env / "runs", "rid")
    with TestClient(app) as c:
        c.post("/api/auth/login", json={"token": "test-secret-token"})
        r = c.patch("/api/runs/rid", json={"public": True})
        assert r.status_code == 200
    assert hook_route.called
