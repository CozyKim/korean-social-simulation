"""FastAPI 인스턴스 + CORS + 라우터 등록."""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from korean_social_simulation.api.config import Settings
from korean_social_simulation.api.job_manager import JobManager


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """앱 lifespan — JobManager 인스턴스를 app.state에 주입."""
    settings = Settings.from_env()
    app.state.settings = settings
    app.state.job_manager = JobManager()
    yield


def create_app() -> FastAPI:
    """FastAPI 앱 팩토리 — 테스트에서도 같은 함수로 인스턴스 생성."""
    app = FastAPI(title="Korean Social Simulation API", lifespan=lifespan)

    settings = Settings.from_env()
    app.add_middleware(
        CORSMiddleware,
        allow_origins=list(settings.cors_origins),
        allow_credentials=True,
        allow_methods=["GET", "POST", "PATCH", "DELETE", "OPTIONS"],
        allow_headers=["*"],
    )

    return app


app = create_app()
