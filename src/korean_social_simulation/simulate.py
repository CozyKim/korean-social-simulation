"""시뮬레이션 코어 — 1 페르소나 1 호출 + 병렬 실행 + 공개 simulate()."""

from __future__ import annotations

import asyncio
import logging
import time
from collections.abc import Awaitable, Callable, Mapping
from pathlib import Path
from typing import Any

import pandas as pd
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import HumanMessage, SystemMessage
from pydantic import BaseModel, ValidationError

from korean_social_simulation._version import SAMPLER_VERSION
from korean_social_simulation.data.loader import load_personas
from korean_social_simulation.data.sampler import sample_personas_cached
from korean_social_simulation.llm.factory import DEFAULT_CONCURRENCY, get_llm
from korean_social_simulation.llm.prompts import (
    SIMULATION_INSTRUCTIONS,
    format_persona_block,
    format_scenario_block,
)
from korean_social_simulation.reaction import build_reaction_model
from korean_social_simulation.run import Run
from korean_social_simulation.scenario import Scenario

logger = logging.getLogger(__name__)

ProgressCallback = Callable[[dict[str, Any]], None]
ProgressSink = Callable[[dict[str, Any]], Awaitable[None]]


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
    on_progress: ProgressCallback | None = None,
    progress_sink: ProgressSink | None = None,
    pending_path: Path | None = None,
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
        on_progress: 페르소나 1건이 끝날 때마다 결과 dict를 받는 콜백
            (완료 순서대로 호출). 콜백 예외는 잡아서 로깅만 하고 계속 진행.
        progress_sink: 페르소나 1건이 끝날 때마다 await되는 async 콜백.
            콜백 예외는 잡아서 로깅만 하고 계속 진행.
        pending_path: ``Run.create_pending`` 으로 만든 run 디렉터리. 주어지면
            페르소나 결과를 ``reactions.partial.jsonl`` 에 도착 즉시 점진 저장.

    Returns:
        ``simulate_one`` 결과 dict의 리스트 (입력 순서 보존).
    """
    sem = asyncio.Semaphore(concurrency)

    async def _one(persona: Mapping[str, Any]) -> dict[str, Any]:
        async with sem:
            row = await simulate_one(persona, scenario, llm, reaction_model)
        if pending_path is not None:
            try:
                Run.append_partial(pending_path, row)
            except Exception:  # noqa: BLE001
                logger.exception("append_partial raised; continuing")
        if on_progress is not None:
            try:
                on_progress(row)
            except Exception:  # noqa: BLE001
                logger.exception("on_progress callback raised; continuing")
        if progress_sink is not None:
            try:
                await progress_sink(row)
            except Exception:  # noqa: BLE001
                logger.exception("progress_sink callback raised; continuing")
        return row

    rows = sample.to_dict(orient="records")
    coros = [_one(row) for row in rows]
    return await asyncio.gather(*coros)


async def asimulate(
    *,
    scenario: Scenario,
    n: int = 200,
    model: str = "vllm-qwen",
    seed: int = 42,
    filters: dict[str, Any] | None = None,
    action_intent_choices: list[str] | None = None,
    extra_fields: dict[str, tuple[type, str]] | None = None,
    min_cell_threshold: int = 5,
    concurrency: int | None = None,
    runs_root: Path | str = "runs",
    on_progress: ProgressCallback | None = None,
    run_id: str | None = None,
    progress_sink: ProgressSink | None = None,
) -> Run:
    """end-to-end 시뮬레이션 1회 실행 → Run 반환 (async).

    노트북·Streamlit·FastAPI 등 이미 이벤트 루프가 떠 있는 환경에서는 이
    async 진입점을 ``await`` 한다. 동기 컨텍스트에서는 :func:`simulate` 를 사용.

    Args:
        on_progress: 페르소나 1건이 끝날 때마다 결과 dict를 받는 콜백.
            진행률 표시용. (다른 인자는 :func:`simulate` 와 동일)
        run_id: 명시적 run_id. 주어지면 시뮬 시작 시점에 ``Run.create_pending`` 으로
            디렉터리를 선할당하고, 페르소나 결과를 ``reactions.partial.jsonl`` 에
            도착 즉시 점진 저장한다. 종료 시 parquet으로 변환. FastAPI job manager
            전용 옵션. None이면 기존 흐름(시뮬 종료 후 Run.create).
        progress_sink: 페르소나 1건이 끝날 때마다 await되는 async 콜백.
            FastAPI SSE event queue로 fan-out하기 위함.

    Raises:
        RuntimeError: 모든 페르소나의 LLM 호출이 실패해 결과를 만들 수 없을 때.
    """
    population_ds, dataset_fingerprint = load_personas()
    population_df = population_ds.to_pandas()

    sample = sample_personas_cached(
        population_df,
        n=n,
        seed=seed,
        dataset_fingerprint=dataset_fingerprint,
        filters=filters,
        min_cell_threshold=min_cell_threshold,
    )

    reaction_model = build_reaction_model(
        action_intent_choices=action_intent_choices,
        extra_fields=extra_fields,
    )
    llm = get_llm(model)
    conc = concurrency or DEFAULT_CONCURRENCY.get(model, 8)

    meta: dict[str, Any] = {
        "model": model,
        "n": n,
        "seed": seed,
        "filters": filters or {},
        "dataset_fingerprint": dataset_fingerprint,
        "sampler_version": SAMPLER_VERSION,
        "concurrency": conc,
        "min_cell_threshold": min_cell_threshold,
        "extra_field_names": list((extra_fields or {}).keys()),
        "extra_fields": _serialize_extra_fields(extra_fields),
        "action_intent_choices": action_intent_choices,
    }

    pending_path: Path | None = None
    if run_id is not None:
        pending_path = Run.create_pending(
            root=Path(runs_root),
            scenario=scenario,
            meta=meta,
            run_id=run_id,
        )

    try:
        rows = await _run_async(
            sample,
            scenario,
            llm,
            reaction_model,
            concurrency=conc,
            on_progress=on_progress,
            progress_sink=progress_sink,
            pending_path=pending_path,
        )
    except Exception as exc:
        if pending_path is not None:
            Run.mark_failed(pending_path, error=f"{type(exc).__name__}: {exc}")
        raise

    df = pd.DataFrame(rows)
    df["model"] = model

    if "stance" not in df.columns or df["stance"].isna().all():
        first_errors = df["error"].dropna().head(3).tolist() if "error" in df.columns else []
        if pending_path is not None:
            Run.mark_failed(pending_path, error=f"all_failed: {first_errors}")
        raise RuntimeError(f"All {len(df)} simulations failed. Sample errors: {first_errors}. Check the run directory for details.")

    if pending_path is not None:
        return Run.finalize_pending(pending_path, sample=sample)

    return Run.create(
        root=Path(runs_root),
        scenario=scenario,
        reactions=df,
        sample=sample,
        meta=meta,
    )


def simulate(
    *,
    scenario: Scenario,
    n: int = 200,
    model: str = "vllm-qwen",
    seed: int = 42,
    filters: dict[str, Any] | None = None,
    action_intent_choices: list[str] | None = None,
    extra_fields: dict[str, tuple[type, str]] | None = None,
    min_cell_threshold: int = 5,
    concurrency: int | None = None,
    runs_root: Path | str = "runs",
    on_progress: ProgressCallback | None = None,
    run_id: str | None = None,
    progress_sink: ProgressSink | None = None,
) -> Run:
    """동기 wrapper — 실행 중인 이벤트 루프가 있으면 명확히 안내하며 실패한다.

    노트북/pytest-asyncio/FastAPI처럼 이미 이벤트 루프가 떠 있는 환경에서는
    ``RuntimeError`` 를 발생시키며 :func:`asimulate` 사용을 안내한다.

    Args:
        scenario: 입력 시나리오.
        n: 샘플 크기 (기본 200).
        model: ``llm.factory.available_models()`` 키.
        seed: 샘플링 재현성 시드.
        filters: 모집단 필터.
        action_intent_choices: ReactionModel의 ``action_intent`` enum 오버라이드.
        extra_fields: 추가 reaction 필드.
        min_cell_threshold: 희소 셀 경고 기준 (0이면 비활성).
        concurrency: 동시 LLM 호출 수.
        runs_root: 산출물 루트 디렉터리.
        on_progress: 페르소나 1건이 끝날 때마다 결과 dict를 받는 콜백
            (완료 순서대로). 진행률 UI 등에 활용.
        run_id: 명시적 run_id. 주어지면 ``Run.create_pending`` 으로 디렉터리 선할당.
        progress_sink: 페르소나 1건이 끝날 때마다 await되는 async 콜백.

    Returns:
        ``Run`` 인스턴스.

    Raises:
        RuntimeError: 이벤트 루프가 이미 실행 중이거나, 모든 페르소나의 LLM
            호출이 실패한 경우.
    """
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        pass
    else:
        raise RuntimeError("simulate()는 동기 컨텍스트에서만 호출할 수 있습니다. 노트북·async 환경에서는 `await asimulate(...)` 를 사용하세요.")

    return asyncio.run(
        asimulate(
            scenario=scenario,
            n=n,
            model=model,
            seed=seed,
            filters=filters,
            action_intent_choices=action_intent_choices,
            extra_fields=extra_fields,
            min_cell_threshold=min_cell_threshold,
            concurrency=concurrency,
            runs_root=runs_root,
            on_progress=on_progress,
            run_id=run_id,
            progress_sink=progress_sink,
        )
    )


def _serialize_extra_fields(
    extra_fields: dict[str, tuple[type, str]] | None,
) -> dict[str, dict[str, str]] | None:
    """``extra_fields`` 정의를 scenario.json에 안전히 저장 가능한 형태로 변환.

    ``type`` 객체는 직렬화 불가하므로 이름 문자열로 보존한다.
    """
    if not extra_fields:
        return None
    return {name: {"type": typ.__name__, "description": desc} for name, (typ, desc) in extra_fields.items()}
