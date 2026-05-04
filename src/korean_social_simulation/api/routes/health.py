"""헬스체크 + vLLM 가용성 60초 캐시."""

from __future__ import annotations

import time
from typing import Any

import httpx
from fastapi import APIRouter, Request

from korean_social_simulation.api.deps import SettingsDep
from korean_social_simulation.api.schemas import HealthResponse

router = APIRouter(prefix="/api", tags=["health"])

_VLLM_CACHE_TTL_S = 60
_vllm_state: dict[str, Any] = {"status": "unknown", "ts": 0.0}


async def _check_vllm(base_url: str) -> str:
    """vLLM /models 엔드포인트를 호출해 가용 여부를 반환.

    Args:
        base_url: vLLM 백엔드 base URL (예: ``http://localhost:8000/v1``).

    Returns:
        ``"up"`` 또는 ``"down"``.
    """
    try:
        async with httpx.AsyncClient(timeout=5.0) as h:
            r = await h.get(f"{base_url.rstrip('/')}/models")
            return "up" if r.status_code == 200 else "down"
    except Exception:  # noqa: BLE001
        return "down"


@router.get("/health", response_model=HealthResponse)
async def health(request: Request, settings: SettingsDep) -> HealthResponse:
    """헬스체크 엔드포인트.

    vLLM 가용성은 60초마다 최대 1회만 확인한다 (모듈 레벨 캐시).
    VLLM_BASE_URL 미설정 시 즉시 ``"down"`` 반환.

    Args:
        request: FastAPI Request (app.state.job_manager 접근용).
        settings: 앱 설정 (vllm_base_url 포함).

    Returns:
        :class:`HealthResponse` — status/vllm/active_jobs.
    """
    if not settings.vllm_base_url:
        vllm_status = "down"
    else:
        now = time.monotonic()
        if now - float(_vllm_state["ts"]) > _VLLM_CACHE_TTL_S:
            _vllm_state["status"] = await _check_vllm(settings.vllm_base_url)
            _vllm_state["ts"] = now
        vllm_status = str(_vllm_state["status"])

    return HealthResponse(
        status="ok",
        vllm=vllm_status,
        active_jobs=request.app.state.job_manager.active_count(),
    )
