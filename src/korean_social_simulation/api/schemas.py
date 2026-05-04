"""API request/response Pydantic 모델."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class LoginRequest(BaseModel):
    token: str = Field(min_length=1, max_length=256)


class MeResponse(BaseModel):
    authenticated: bool


class HealthResponse(BaseModel):
    status: str
    vllm: str  # "up" | "down" | "unknown"
    active_jobs: int


class CreateRunRequest(BaseModel):
    scenario_title: str = Field(min_length=1, max_length=200)
    scenario_stimulus: str = Field(min_length=1, max_length=4096)
    scenario_context: str | None = Field(default=None, max_length=2048)
    scenario_question: str | None = Field(default=None, max_length=1024)
    scenario_type: str = "other"
    n: int = Field(ge=1, le=1000)
    model: str
    seed: int = 42
    concurrency: int | None = None
    filters: dict[str, Any] | None = None
    insights_model: str | None = None


class CreateRunResponse(BaseModel):
    run_id: str
    status: str  # "starting"


class TryRunRequest(BaseModel):
    scenario_title: str = Field(min_length=1, max_length=200)
    scenario_stimulus: str = Field(min_length=1, max_length=4096)
    scenario_type: str = "other"
    n: int = Field(ge=1, le=20)


class PatchRunRequest(BaseModel):
    public: bool


class RunSummary(BaseModel):
    run_id: str
    title: str
    model: str
    n: int
    status: str
    public: bool
    created_at: str
