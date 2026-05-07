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


def test_post_runs_then_get_run_returns_200(monkeypatch, client: TestClient) -> None:
    """POST /api/runs 직후 즉시 GET /api/runs/{id} 가 200 + status='starting'.

    배경: 프론트가 202 받자마자 ``/app/runs/{id}`` 로 이동하면 SSR이 GET 을 호출.
    이 시점에 background ``_runner`` 가 아직 ``Run.create_pending`` 을 부르기 전이면
    ``scenario.json`` 이 디스크에 없어 404 가 떨어진다. 라우트가 202 반환 전에
    동기적으로 디렉터리를 선할당하여 이 race 를 닫아야 한다.
    """
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
        run_id = r.json()["run_id"]

        # 즉시 GET — background 작업 진행 여부와 무관하게 200 이어야 한다.
        get_res = client.get(f"/api/runs/{run_id}")
        assert get_res.status_code == 200
        body = get_res.json()
        # 시뮬이 진행 중이거나 갓 끝났을 수 있으니 starting/running/completed 모두 허용.
        assert body["status"] in {"starting", "running", "completed"}
        assert body["title"] == "t"
        assert body["n"] == 2


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


def test_active_owner_run_fresh_subscribe_backfills_existing_events(client: TestClient) -> None:
    """진행 중 owner run 에 늦게 구독한 클라이언트는 이미 발행된 이벤트를 backfill 받아야 한다.

    배경: ``stream.py`` 의 owner active 분기가 ``last_event_id`` 를 그대로 ``subscribe`` 에
    넘기는데, fresh subscribe (헤더/쿼리 없음) 시 ``last_event_id=None`` 이면
    ``JobManager.subscribe`` 가 backfill 을 건너뛴다. 그 결과 이미 ``persona_done`` 이
    여러 건 발행된 활성 run 을 늦게 연 사용자는 진행 중인 N개를 받지 못한다.

    검증: ``JobManager`` 에 직접 register + publish 로 이벤트 N개를 미리 쌓고,
    ``GET /events`` 로 fresh subscribe → backfill 로 N개 모두 수신.
    """
    import asyncio
    import json
    import threading
    import time

    from korean_social_simulation.run import Run
    from korean_social_simulation.scenario import Scenario

    _login(client)

    app = client.app
    runs_root = app.state.settings.runs_root
    jm = app.state.job_manager
    run_id = "active-backfill-rid"

    # 디스크에 owner-소유(public=False) scenario.json 미리 생성. _is_visible 통과용.
    Run.create_pending(
        root=runs_root,
        scenario=Scenario(title="t", stimulus="s"),
        meta={"model": "vllm-qwen", "n": 3, "seed": 42, "filters": {}, "concurrency": 1},
        run_id=run_id,
        status="starting",
    )

    # JobManager 에 active 등록 + publish 3건 (status=STARTING → 첫 publish 후 RUNNING).
    # status 를 RUNNING 으로 유지한 채 stream 을 열어야 owner active 분기를 탄다.
    jm.register(run_id, total=3)
    loop = asyncio.new_event_loop()
    try:
        for i in range(3):
            loop.run_until_complete(
                jm.publish(
                    run_id,
                    {
                        "type": "persona_done",
                        "index": i,
                        "total": 3,
                        "persona": {"sex": "남", "age": 30, "province": "서울특별시"},
                        "avatar_key": "male_30_seoul",
                        "reaction": {"stance": "positive", "intensity": 4, "action_intent": "purchase", "quote": f"q{i}"},
                    },
                )
            )
    finally:
        loop.close()

    # 별도 thread 에서 짧은 delay 후 complete 발행 — stream 이 backfill 을 모두
    # 소비한 뒤 종료할 수 있도록. 동기 TestClient 에서 stream 을 끊기 위한 패턴.
    def _delayed_complete() -> None:
        time.sleep(0.5)
        loop2 = asyncio.new_event_loop()
        try:
            loop2.run_until_complete(jm.complete(run_id))
        finally:
            loop2.close()

    threading.Thread(target=_delayed_complete, daemon=True).start()

    # fresh subscribe — Last-Event-ID 헤더/쿼리 없음. owner active 분기가 backfill 안 하면
    # persona_done 이벤트는 0건이고 completed 만 받게 된다.
    received: list[dict] = []
    with client.stream("GET", f"/api/runs/{run_id}/events") as stream:
        for line in stream.iter_lines():
            if line.startswith("data:"):
                payload = json.loads(line.removeprefix("data:").strip())
                received.append(payload)
                if payload.get("type") in {"completed", "error"}:
                    break

    persona_events = [e for e in received if e.get("type") == "persona_done"]
    # backfill 이 적용되면 3건 모두 받아야 한다. 미적용 시 0건.
    assert len(persona_events) == 3, f"expected 3 backfilled persona_done, got {len(persona_events)}: {received}"
    assert any(e.get("type") == "completed" for e in received)


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
