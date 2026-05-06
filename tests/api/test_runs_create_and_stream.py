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


def test_sse_replay_resumes_from_query_param(monkeypatch, client: TestClient) -> None:
    """완료된 run을 ``?last_event_id=`` 쿼리로 재구독해도 그 이후만 받아야 한다.

    배경: EventSource 자동 재연결은 ``Last-Event-ID`` 헤더를 보내지만, 수동 재연결
    (e.g. 페이지 새로고침 후 useSSE 가 store 의 ``lastEventId`` 로 재구독) 시에는
    헤더를 추가할 수 없어 쿼리 파라미터 fallback 이 필요하다.
    """
    import json

    from tests.test_e2e import _patch_llm_and_data

    with _patch_llm_and_data(monkeypatch, n=500):
        _login(client)
        r = client.post(
            "/api/runs",
            json={"scenario_title": "t", "scenario_stimulus": "s", "n": 4, "model": "vllm-qwen"},
        )
        run_id = r.json()["run_id"]

        # 1차 — 완료까지 소비
        with client.stream("GET", f"/api/runs/{run_id}/events") as stream:
            for line in stream.iter_lines():
                if line.startswith("data:"):
                    payload = json.loads(line.removeprefix("data:").strip())
                    if payload.get("type") in {"completed", "error"}:
                        break

        # 2차 — 쿼리 파라미터로 last_event_id=2, replay 경로
        received: list[dict] = []
        with client.stream(
            "GET",
            f"/api/runs/{run_id}/events?last_event_id=2",
        ) as stream:
            for line in stream.iter_lines():
                if line.startswith("data:"):
                    payload = json.loads(line.removeprefix("data:").strip())
                    received.append(payload)
                    if payload.get("type") in {"completed", "error"}:
                        break

    persona_events = [e for e in received if e.get("type") == "persona_done"]
    assert all(e["event_id"] >= 3 for e in persona_events), persona_events
    assert any(e["type"] == "completed" for e in received)


def test_sse_header_overrides_query_last_event_id(monkeypatch, client: TestClient) -> None:
    """헤더와 쿼리가 동시에 올 경우 헤더가 우선해야 한다 (브라우저 자동 재연결)."""
    import json

    from tests.test_e2e import _patch_llm_and_data

    with _patch_llm_and_data(monkeypatch, n=500):
        _login(client)
        r = client.post(
            "/api/runs",
            json={"scenario_title": "t", "scenario_stimulus": "s", "n": 4, "model": "vllm-qwen"},
        )
        run_id = r.json()["run_id"]

        # 완료까지 소비
        with client.stream("GET", f"/api/runs/{run_id}/events") as stream:
            for line in stream.iter_lines():
                if line.startswith("data:"):
                    payload = json.loads(line.removeprefix("data:").strip())
                    if payload.get("type") in {"completed", "error"}:
                        break

        # 헤더=3, 쿼리=0 — 헤더 우선이면 4번째 persona_done 부터 받아야 함
        received: list[dict] = []
        with client.stream(
            "GET",
            f"/api/runs/{run_id}/events?last_event_id=0",
            headers={"Last-Event-ID": "3"},
        ) as stream:
            for line in stream.iter_lines():
                if line.startswith("data:"):
                    payload = json.loads(line.removeprefix("data:").strip())
                    received.append(payload)
                    if payload.get("type") in {"completed", "error"}:
                        break

    persona_events = [e for e in received if e.get("type") == "persona_done"]
    assert all(e["event_id"] >= 4 for e in persona_events), persona_events


def test_completed_owner_run_uses_disk_replay_not_in_memory(monkeypatch, client: TestClient) -> None:
    """완료된 owner run 을 재구독하면 in-memory deque(maxlen=1000) backfill 이 아니라
    디스크 parquet replay 분기로 가야 한다.

    배경: 허용 최대값 ``n=1000`` 에서 ``JobState.events`` deque 는 persona_done 1000개 +
    completed 1개로 가득 차 첫 persona_done 이 evict 된다. 디스크 산출물이 있는
    완료/실패 owner run 은 무조건 ``_replay_stream`` 으로 fall through 해야 클라이언트가
    빠짐없이 N 개를 받는다.

    분별 방법: live(``_live_stream``) 첫 이벤트는 ``{"run_id": ...}`` 키를 포함하고
    replay(``_replay_stream``) 첫 이벤트는 ``{"total": N}`` 키를 포함한다.
    """
    import json

    from tests.test_e2e import _patch_llm_and_data

    with _patch_llm_and_data(monkeypatch, n=500):
        _login(client)
        r = client.post(
            "/api/runs",
            json={"scenario_title": "t", "scenario_stimulus": "s", "n": 3, "model": "vllm-qwen"},
        )
        run_id = r.json()["run_id"]

        # 1차 — 완료까지 소비. 백그라운드 task 가 ``jm.complete`` 를 호출한 뒤에는
        # JobState 가 status=COMPLETED 로 in-memory 에 그대로 남는다.
        with client.stream("GET", f"/api/runs/{run_id}/events") as stream:
            for line in stream.iter_lines():
                if line.startswith("data:"):
                    payload = json.loads(line.removeprefix("data:").strip())
                    if payload.get("type") in {"completed", "error"}:
                        break

        # 2차 — 같은 run_id 를 재구독. disk parquet replay 로 가야 한다.
        first_started: dict | None = None
        with client.stream("GET", f"/api/runs/{run_id}/events") as stream:
            for line in stream.iter_lines():
                if line.startswith("data:"):
                    payload = json.loads(line.removeprefix("data:").strip())
                    if payload.get("type") == "started":
                        first_started = payload
                        break

    assert first_started is not None
    # replay 분기는 'total' 을 포함하고 'run_id' 는 포함하지 않는다.
    assert "total" in first_started, f"expected disk replay, got live event {first_started}"
    assert first_started.get("total") == 3
    assert "run_id" not in first_started
