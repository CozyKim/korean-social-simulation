"""사이트 로그인 — 본인 1명용 KSS_OWNER_TOKEN 시크릿."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request, Response, status

from korean_social_simulation.api.deps import (
    COOKIE_NAME,
    SettingsDep,
    client_ip,
    is_owner_cookie_valid,
    issue_cookie,
    verify_owner_token,
)
from korean_social_simulation.api.ratelimit import get_limiter
from korean_social_simulation.api.schemas import LoginRequest, MeResponse

router = APIRouter(prefix="/api", tags=["auth"])


@router.post("/auth/login")
def login(
    body: LoginRequest,
    response: Response,
    request: Request,
    settings: SettingsDep,
) -> dict[str, bool]:
    ip = client_ip(request)
    limiter = get_limiter()
    if not limiter.hit("auth_login", ip, max_per_window=5, window_s=60):
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="too many login attempts",
            headers={"Retry-After": "60"},
        )
    if not verify_owner_token(settings, body.token):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="invalid token",
        )
    response.set_cookie(
        key=COOKIE_NAME,
        value=issue_cookie(settings),
        max_age=settings.cookie_max_age_seconds,
        httponly=True,
        secure=settings.cookie_secure,
        samesite=settings.cookie_samesite,
    )
    return {"ok": True}


@router.post("/auth/logout")
def logout(response: Response) -> dict[str, bool]:
    response.delete_cookie(COOKIE_NAME)
    return {"ok": True}


@router.get("/me", response_model=MeResponse)
def me(request: Request, settings: SettingsDep) -> MeResponse:
    raw = request.cookies.get(COOKIE_NAME)
    return MeResponse(authenticated=is_owner_cookie_valid(settings, raw))
