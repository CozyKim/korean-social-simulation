"""FastAPI 의존성 — 인증, settings, IP 추출."""

from __future__ import annotations

import hmac
from typing import Annotated

from fastapi import Cookie, Depends, HTTPException, Request, status
from itsdangerous import BadSignature, TimestampSigner

from korean_social_simulation.api.config import Settings

COOKIE_NAME = "kss_owner"
COOKIE_VALUE = "1"


def get_settings(request: Request) -> Settings:
    return request.app.state.settings  # set in lifespan


SettingsDep = Annotated[Settings, Depends(get_settings)]


def _signer(settings: Settings) -> TimestampSigner:
    return TimestampSigner(settings.cookie_secret)


def issue_cookie(settings: Settings) -> str:
    """로그인 성공 시 발급할 서명된 쿠키 값."""
    return _signer(settings).sign(COOKIE_VALUE).decode("ascii")


def is_owner_cookie_valid(settings: Settings, raw: str | None) -> bool:
    if not raw:
        return False
    try:
        unsigned = _signer(settings).unsign(
            raw,
            max_age=settings.cookie_max_age_seconds,
        )
    except BadSignature:
        return False
    return unsigned == COOKIE_VALUE.encode("ascii")


def require_owner(
    settings: SettingsDep,
    kss_owner: Annotated[str | None, Cookie()] = None,
) -> None:
    if not is_owner_cookie_valid(settings, kss_owner):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="login required")


def optional_owner(
    settings: SettingsDep,
    kss_owner: Annotated[str | None, Cookie()] = None,
) -> bool:
    return is_owner_cookie_valid(settings, kss_owner)


def verify_owner_token(settings: Settings, candidate: str) -> bool:
    """timing-safe 비교."""
    return hmac.compare_digest(settings.owner_token, candidate)


def client_ip(settings: Settings, request: Request) -> str:
    """클라이언트 IP 추출 — proxy 신뢰 정책에 따라 결정.

    ``settings.trust_proxy_headers`` 가 True 일 때만 ``X-Forwarded-For`` 첫 값을
    사용하고, 그 외에는 ``request.client.host`` 를 사용한다. 직접 노출된 서버에서
    무조건 X-FF 를 신뢰하면 임의 클라이언트가 헤더를 spoof 해 IP rate limit 을
    우회할 수 있다.

    Args:
        settings: ``trust_proxy_headers`` 플래그 보유.
        request: FastAPI Request.

    Returns:
        IP 문자열. ``request.client`` 가 없고 X-FF 도 사용하지 않는 경우 ``"unknown"``.
    """
    if settings.trust_proxy_headers:
        fwd = request.headers.get("x-forwarded-for")
        if fwd:
            return fwd.split(",")[0].strip()
    return request.client.host if request.client else "unknown"
