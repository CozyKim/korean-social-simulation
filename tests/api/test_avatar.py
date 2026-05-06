"""avatar_key 매핑 — 한국어 sex 라벨을 프론트엔드 자산 키로 변환."""

from __future__ import annotations

import json

from fastapi.testclient import TestClient


def _login(client: TestClient) -> None:
    client.post("/api/auth/login", json={"token": "test-secret-token"})


def test_avatar_key_maps_korean_sex_to_canonical() -> None:
    """`남`/`여` → `male`/`female` canonical 매핑."""
    from korean_social_simulation.api.avatar import avatar_key_from_row

    assert avatar_key_from_row({"sex": "남", "age": 28, "province": "서울특별시"}) == "male_20s_서울특별시"
    assert avatar_key_from_row({"sex": "여", "age": 35, "province": "경기도"}) == "female_30s_경기도"


def test_avatar_key_unknown_sex_returns_none() -> None:
    """알 수 없는 sex 값(빈 문자열, 'X' 등) 은 안전하게 None."""
    from korean_social_simulation.api.avatar import avatar_key_from_row

    assert avatar_key_from_row({"sex": "X", "age": 28, "province": "서울특별시"}) is None
    assert avatar_key_from_row({"sex": "", "age": 28, "province": "서울특별시"}) is None
    # missing 필드도 None.
    assert avatar_key_from_row({"sex": "남", "age": None, "province": "서울특별시"}) is None
    assert avatar_key_from_row({"sex": "남", "age": 28, "province": None}) is None


def test_sse_persona_event_includes_avatar_key(monkeypatch, client: TestClient) -> None:
    """progress_sink emission 에 ``avatar_key`` 가 canonical 형식으로 포함된다."""
    from tests.test_e2e import _patch_llm_and_data

    with _patch_llm_and_data(monkeypatch, n=500):
        _login(client)
        r = client.post(
            "/api/runs",
            json={"scenario_title": "t", "scenario_stimulus": "s", "n": 2, "model": "vllm-qwen"},
        )
        run_id = r.json()["run_id"]

        events: list[dict] = []
        with client.stream("GET", f"/api/runs/{run_id}/events") as stream:
            for line in stream.iter_lines():
                if line.startswith("data:"):
                    payload = json.loads(line.removeprefix("data:").strip())
                    events.append(payload)
                    if payload.get("type") in {"completed", "error"}:
                        break

    persona_events = [e for e in events if e.get("type") == "persona_done"]
    assert len(persona_events) == 2
    for e in persona_events:
        assert "avatar_key" in e
        # tiny 모집단의 sex 는 `남`/`여` — canonical 키는 male_/female_ 로 시작해야 한다.
        assert e["avatar_key"] is not None
        assert e["avatar_key"].split("_", 1)[0] in {"male", "female"}


def test_try_run_event_includes_avatar_key(monkeypatch, settings_env) -> None:
    """``/api/try`` 의 ephemeral guest run 이벤트에도 ``avatar_key`` 포함."""
    import respx
    from httpx import Response

    monkeypatch.setenv("VLLM_BASE_URL", "https://vllm.example.com/v1")
    from korean_social_simulation.api.main import create_app
    from korean_social_simulation.api.ratelimit import get_limiter
    from korean_social_simulation.api.routes import health as health_routes
    from tests.test_e2e import _patch_llm_and_data

    health_routes._vllm_state["status"] = "unknown"
    health_routes._vllm_state["ts"] = 0.0
    get_limiter().reset()

    with respx.mock:
        respx.get("https://vllm.example.com/v1/models").mock(return_value=Response(200, json={"data": []}))
        with _patch_llm_and_data(monkeypatch, n=500):
            with TestClient(create_app()) as c:
                r = c.post("/api/try", json={"scenario_title": "t", "scenario_stimulus": "s", "n": 2})
                assert r.status_code == 202
                run_id = r.json()["run_id"]

                events: list[dict] = []
                with c.stream("GET", f"/api/runs/{run_id}/events") as stream:
                    for line in stream.iter_lines():
                        if line.startswith("data:"):
                            payload = json.loads(line.removeprefix("data:").strip())
                            events.append(payload)
                            if payload.get("type") in {"completed", "error"}:
                                break

    persona_events = [e for e in events if e.get("type") == "persona_done"]
    assert len(persona_events) == 2
    for e in persona_events:
        assert "avatar_key" in e
        assert e["avatar_key"] is not None
        assert e["avatar_key"].split("_", 1)[0] in {"male", "female"}
