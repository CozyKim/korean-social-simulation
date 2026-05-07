# syntax=docker/dockerfile:1.7
FROM python:3.13-slim AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=0

RUN apt-get update && apt-get install -y --no-install-recommends \
        ca-certificates curl libgomp1 && rm -rf /var/lib/apt/lists/*

COPY --from=ghcr.io/astral-sh/uv:0.5.18 /uv /usr/local/bin/uv

WORKDIR /app

COPY pyproject.toml uv.lock ./
COPY README.md ./
COPY src ./src

RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev --extra api

ENV PATH="/app/.venv/bin:${PATH}" \
    KOREAN_SOCIAL_SIMULATION_CODEX_OAUTH_AUTH_PATH=/data/codex_oauth/auth.json \
    KSS_RUNS_ROOT=/data/runs \
    KSS_SCENARIOS_ROOT=/data/scenarios

EXPOSE 8001

CMD ["uvicorn", "korean_social_simulation.api.main:app", \
     "--host", "0.0.0.0", "--port", "8001", "--workers", "1"]
