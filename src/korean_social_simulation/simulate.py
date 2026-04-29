"""시뮬레이션 코어 — 1 페르소나 1 호출 + 병렬 실행."""

from __future__ import annotations

import asyncio
import logging
import time
from collections.abc import Mapping
from typing import Any

import pandas as pd
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import HumanMessage, SystemMessage
from pydantic import BaseModel, ValidationError

from korean_social_simulation.llm.prompts import (
    SIMULATION_INSTRUCTIONS,
    format_persona_block,
    format_scenario_block,
)
from korean_social_simulation.scenario import Scenario

logger = logging.getLogger(__name__)


_PERSONA_META_KEYS = (
    "uuid",
    "sex",
    "age",
    "province",
    "district",
    "occupation",
    "education_level",
    "family_type",
    "housing_type",
)


async def simulate_one(
    persona: Mapping[str, Any],
    scenario: Scenario,
    llm: BaseChatModel,
    reaction_model: type[BaseModel],
    *,
    max_attempts: int = 2,
) -> dict[str, Any]:
    """1 페르소나 × 1 시나리오 → 1 reaction dict.

    검증 실패 시 1회 재시도. 그래도 실패하면 ``error`` 필드를 채워 반환하여
    배치 시뮬레이션이 멈추지 않도록 한다.

    Args:
        persona: 페르소나 컬럼 매핑 (uuid, sex, age, ...).
        scenario: 입력 시나리오.
        llm: structured output을 지원하는 LangChain chat model.
        reaction_model: ``build_reaction_model`` 로 생성한 Pydantic 스키마.
        max_attempts: 검증/호출 실패 시 총 시도 횟수.

    Returns:
        페르소나 메타 + reaction 필드 + ``latency_ms``, ``error`` 가 합쳐진 dict.
    """
    structured = llm.with_structured_output(reaction_model)
    messages = [
        SystemMessage(content=SIMULATION_INSTRUCTIONS),
        HumanMessage(content=format_scenario_block(scenario)),
        HumanMessage(content=format_persona_block(persona)),
    ]

    start = time.perf_counter()
    last_error: str | None = None
    reaction: BaseModel | None = None

    for attempt in range(1, max_attempts + 1):
        try:
            reaction = await structured.ainvoke(messages)
            last_error = None
            break
        except ValidationError as exc:
            last_error = f"schema_validation: {exc.error_count()} errors"
            logger.warning(
                "Persona %s attempt %d failed: %s",
                persona.get("uuid"),
                attempt,
                last_error,
            )
        except Exception as exc:  # noqa: BLE001
            last_error = f"{type(exc).__name__}: {exc}"
            logger.warning(
                "Persona %s attempt %d errored: %s",
                persona.get("uuid"),
                attempt,
                last_error,
            )

    latency_ms = int((time.perf_counter() - start) * 1000)
    out: dict[str, Any] = {k: persona.get(k) for k in _PERSONA_META_KEYS}
    out["latency_ms"] = latency_ms
    out["error"] = last_error
    if reaction is not None:
        out.update(reaction.model_dump())
    return out


async def _run_async(
    sample: pd.DataFrame,
    scenario: Scenario,
    llm: BaseChatModel,
    reaction_model: type[BaseModel],
    *,
    concurrency: int,
) -> list[dict[str, Any]]:
    """N개 페르소나에 대해 시뮬을 병렬 실행하고 결과 list 반환.

    ``asyncio.Semaphore`` 로 동시 실행 LLM 호출 수를 제한하고,
    ``asyncio.gather`` 로 모든 페르소나의 결과를 한 번에 모은다.

    Args:
        sample: 페르소나 행을 담은 DataFrame.
        scenario: 입력 시나리오.
        llm: structured output 지원 LangChain chat model.
        reaction_model: ``build_reaction_model`` 로 생성한 Pydantic 스키마.
        concurrency: 최대 동시 LLM 호출 수.

    Returns:
        ``simulate_one`` 결과 dict의 리스트 (입력 순서 보존).
    """
    sem = asyncio.Semaphore(concurrency)

    async def _one(persona: Mapping[str, Any]) -> dict[str, Any]:
        async with sem:
            return await simulate_one(persona, scenario, llm, reaction_model)

    rows = sample.to_dict(orient="records")
    coros = [_one(row) for row in rows]
    return await asyncio.gather(*coros)
