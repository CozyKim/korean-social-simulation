"""POST /api/runs 즉시 응답 + 백그라운드 시뮬 진행."""

from __future__ import annotations

from fastapi.testclient import TestClient


def _login(client: TestClient) -> None:
    client.post("/api/auth/login", json={"token": "test-secret-token"})


def test_post_runs_requires_login(client: TestClient) -> None:
    r = client.post(
        "/api/runs",
        json={
            "scenario_title": "t",
            "scenario_stimulus": "s",
            "n": 2,
            "model": "vllm-qwen",
        },
    )
    assert r.status_code == 401


def test_post_runs_returns_run_id_immediately(monkeypatch, client: TestClient) -> None:
    from tests.test_e2e import _patch_llm_and_data

    with _patch_llm_and_data(monkeypatch, n=500):
        _login(client)
        r = client.post(
            "/api/runs",
            json={
                "scenario_title": "t",
                "scenario_stimulus": "s",
                "n": 2,
                "model": "vllm-qwen",
            },
        )
    assert r.status_code == 202
    body = r.json()
    assert "run_id" in body
    assert body["status"] == "starting"


def test_sse_streams_persona_events(monkeypatch, client: TestClient) -> None:
    """POST /api/runs 후 즉시 SSE 구독해 persona_done + completed 이벤트를 수신."""
    import json

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

    types = [e["type"] for e in events if e.get("type")]
    assert types.count("persona_done") == 2
    assert types[-1] == "completed"


def test_completed_event_has_no_report_url_when_report_missing(monkeypatch, client: TestClient) -> None:
    """run.areport() 가 호출되지 않아 report.md 가 없으면 completed 이벤트에
    report_url 이 들어 있어선 안 된다."""
    import json

    from tests.test_e2e import _patch_llm_and_data

    with _patch_llm_and_data(monkeypatch, n=500):
        _login(client)
        r = client.post(
            "/api/runs",
            json={"scenario_title": "t", "scenario_stimulus": "s", "n": 2, "model": "vllm-qwen"},
        )
        run_id = r.json()["run_id"]

        completed: dict | None = None
        with client.stream("GET", f"/api/runs/{run_id}/events") as stream:
            for line in stream.iter_lines():
                if line.startswith("data:"):
                    payload = json.loads(line.removeprefix("data:").strip())
                    if payload.get("type") == "completed":
                        completed = payload
                        break

    assert completed is not None
    # report.md 가 없으므로 report_url 키 자체가 없거나 None 이어야 한다 (404 링크 금지).
    assert completed.get("report_url") is None


def test_sse_replay_resumes_after_last_event_id(monkeypatch, client: TestClient) -> None:
    """완료된 run을 Last-Event-ID로 재구독하면 그 이후만 받는다."""
    import json

    from tests.test_e2e import _patch_llm_and_data

    with _patch_llm_and_data(monkeypatch, n=500):
        _login(client)
        r = client.post(
            "/api/runs",
            json={"scenario_title": "t", "scenario_stimulus": "s", "n": 4, "model": "vllm-qwen"},
        )
        run_id = r.json()["run_id"]

        # 1차 — 끝까지 소비 (이후 replay 모드로 전환되도록)
        with client.stream("GET", f"/api/runs/{run_id}/events") as stream:
            for line in stream.iter_lines():
                if line.startswith("data:"):
                    payload = json.loads(line.removeprefix("data:").strip())
                    if payload.get("type") in {"completed", "error"}:
                        break

        # 2차 — Last-Event-ID=2 로 재구독, replay 경로
        received: list[dict] = []
        with client.stream(
            "GET",
            f"/api/runs/{run_id}/events",
            headers={"Last-Event-ID": "2"},
        ) as stream:
            for line in stream.iter_lines():
                if line.startswith("data:"):
                    payload = json.loads(line.removeprefix("data:").strip())
                    received.append(payload)
                    if payload.get("type") in {"completed", "error"}:
                        break

    persona_events = [e for e in received if e.get("type") == "persona_done"]
    # replay 경로의 event_id는 row index + 1 (1..N), 그 후 completed = N+1
    assert all(e["event_id"] >= 3 for e in persona_events), persona_events
    assert any(e["type"] == "completed" for e in received)
