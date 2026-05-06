"""게스트 mini-run — vLLM 전용, 강한 가드."""

from __future__ import annotations

import asyncio
import logging
import shutil
import tempfile
import uuid
from typing import Any

from fastapi import APIRouter, HTTPException, Request, status

from korean_social_simulation.api.avatar import avatar_key_from_row
from korean_social_simulation.api.deps import SettingsDep, client_ip
from korean_social_simulation.api.job_manager import JobManager
from korean_social_simulation.api.ratelimit import get_limiter
from korean_social_simulation.api.routes.health import _check_vllm, _vllm_state
from korean_social_simulation.api.schemas import CreateRunResponse, TryRunRequest
from korean_social_simulation.scenario import Scenario
from korean_social_simulation.simulate import asimulate

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api", tags=["try"])

GUEST_GLOBAL_CONCURRENT_LIMIT = 2
GUEST_PER_IP_PER_DAY = 1
GUEST_WINDOW_S = 24 * 60 * 60


def _job_manager(request: Request) -> JobManager:
    return request.app.state.job_manager


@router.post(
    "/try",
    response_model=CreateRunResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
async def try_run(
    body: TryRunRequest,
    request: Request,
    settings: SettingsDep,
) -> CreateRunResponse:
    """게스트 mini-run 엔드포인트.

    vLLM 가용 여부 확인 → IP rate limit → 전역 동시 한도 → 백그라운드 실행.
    결과는 디스크에 저장하지 않고 JobManager 이벤트로만 노출한다.

    Args:
        body: 시나리오 제목, 자극, 타입, n (1..20).
        request: FastAPI Request (app.state 접근용).
        settings: 앱 설정 (vllm_base_url 포함).

    Returns:
        :class:`CreateRunResponse` — run_id + "starting".

    Raises:
        HTTPException 503: vLLM 미설정 또는 vLLM 다운.
        HTTPException 429: IP별 1회/일 한도 초과.
        HTTPException 503: 전역 동시 2개 한도 초과.
    """
    if not settings.vllm_base_url:
        raise HTTPException(status_code=503, detail="vLLM not configured")

    vllm_status = str(_vllm_state.get("status", "unknown"))
    if vllm_status != "up":
        vllm_status = await _check_vllm(settings.vllm_base_url)
        if vllm_status != "up":
            raise HTTPException(status_code=503, detail="vLLM unreachable")

    ip = client_ip(request)
    limiter = get_limiter()
    if not limiter.hit("try_run", ip, max_per_window=GUEST_PER_IP_PER_DAY, window_s=GUEST_WINDOW_S):
        raise HTTPException(
            status_code=429,
            detail="guest mini-run limited to 1 per day per IP",
            headers={"Retry-After": str(GUEST_WINDOW_S)},
        )

    jm = _job_manager(request)
    if jm.active_count() >= GUEST_GLOBAL_CONCURRENT_LIMIT:
        raise HTTPException(status_code=503, detail="too many concurrent guest runs")

    run_id = uuid.uuid4().hex
    # ``public=True`` 로 등록해 익명 게스트가 자기 mini-run SSE 를 구독할 수 있게 한다.
    # ephemeral 실행이라 ``scenario.json`` 이 디스크에 남지 않으므로 stream.py 의
    # disk-meta 가시성 체크만으로는 충분하지 않다.
    jm.register(run_id, total=body.n, public=True)
    scenario = Scenario(
        title=body.scenario_title,
        stimulus=body.scenario_stimulus,
        scenario_type=body.scenario_type,
    )

    async def _progress_sink(row: dict[str, Any]) -> None:
        state = jm.get(run_id)
        progress = state.progress if state is not None else 0
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
                "avatar_key": avatar_key_from_row(row),
                "reaction": {
                    "stance": row.get("stance"),
                    "intensity": row.get("intensity"),
                    "quote": row.get("quote"),
                },
            },
        )

    async def _runner() -> None:
        tmp = tempfile.mkdtemp(prefix="kss-try-")
        try:
            try:
                await asimulate(
                    scenario=scenario,
                    n=body.n,
                    model="vllm-qwen",
                    seed=42,
                    concurrency=1,
                    runs_root=tmp,
                    min_cell_threshold=0,
                    progress_sink=_progress_sink,
                )
                await jm.complete(run_id, payload={"ephemeral": True})
            except Exception as exc:  # noqa: BLE001
                logger.exception("guest run %s failed", run_id)
                await jm.fail(run_id, error=f"{type(exc).__name__}: {exc}")
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    asyncio.create_task(_runner())
    return CreateRunResponse(run_id=run_id, status="starting")
