"""환경변수 기반 설정.

본 spec의 단일 인스턴스 가정 + 본인 1명 인증 모델에 맞춰 최소화된 Settings.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

CookieSameSite = Literal["lax", "strict", "none"]


def _parse_samesite(raw: str | None) -> CookieSameSite:
    """KSS_COOKIE_SAMESITE 파싱 — 허용값 외에는 ``lax`` 로 fallback."""
    if not raw:
        return "lax"
    normalized = raw.strip().lower()
    if normalized in {"lax", "strict", "none"}:
        return normalized  # type: ignore[return-value]
    return "lax"


def _parse_bool(raw: str | None, *, default: bool = False) -> bool:
    """``true`` / ``1`` / ``yes`` 만 True 로 인정 (대소문자 무시)."""
    if raw is None:
        return default
    return raw.strip().lower() in {"true", "1", "yes", "on"}


@dataclass(frozen=True)
class Settings:
    """런타임 설정 — 모두 환경변수에서 로드."""

    owner_token: str
    cookie_secret: str
    runs_root: Path
    scenarios_root: Path
    cors_origins: tuple[str, ...]
    vllm_base_url: str | None
    vercel_revalidate_hook_url: str | None
    vercel_revalidate_secret: str = ""
    cookie_max_age_seconds: int = 60 * 60 * 24 * 30  # 30일
    cookie_samesite: CookieSameSite = "lax"
    cookie_secure: bool = False
    trust_proxy_headers: bool = False

    @classmethod
    def from_env(cls) -> Settings:
        token = os.environ.get("KSS_OWNER_TOKEN")
        if not token:
            raise RuntimeError("KSS_OWNER_TOKEN 환경변수가 필요합니다. 본인 1명용 사이트 로그인 시크릿을 설정하세요.")
        secret = os.environ.get("KSS_COOKIE_SECRET")
        if not secret:
            raise RuntimeError("KSS_COOKIE_SECRET 환경변수가 필요합니다 (itsdangerous 서명 키).")
        origins_raw = os.environ.get("KSS_CORS_ORIGINS", "http://localhost:3000")
        return cls(
            owner_token=token,
            cookie_secret=secret,
            runs_root=Path(os.environ.get("KSS_RUNS_ROOT", "runs")),
            scenarios_root=Path(os.environ.get("KSS_SCENARIOS_ROOT", "scenarios")),
            cors_origins=tuple(o.strip() for o in origins_raw.split(",") if o.strip()),
            vllm_base_url=os.environ.get("VLLM_BASE_URL"),
            vercel_revalidate_hook_url=os.environ.get("VERCEL_REVALIDATE_HOOK_URL"),
            vercel_revalidate_secret=os.environ.get("VERCEL_REVALIDATE_SECRET", ""),
            cookie_samesite=_parse_samesite(os.environ.get("KSS_COOKIE_SAMESITE")),
            cookie_secure=_parse_bool(os.environ.get("KSS_COOKIE_SECURE")),
            trust_proxy_headers=_parse_bool(os.environ.get("KSS_TRUST_PROXY_HEADERS")),
        )
