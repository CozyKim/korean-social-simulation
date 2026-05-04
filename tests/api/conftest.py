"""FastAPI TestClient 픽스처 — 환경변수 + 임시 디렉터리."""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def settings_env(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.setenv("KSS_OWNER_TOKEN", "test-secret-token")
    monkeypatch.setenv("KSS_COOKIE_SECRET", "test-cookie-secret-key")
    monkeypatch.setenv("KSS_RUNS_ROOT", str(tmp_path / "runs"))
    monkeypatch.setenv("KSS_SCENARIOS_ROOT", str(tmp_path / "scenarios"))
    monkeypatch.setenv("KSS_CORS_ORIGINS", "http://localhost:3000")
    (tmp_path / "runs").mkdir()
    (tmp_path / "scenarios").mkdir()
    return tmp_path


@pytest.fixture
def client(settings_env: Path) -> Iterator[TestClient]:
    from korean_social_simulation.api.main import create_app
    from korean_social_simulation.api.ratelimit import get_limiter

    get_limiter().reset()
    app = create_app()
    with TestClient(app) as c:
        yield c
