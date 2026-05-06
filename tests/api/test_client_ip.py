"""``client_ip`` — X-Forwarded-For trust 정책.

기본 ``trust_proxy_headers=False`` 일 때는 X-FF 를 무시하고 ``request.client.host`` 를 사용한다.
spoofing 방지: 직접 노출된 서버에서 임의 클라이언트가 X-Forwarded-For 헤더로 IP rate limit 우회.

``trust_proxy_headers=True`` 일 때만 X-FF 첫 값 사용 (proxy 뒤에 있을 때).
"""

from __future__ import annotations

from pathlib import Path

import pytest
from fastapi import FastAPI, Request
from fastapi.testclient import TestClient

from korean_social_simulation.api.config import Settings
from korean_social_simulation.api.deps import client_ip


def _make_app(settings: Settings) -> FastAPI:
    app = FastAPI()
    app.state.settings = settings

    @app.get("/whoami")
    def _whoami(request: Request) -> dict[str, str]:
        return {"ip": client_ip(settings, request)}

    return app


@pytest.fixture
def base_settings(tmp_path: Path) -> Settings:
    return Settings(
        owner_token="t",
        cookie_secret="s",
        runs_root=tmp_path / "runs",
        scenarios_root=tmp_path / "scenarios",
        cors_origins=("http://localhost:3000",),
        vllm_base_url=None,
        vercel_revalidate_hook_url=None,
    )


def test_client_ip_ignores_xff_by_default(base_settings: Settings) -> None:
    """기본값(``trust_proxy_headers=False``) 에서는 X-Forwarded-For 를 무시한다."""
    settings = base_settings  # trust_proxy_headers 기본 False
    app = _make_app(settings)
    with TestClient(app) as c:
        r = c.get("/whoami", headers={"X-Forwarded-For": "1.2.3.4, 5.6.7.8"})
    assert r.status_code == 200
    # spoof 시도된 1.2.3.4 가 아니라 실제 client host 가 반환돼야 한다.
    assert r.json()["ip"] != "1.2.3.4"


def test_client_ip_uses_xff_when_trust_enabled(base_settings: Settings) -> None:
    """``trust_proxy_headers=True`` 일 때는 X-FF 첫 값을 사용한다."""
    settings = Settings(
        owner_token=base_settings.owner_token,
        cookie_secret=base_settings.cookie_secret,
        runs_root=base_settings.runs_root,
        scenarios_root=base_settings.scenarios_root,
        cors_origins=base_settings.cors_origins,
        vllm_base_url=base_settings.vllm_base_url,
        vercel_revalidate_hook_url=base_settings.vercel_revalidate_hook_url,
        trust_proxy_headers=True,
    )
    app = _make_app(settings)
    with TestClient(app) as c:
        r = c.get("/whoami", headers={"X-Forwarded-For": "1.2.3.4, 5.6.7.8"})
    assert r.status_code == 200
    assert r.json()["ip"] == "1.2.3.4"


def test_client_ip_falls_back_when_xff_absent(base_settings: Settings) -> None:
    """X-FF 가 없으면 trust 여부 무관하게 ``request.client.host`` 사용."""
    settings = Settings(
        owner_token=base_settings.owner_token,
        cookie_secret=base_settings.cookie_secret,
        runs_root=base_settings.runs_root,
        scenarios_root=base_settings.scenarios_root,
        cors_origins=base_settings.cors_origins,
        vllm_base_url=base_settings.vllm_base_url,
        vercel_revalidate_hook_url=base_settings.vercel_revalidate_hook_url,
        trust_proxy_headers=True,
    )
    app = _make_app(settings)
    with TestClient(app) as c:
        r = c.get("/whoami")
    assert r.status_code == 200
    # TestClient 의 기본 client host 는 "testclient" 또는 IP 형태.
    assert r.json()["ip"]  # non-empty


def test_settings_from_env_trust_proxy_headers_default_false(monkeypatch, tmp_path: Path) -> None:
    """환경변수 미설정 시 ``trust_proxy_headers=False``."""
    monkeypatch.setenv("KSS_OWNER_TOKEN", "t")
    monkeypatch.setenv("KSS_COOKIE_SECRET", "s")
    monkeypatch.setenv("KSS_RUNS_ROOT", str(tmp_path / "runs"))
    monkeypatch.setenv("KSS_SCENARIOS_ROOT", str(tmp_path / "scenarios"))
    monkeypatch.delenv("KSS_TRUST_PROXY_HEADERS", raising=False)
    settings = Settings.from_env()
    assert settings.trust_proxy_headers is False


def test_settings_from_env_trust_proxy_headers_true(monkeypatch, tmp_path: Path) -> None:
    """``KSS_TRUST_PROXY_HEADERS=true`` 일 때 True."""
    monkeypatch.setenv("KSS_OWNER_TOKEN", "t")
    monkeypatch.setenv("KSS_COOKIE_SECRET", "s")
    monkeypatch.setenv("KSS_RUNS_ROOT", str(tmp_path / "runs"))
    monkeypatch.setenv("KSS_SCENARIOS_ROOT", str(tmp_path / "scenarios"))
    monkeypatch.setenv("KSS_TRUST_PROXY_HEADERS", "true")
    settings = Settings.from_env()
    assert settings.trust_proxy_headers is True
