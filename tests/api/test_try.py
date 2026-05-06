"""게스트 mini-run — vLLM 전용, n≤20 422, IP 1회/일, 전역 동시 2개."""

from __future__ import annotations

import json
import time

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


@respx.mock
def test_try_stream_accessible_to_anonymous(monkeypatch, settings_env) -> None:
    """게스트 mini-run 으로 만들어진 ephemeral job 은 익명 SSE 구독으로 접근 가능."""
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
            r = c.post("/api/try", json={"scenario_title": "t", "scenario_stimulus": "s", "n": 2})
            assert r.status_code == 202
            run_id = r.json()["run_id"]
            assert run_id

            # scenario.json 이 디스크에 없어도 익명 SSE 가 200 으로 열려야 한다.
            events: list[dict] = []
            with c.stream("GET", f"/api/runs/{run_id}/events") as stream:
                assert stream.status_code == 200
                for line in stream.iter_lines():
                    if line.startswith("data:"):
                        payload = json.loads(line.removeprefix("data:").strip())
                        events.append(payload)
                        if payload.get("type") in {"completed", "error"}:
                            break

    types = [e.get("type") for e in events]
    assert "started" in types
    assert any(t == "completed" for t in types)


@respx.mock
def test_try_revalidates_stale_vllm_cache(monkeypatch, settings_env) -> None:
    """캐시된 ``status="up"`` 가 TTL 을 넘긴 경우 재검증해야 한다.

    vLLM 이 다운된 상태인데 stale 캐시 때문에 ``/api/try`` 가 202 로 통과되면
    게스트는 quota 만 차감되고 background job 이 실패한다. 재검증으로 503 을
    내리고 quota 도 보존돼야 한다.
    """
    monkeypatch.setenv("VLLM_BASE_URL", "https://vllm.example.com/v1")
    # 실제 호출은 503 (다운 상태) — 재검증되면 down 으로 갱신돼야 함.
    respx.get("https://vllm.example.com/v1/models").mock(return_value=Response(503))
    from korean_social_simulation.api.main import create_app
    from korean_social_simulation.api.ratelimit import get_limiter
    from korean_social_simulation.api.routes import health as health_routes

    # stale "up" 캐시 주입: ts 를 TTL 보다 훨씬 과거로.
    health_routes._vllm_state["status"] = "up"
    health_routes._vllm_state["ts"] = time.monotonic() - (health_routes._VLLM_CACHE_TTL_S + 10)
    get_limiter().reset()

    with TestClient(create_app()) as c:
        r = c.post("/api/try", json={"scenario_title": "t", "scenario_stimulus": "s", "n": 2})
        # stale cache 무시하고 재검증 → vLLM 다운 → 503
        assert r.status_code == 503

    # quota 가 차감되지 않았는지 확인: 캐시를 fresh up 으로 다시 주입하고 재호출 → 정상 처리.
    respx.get("https://vllm.example.com/v1/models").mock(return_value=Response(200, json={"data": []}))
    health_routes._vllm_state["status"] = "up"
    health_routes._vllm_state["ts"] = time.monotonic()
    from tests.test_e2e import _patch_llm_and_data

    with _patch_llm_and_data(monkeypatch, n=500):
        with TestClient(create_app()) as c:
            r = c.post("/api/try", json={"scenario_title": "t", "scenario_stimulus": "s", "n": 2})
            # quota 가 보존됐다면 첫 호출로 처리 → 202
            assert r.status_code == 202


@respx.mock
def test_try_capacity_check_before_quota_charge(monkeypatch, settings_env) -> None:
    """전역 동시 한도 초과로 503 이 날 때는 IP quota 가 차감되지 않아야 한다.

    saturation 시각에 처음 들어온 게스트가 24h lock-out 되는 것을 방지.
    """
    monkeypatch.setenv("VLLM_BASE_URL", "https://vllm.example.com/v1")
    respx.get("https://vllm.example.com/v1/models").mock(return_value=Response(200, json={"data": []}))
    from korean_social_simulation.api.main import create_app
    from korean_social_simulation.api.ratelimit import get_limiter
    from korean_social_simulation.api.routes import health as health_routes
    from korean_social_simulation.api.routes.try_run import GUEST_GLOBAL_CONCURRENT_LIMIT
    from tests.test_e2e import _patch_llm_and_data

    health_routes._vllm_state["status"] = "unknown"
    health_routes._vllm_state["ts"] = 0.0
    get_limiter().reset()

    with _patch_llm_and_data(monkeypatch, n=500):
        with TestClient(create_app()) as c:
            jm = c.app.state.job_manager
            # capacity 를 인위적으로 가득 채운다.
            for i in range(GUEST_GLOBAL_CONCURRENT_LIMIT):
                jm.register(f"saturate-{i}", total=1, public=False)
            assert jm.active_count() >= GUEST_GLOBAL_CONCURRENT_LIMIT

            r1 = c.post("/api/try", json={"scenario_title": "t", "scenario_stimulus": "s", "n": 2})
            # capacity 초과 → 503, quota 미차감
            assert r1.status_code == 503

            # capacity 를 비우고 같은 IP 로 다시 호출 → 정상 처리돼야 한다 (quota 보존 증명).
            for i in range(GUEST_GLOBAL_CONCURRENT_LIMIT):
                jm._jobs.pop(f"saturate-{i}", None)
            assert jm.active_count() == 0

            r2 = c.post("/api/try", json={"scenario_title": "t", "scenario_stimulus": "s", "n": 2})
            assert r2.status_code == 202
