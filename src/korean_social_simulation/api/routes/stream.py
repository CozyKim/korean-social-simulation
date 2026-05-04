"""SSE 스트림 — 진행 중 run은 라이브, 완료된 run은 reactions.parquet replay."""

from __future__ import annotations

import asyncio
import json
from collections.abc import AsyncIterator
from pathlib import Path

import pandas as pd
from fastapi import APIRouter, Header, HTTPException, Request, status
from sse_starlette.sse import EventSourceResponse

from korean_social_simulation.api.deps import SettingsDep, is_owner_cookie_valid
from korean_social_simulation.api.job_manager import JobManager, JobStatus

router = APIRouter(prefix="/api", tags=["stream"])


HEARTBEAT_INTERVAL_S = 15
REPLAY_INTERVAL_S = 0.05


def _job_manager(request: Request) -> JobManager:
    return request.app.state.job_manager


def _is_visible(scenario_meta: dict, is_owner: bool) -> bool:
    if is_owner:
        return True
    return bool(scenario_meta.get("public"))


def _load_scenario_meta(runs_root: Path, run_id: str) -> dict | None:
    meta_path = runs_root / run_id / "scenario.json"
    if not meta_path.exists():
        return None
    return json.loads(meta_path.read_text(encoding="utf-8"))


@router.get("/runs/{run_id}/events")
async def stream_run_events(
    run_id: str,
    request: Request,
    settings: SettingsDep,
    last_event_id: int | None = Header(default=None, alias="Last-Event-ID", convert_underscores=False),
):
    """SSE: 진행 중이면 JobManager 큐, 완료된 run이면 parquet replay.

    Args:
        run_id: 대상 run의 식별자.
        request: FastAPI Request (app.state 및 cookies 접근용).
        settings: 앱 설정 (runs_root 등).
        last_event_id: 재연결 시 Last-Event-ID 헤더값 — 이미 수신한 이벤트를 건너뜀.

    Returns:
        EventSourceResponse — SSE 스트림.

    Raises:
        HTTPException(404): run이 존재하지 않거나 비공개이고 오너가 아닌 경우.
    """
    is_owner = is_owner_cookie_valid(settings, request.cookies.get("kss_owner"))
    jm = _job_manager(request)
    job = jm.get(run_id)

    if job is not None and job.status in {JobStatus.STARTING, JobStatus.RUNNING}:
        meta = _load_scenario_meta(settings.runs_root, run_id) or {}
        if not _is_visible(meta, is_owner):
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
        return EventSourceResponse(_live_stream(jm, run_id, last_event_id))

    meta = _load_scenario_meta(settings.runs_root, run_id)
    if meta is None:
        # 아직 active(STARTING/RUNNING)인 job을 위에서 확인했으므로 — 여기까지 왔다면
        # job이 없거나 이미 완료/실패됐지만 parquet이 없다.
        # job 자체가 존재하고 완료됐을 수도 있으므로 job.status도 확인.
        if job is not None:
            # job은 있지만 scenario.json이 아직 없으면(파일 미완성 등) 404
            if not _is_visible({}, is_owner):
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
        else:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
    if meta is not None and not _is_visible(meta, is_owner):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
    if meta is not None:
        return EventSourceResponse(_replay_stream(settings.runs_root / run_id, last_event_id or 0))
    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)


async def _live_stream(
    jm: JobManager,
    run_id: str,
    last_event_id: int | None,
) -> AsyncIterator[dict]:
    """JobManager 큐에서 이벤트를 읽어 SSE로 전달한다.

    Args:
        jm: JobManager 인스턴스.
        run_id: 대상 run 식별자.
        last_event_id: 재연결 시 이 event_id 이하 이벤트는 건너뜀.

    Yields:
        SSE 이벤트 딕셔너리 (id, data).
    """
    queue = jm.subscribe(run_id, last_event_id=last_event_id)
    try:
        yield {
            "id": "0",
            "data": json.dumps({"type": "started", "run_id": run_id, "event_id": 0}),
        }
        while True:
            try:
                evt = await asyncio.wait_for(queue.get(), timeout=HEARTBEAT_INTERVAL_S)
            except TimeoutError:
                yield {"event": "heartbeat", "data": json.dumps({"type": "heartbeat"})}
                continue
            yield {"id": str(evt["event_id"]), "data": json.dumps(evt, ensure_ascii=False)}
            if evt["type"] in {"completed", "error"}:
                break
    finally:
        jm.unsubscribe(run_id, queue)


async def _replay_stream(run_path: Path, last_event_id: int) -> AsyncIterator[dict]:
    """reactions.parquet을 읽어 SSE 이벤트로 replay한다.

    Args:
        run_path: run 디렉터리 경로.
        last_event_id: 이 값 이하의 event_id는 건너뜀 (0이면 전부 전송).

    Yields:
        SSE 이벤트 딕셔너리 (id, data).
    """
    parquet = run_path / "reactions.parquet"
    if not parquet.exists():
        yield {"data": json.dumps({"type": "error", "error": "reactions.parquet missing"})}
        return
    df = pd.read_parquet(parquet)
    yield {"id": "0", "data": json.dumps({"type": "started", "event_id": 0, "total": len(df)})}
    for idx, row in df.reset_index(drop=True).iterrows():
        eid = int(idx) + 1
        if eid <= last_event_id:
            continue
        evt = {
            "type": "persona_done",
            "event_id": eid,
            "index": int(idx),
            "total": len(df),
            "persona": {
                "sex": row.get("sex"),
                "age": int(row["age"]) if pd.notna(row.get("age")) else None,
                "province": row.get("province"),
            },
            "reaction": {
                "stance": row.get("stance"),
                "intensity": int(row["intensity"]) if pd.notna(row.get("intensity")) else None,
                "action_intent": row.get("action_intent"),
                "quote": row.get("quote"),
            },
        }
        yield {"id": str(eid), "data": json.dumps(evt, ensure_ascii=False, default=str)}
        await asyncio.sleep(REPLAY_INTERVAL_S)
    final_eid = len(df) + 1
    yield {"id": str(final_eid), "data": json.dumps({"type": "completed", "event_id": final_eid})}
