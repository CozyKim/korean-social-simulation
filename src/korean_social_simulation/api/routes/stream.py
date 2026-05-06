"""SSE 스트림 — 진행 중 run은 라이브, 완료된 run은 reactions.parquet replay."""

from __future__ import annotations

import asyncio
import json
from collections.abc import AsyncIterator
from pathlib import Path

import pandas as pd
from fastapi import APIRouter, Header, HTTPException, Query, Request, status
from fastapi.responses import StreamingResponse
from sse_starlette.sse import EventSourceResponse

from korean_social_simulation.api.avatar import avatar_key_from_row
from korean_social_simulation.api.deps import SettingsDep, is_owner_cookie_valid
from korean_social_simulation.api.job_manager import JobManager, JobStatus
from korean_social_simulation.api.safe_path import resolve_run_path

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
    last_event_id_header: int | None = Header(default=None, alias="Last-Event-ID", convert_underscores=False),
    last_event_id_query: int | None = Query(default=None, alias="last_event_id"),
):
    """SSE: 진행 중이면 JobManager 큐, 완료된 run이면 parquet replay.

    Args:
        run_id: 대상 run의 식별자.
        request: FastAPI Request (app.state 및 cookies 접근용).
        settings: 앱 설정 (runs_root 등).
        last_event_id_header: 재연결 시 ``Last-Event-ID`` 헤더값. 브라우저의 EventSource
            자동 재연결이 자동으로 채운다.
        last_event_id_query: 수동 재연결을 위한 ``?last_event_id=`` 쿼리 fallback —
            클라이언트(useSSE)가 페이지 새로고침 후 store 의 ``lastEventId`` 로 재구독할
            때 사용. 헤더가 있으면 헤더가 우선한다.

    Returns:
        EventSourceResponse — SSE 스트림.

    Raises:
        HTTPException(404): run이 존재하지 않거나 비공개이고 오너가 아닌 경우.
    """
    last_event_id = last_event_id_header if last_event_id_header is not None else last_event_id_query
    is_owner = is_owner_cookie_valid(settings, request.cookies.get("kss_owner"))
    jm = _job_manager(request)
    job = jm.get(run_id)

    # in-memory 분기를 두 갈래로 나눈다:
    # - ephemeral guest (``job.public=True``): ``/api/try`` mini-run. 디스크 산출물이
    #   전혀 없으므로 status 와 무관하게 in-memory 큐+backfill 로 처리해야 익명 게스트가
    #   완료 후에도 ``completed`` 이벤트를 받고 종료할 수 있다.
    # - 일반 owner job: 진행 중(STARTING/RUNNING) 일 때만 in-memory live. 완료/실패 후엔
    #   디스크 parquet replay 로 fall through 해야 한다 — ``JobState.events`` deque 는
    #   maxlen=1000 이라 ``n=1000`` 케이스에서 첫 persona_done 이 evict 되어 backfill 이
    #   누락되기 때문이다.
    if job is not None and job.public:
        # ephemeral guest. last_event_id 가 None 이면 0 으로 보정해 deque 의 모든 이벤트를
        # backfill — 이미 완료된 ephemeral job 의 client 가 늦게 구독해도 ``completed``
        # 이벤트를 받고 정상 종료되도록 한다.
        return EventSourceResponse(_live_stream(jm, run_id, last_event_id if last_event_id is not None else 0))

    if job is not None and job.status in {JobStatus.STARTING, JobStatus.RUNNING}:
        # 진행 중인 owner job — 디스크 meta 가 아직 없을 수도 있으므로 fallback 빈 dict.
        meta = _load_scenario_meta(settings.runs_root, run_id) or {}
        if not _is_visible(meta, is_owner):
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
        return EventSourceResponse(_live_stream(jm, run_id, last_event_id))

    # 완료/실패된 owner job 또는 in-memory 등록 자체가 없는 경우 — 디스크 replay.
    run_path = resolve_run_path(settings.runs_root, run_id)
    meta = _load_scenario_meta(settings.runs_root, run_id)
    if meta is None or not _is_visible(meta, is_owner):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
    return EventSourceResponse(_replay_stream(run_path, last_event_id or 0))


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
        # avatar_key 는 row 에 sex/age/province 가 있을 때만 산출. live 분기와 형식을 맞춤.
        row_dict = row.to_dict() if hasattr(row, "to_dict") else dict(row)
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
            "avatar_key": avatar_key_from_row(row_dict),
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


@router.get("/runs/{run_id}/reactions")
def get_reactions(
    run_id: str,
    request: Request,
    settings: SettingsDep,
) -> StreamingResponse:
    """reactions.parquet 파일을 스트림으로 반환한다.

    Args:
        run_id: 대상 run의 식별자.
        request: FastAPI Request (쿠키 접근용).
        settings: 앱 설정 (runs_root).

    Returns:
        StreamingResponse — application/vnd.apache.parquet MIME 타입.

    Raises:
        HTTPException(404): run이 없거나 비공개이고 오너가 아닌 경우, 또는 파일 미존재 시.
    """
    is_owner = is_owner_cookie_valid(settings, request.cookies.get("kss_owner"))
    run_path = resolve_run_path(settings.runs_root, run_id)
    meta = _load_scenario_meta(settings.runs_root, run_id)
    if meta is None or not _is_visible(meta, is_owner):
        raise HTTPException(status_code=404)
    parquet = run_path / "reactions.parquet"
    if not parquet.exists():
        raise HTTPException(status_code=404)

    def _iter():
        with parquet.open("rb") as f:
            while chunk := f.read(64 * 1024):
                yield chunk

    return StreamingResponse(_iter(), media_type="application/vnd.apache.parquet")


@router.get("/runs/{run_id}/charts/{name}")
def get_chart(
    run_id: str,
    name: str,
    request: Request,
    settings: SettingsDep,
) -> StreamingResponse:
    """차트 이미지(PNG/SVG)를 스트림으로 반환한다.

    Args:
        run_id: 대상 run의 식별자.
        name: 차트 파일명 (.png 또는 .svg만 허용).
        request: FastAPI Request (쿠키 접근용).
        settings: 앱 설정 (runs_root).

    Returns:
        StreamingResponse — image/png 또는 image/svg+xml MIME 타입.

    Raises:
        HTTPException(404): run이 없거나 비공개이고 오너가 아닌 경우, 파일 미존재, 또는 허용되지 않는 확장자.
    """
    is_owner = is_owner_cookie_valid(settings, request.cookies.get("kss_owner"))
    run_path = resolve_run_path(settings.runs_root, run_id)
    meta = _load_scenario_meta(settings.runs_root, run_id)
    if meta is None or not _is_visible(meta, is_owner):
        raise HTTPException(status_code=404)
    chart = run_path / "charts" / name
    if not chart.exists() or chart.suffix.lower() not in {".png", ".svg"}:
        raise HTTPException(status_code=404)
    media = "image/png" if chart.suffix.lower() == ".png" else "image/svg+xml"
    return StreamingResponse(chart.open("rb"), media_type=media)


@router.get("/runs/{run_id}/report")
def get_report(
    run_id: str,
    request: Request,
    settings: SettingsDep,
) -> StreamingResponse:
    """report.md 파일을 스트림으로 반환한다.

    Args:
        run_id: 대상 run의 식별자.
        request: FastAPI Request (쿠키 접근용).
        settings: 앱 설정 (runs_root).

    Returns:
        StreamingResponse — text/markdown; charset=utf-8 MIME 타입.

    Raises:
        HTTPException(404): run이 없거나 비공개이고 오너가 아닌 경우, 또는 파일 미존재 시.
    """
    is_owner = is_owner_cookie_valid(settings, request.cookies.get("kss_owner"))
    run_path = resolve_run_path(settings.runs_root, run_id)
    meta = _load_scenario_meta(settings.runs_root, run_id)
    if meta is None or not _is_visible(meta, is_owner):
        raise HTTPException(status_code=404)
    report = run_path / "report.md"
    if not report.exists():
        raise HTTPException(status_code=404)
    return StreamingResponse(report.open("rb"), media_type="text/markdown; charset=utf-8")
