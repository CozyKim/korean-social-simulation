"""게스트 mini-run — vLLM 전용, n≤20 422, IP 1회/일, 전역 동시 2개."""

from __future__ import annotations

import respx
from fastapi.testclient import TestClient
from httpx import Response


def test_try_blocked_when_vllm_down(settings_env, client: TestClient) -> None:
    # vLLM URL이 설정 안 됨 → 503
    r = client.post("/api/try", json={"scenario_title": "t", "scenario_stimulus": "s", "n": 5})
    assert r.status_code == 503


@respx.mock
def test_try_n_over_20_422(monkeypatch, settings_env) -> None:
    monkeypatch.setenv("VLLM_BASE_URL", "https://vllm.example.com/v1")
    respx.get("https://vllm.example.com/v1/models").mock(return_value=Response(200, json={"data": []}))
    from korean_social_simulation.api.main import create_app
    from korean_social_simulation.api.ratelimit import get_limiter
    from korean_social_simulation.api.routes import health as health_routes

    health_routes._vllm_state["status"] = "unknown"
    health_routes._vllm_state["ts"] = 0.0
    get_limiter().reset()

    with TestClient(create_app()) as c:
        r = c.post("/api/try", json={"scenario_title": "t", "scenario_stimulus": "s", "n": 21})
        assert r.status_code == 422


@respx.mock
def test_try_rate_limit_per_ip(monkeypatch, settings_env) -> None:
    monkeypatch.setenv("VLLM_BASE_URL", "https://vllm.example.com/v1")
    respx.get("https://vllm.example.com/v1/models").mock(return_value=Response(200, json={"data": []}))
    from korean_social_simulation.api.main import create_app
    from korean_social_simulation.api.ratelimit import get_limiter
    from korean_social_simulation.api.routes import health as health_routes
    from tests.test_e2e import _patch_llm_and_data

    health_routes._vllm_state["status"] = "unknown"
    health_routes._vllm_state["ts"] = 0.0
    get_limiter().reset()

    with _patch_llm_and_data(monkeypatch, n=500):
        with TestClient(create_app()) as c:
            r1 = c.post("/api/try", json={"scenario_title": "t", "scenario_stimulus": "s", "n": 2})
            assert r1.status_code == 202
            r2 = c.post("/api/try", json={"scenario_title": "t", "scenario_stimulus": "s", "n": 2})
            assert r2.status_code == 429
