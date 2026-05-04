"""POST/GET/PATCH/DELETE /api/runs — 본인 1명용 시뮬 관리."""

from __future__ import annotations

import asyncio
import logging
import uuid
from typing import Any

import httpx
from fastapi import APIRouter, Depends, HTTPException, Request, status

from korean_social_simulation.api.deps import (
    SettingsDep,
    is_owner_cookie_valid,
    require_owner,
)
from korean_social_simulation.api.job_manager import JobManager
from korean_social_simulation.api.persistence import (
    list_run_dirs,
    load_run_meta,
    to_summary,
    write_run_meta,
)
from korean_social_simulation.api.schemas import (
    CreateRunRequest,
    CreateRunResponse,
    PatchRunRequest,
)
from korean_social_simulation.scenario import Scenario
from korean_social_simulation.simulate import asimulate

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api", tags=["runs"])


def _job_manager(request: Request) -> JobManager:
    """app.state에서 JobManager 인스턴스를 꺼낸다."""
    return request.app.state.job_manager


def _avatar_key_from_row(row: dict[str, Any]) -> str | None:
    """sex_ageBand_province → 정적 자산 lookup 키. 후속 plan에서 자산 작성됨."""
    from korean_social_simulation.data.sampler import age_band

    sex = row.get("sex")
    age = row.get("age")
    province = row.get("province")
    if not (isinstance(sex, str) and isinstance(age, (int, float)) and isinstance(province, str)):
        return None
    return f"{sex}_{age_band(int(age))}_{province}"


@router.post(
    "/runs",
    response_model=CreateRunResponse,
    status_code=status.HTTP_202_ACCEPTED,
    dependencies=[Depends(require_owner)],
)
async def create_run(
    body: CreateRunRequest,
    request: Request,
    settings: SettingsDep,
) -> CreateRunResponse:
    """시뮬레이션을 백그라운드로 시작하고 run_id를 즉시 반환한다.

    Args:
        body: 시뮬레이션 요청 파라미터.
        request: FastAPI Request (app.state 접근용).
        settings: 앱 설정 (runs_root 등).

    Returns:
        run_id와 status="starting"을 담은 응답 (HTTP 202).
    """
    run_id = uuid.uuid4().hex
    jm = _job_manager(request)
    jm.register(run_id, total=body.n)

    scenario = Scenario(
        title=body.scenario_title,
        stimulus=body.scenario_stimulus,
        context=body.scenario_context,
        question=body.scenario_question,
        scenario_type=body.scenario_type,
    )

    async def _progress_sink(row: dict[str, Any]) -> None:
        state = jm.get(run_id)
        progress = state.progress if state is not None else 0
        avatar_key = _avatar_key_from_row(row)
        await jm.publish(
            run_id,
            {
                "type": "persona_done",
                "index": progress,
                "total": body.n,
                "persona": {
                    "sex": row.get("sex"),
                    "age": row.get("age"),
                    "province": row.get("province"),
                },
                "avatar_key": avatar_key,
                "reaction": {
                    "stance": row.get("stance"),
                    "intensity": row.get("intensity"),
                    "action_intent": row.get("action_intent"),
                    "quote": row.get("quote"),
                    "key_drivers": row.get("key_drivers"),
                    "concerns": row.get("concerns"),
                },
            },
        )

    async def _runner() -> None:
        try:
            await asimulate(
                scenario=scenario,
                n=body.n,
                model=body.model,
                seed=body.seed,
                concurrency=body.concurrency,
                filters=body.filters,
                runs_root=settings.runs_root,
                run_id=run_id,
                progress_sink=_progress_sink,
                min_cell_threshold=0,
            )
            await jm.complete(
                run_id,
                payload={"report_url": f"/api/runs/{run_id}/report"},
            )
        except Exception as exc:  # noqa: BLE001
            logger.exception("run %s failed", run_id)
            await jm.fail(run_id, error=f"{type(exc).__name__}: {exc}")

    asyncio.create_task(_runner())
    return CreateRunResponse(run_id=run_id, status="starting")


@router.get("/runs")
def list_runs(
    request: Request,
    settings: SettingsDep,
) -> list[dict]:
    """시뮬레이션 목록을 반환한다. 익명 사용자는 public=True 항목만, 오너는 전체.

    Args:
        request: FastAPI Request (쿠키 접근용).
        settings: 앱 설정 (runs_root).

    Returns:
        run 요약 딕셔너리 목록.
    """
    is_owner = is_owner_cookie_valid(settings, request.cookies.get("kss_owner"))
    out: list[dict] = []
    for run_path in list_run_dirs(settings.runs_root):
        meta = load_run_meta(run_path)
        if meta is None:
            continue
        if not is_owner and not meta.get("public", False):
            continue
        out.append(to_summary(meta))
    return out


@router.get("/runs/{run_id}")
def get_run(
    run_id: str,
    request: Request,
    settings: SettingsDep,
) -> dict:
    """특정 run의 상세 정보를 반환한다. 비공개 run을 익명 요청이 조회하면 404.

    Args:
        run_id: 조회할 run의 ID.
        request: FastAPI Request (쿠키 접근용).
        settings: 앱 설정 (runs_root).

    Returns:
        run 요약 + scenario 원문 + report_url 딕셔너리.

    Raises:
        HTTPException: run이 없거나 익명 사용자가 비공개 run에 접근 시 404.
    """
    is_owner = is_owner_cookie_valid(settings, request.cookies.get("kss_owner"))
    run_path = settings.runs_root / run_id
    meta = load_run_meta(run_path)
    if meta is None:
        raise HTTPException(status_code=404)
    if not is_owner and not meta.get("public", False):
        raise HTTPException(status_code=404)
    summary = to_summary(meta)
    summary["scenario"] = meta["scenario"]
    summary["report_url"] = f"/api/runs/{run_id}/report" if (run_path / "report.md").exists() else None
    return summary


@router.patch(
    "/runs/{run_id}",
    dependencies=[Depends(require_owner)],
)
async def patch_run(
    run_id: str,
    body: PatchRunRequest,
    settings: SettingsDep,
) -> dict:
    """run의 public 필드를 토글하고 Vercel revalidate hook을 호출한다.

    Args:
        run_id: 수정할 run의 ID.
        body: public 값을 담은 요청 바디.
        settings: 앱 설정 (runs_root, vercel_revalidate_hook_url 등).

    Returns:
        {"public": bool} 딕셔너리.

    Raises:
        HTTPException: run이 없으면 404.
    """
    run_path = settings.runs_root / run_id
    meta = load_run_meta(run_path)
    if meta is None:
        raise HTTPException(status_code=404)
    meta["public"] = body.public
    write_run_meta(run_path, meta)
    if settings.vercel_revalidate_hook_url:
        try:
            async with httpx.AsyncClient(timeout=5.0) as h:
                await h.post(
                    settings.vercel_revalidate_hook_url,
                    json={"path": f"/runs/{run_id}"},
                )
        except Exception as exc:  # noqa: BLE001
            logger.warning("revalidate hook failed: %s", exc)
    return {"public": body.public}
