"""모델 ID → BaseChatModel 인스턴스. 백엔드별 디폴트 동시성 정의."""

from __future__ import annotations

import os
from collections.abc import Callable

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_openai import ChatOpenAI

from korean_social_simulation.llm.codex_oauth import ChatCodexOAuth


def _codex(model: str) -> Callable[[], BaseChatModel]:
    """Codex OAuth 기반 ChatCodexOAuth 빌더 반환."""
    return lambda: ChatCodexOAuth(model=model, reasoning_effort="medium")


def _vllm(model_id: str) -> Callable[[], BaseChatModel]:
    """vLLM OpenAI 호환 엔드포인트용 ChatOpenAI 빌더 반환."""

    def _build() -> BaseChatModel:
        return ChatOpenAI(
            base_url=os.environ.get("VLLM_BASE_URL", "http://localhost:8000/v1"),
            api_key=lambda: os.environ.get("VLLM_API_KEY", "EMPTY"),
            model=model_id,
            temperature=0.7,
        )

    return _build


_PRESETS: dict[str, Callable[[], BaseChatModel]] = {
    "gpt-5.5": _codex("gpt-5.5"),
    "gpt-5.4": _codex("gpt-5.4"),
    "gpt-5.4-nano": _codex("gpt-5.4-nano"),
    "gpt-5.4-mini": _codex("gpt-5.4-mini"),
    "vllm-qwen": _vllm("Qwen2.5-72B-Instruct"),
    "vllm-exaone": _vllm("LGAI-EXAONE/EXAONE-3.5-32B-Instruct"),
}

DEFAULT_CONCURRENCY: dict[str, int] = {
    "gpt-5.5": 2,
    "gpt-5.4": 2,
    "gpt-5.4-nano": 2,
    "vllm-qwen": 16,
    "vllm-exaone": 16,
}


def available_models() -> list[str]:
    """사용 가능한 모델 ID 목록 반환."""
    return list(_PRESETS.keys())


def get_llm(model: str) -> BaseChatModel:
    """모델 ID로 LangChain BaseChatModel 인스턴스 생성.

    Args:
        model: 등록된 프리셋 모델 ID (예: ``"gpt-5.5"``).

    Returns:
        지정된 백엔드용 ``BaseChatModel`` 인스턴스.

    Raises:
        ValueError: ``model`` 이 등록된 프리셋에 없을 때.
    """
    if model not in _PRESETS:
        raise ValueError(f"Unknown model: {model!r}. Available: {available_models()}")
    return _PRESETS[model]()
