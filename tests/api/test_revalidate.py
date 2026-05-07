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


@respx.mock
def test_patch_revalidate_hook_includes_bearer_when_secret_set(monkeypatch, settings_env: Path) -> None:
    """``VERCEL_REVALIDATE_SECRET`` 가 설정되면 hook 호출 시 Bearer 헤더가 첨부돼야 한다."""
    monkeypatch.setenv("VERCEL_REVALIDATE_HOOK_URL", "https://example.com/hook")
    monkeypatch.setenv("VERCEL_REVALIDATE_SECRET", "s3cret-token")
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
    # respx 는 마지막 매칭 요청을 ``calls.last.request`` 로 노출한다.
    sent = hook_route.calls.last.request
    assert sent.headers.get("authorization") == "Bearer s3cret-token"


@respx.mock
def test_patch_revalidate_hook_no_authorization_when_secret_absent(monkeypatch, settings_env: Path) -> None:
    """secret 미설정 시에는 Authorization 헤더가 추가되지 않아야 한다."""
    monkeypatch.setenv("VERCEL_REVALIDATE_HOOK_URL", "https://example.com/hook")
    monkeypatch.delenv("VERCEL_REVALIDATE_SECRET", raising=False)
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
    sent = hook_route.calls.last.request
    assert sent.headers.get("authorization") is None
