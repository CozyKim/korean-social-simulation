"""헬스체크 — vLLM 가용성 + active_jobs."""

from __future__ import annotations

import respx
from fastapi.testclient import TestClient
from httpx import Response


def test_health_no_vllm_configured(client: TestClient) -> None:
    r = client.get("/api/health")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "ok"
    assert body["vllm"] in {"down", "unknown"}
    assert body["active_jobs"] == 0


@respx.mock
def test_health_vllm_up(monkeypatch, settings_env) -> None:
    monkeypatch.setenv("VLLM_BASE_URL", "https://vllm.example.com/v1")
    respx.get("https://vllm.example.com/v1/models").mock(return_value=Response(200, json={"data": []}))
    from korean_social_simulation.api.main import create_app
    from korean_social_simulation.api.ratelimit import get_limiter

    # 모듈 레벨 vllm 캐시 초기화 (다른 테스트의 잔재 방지)
    from korean_social_simulation.api.routes import health as health_routes

    health_routes._vllm_state["status"] = "unknown"
    health_routes._vllm_state["ts"] = 0.0
    get_limiter().reset()
    with TestClient(create_app()) as c:
        r = c.get("/api/health")
        assert r.json()["vllm"] == "up"
