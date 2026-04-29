"""LLM factory 검증."""

import pytest

from korean_social_simulation.llm.factory import (
    DEFAULT_CONCURRENCY,
    available_models,
    get_llm,
)


def test_available_models_contains_expected_keys():
    keys = set(available_models())
    assert {"gpt-5.5", "gpt-5.4", "vllm-qwen", "vllm-exaone"}.issubset(keys)


def test_get_llm_unknown_model_raises():
    with pytest.raises(ValueError, match="Unknown model"):
        get_llm("does-not-exist")


def test_get_llm_codex_returns_chat_codex_oauth():
    from korean_social_simulation.llm.codex_oauth import ChatCodexOAuth

    llm = get_llm("gpt-5.5")
    assert isinstance(llm, ChatCodexOAuth)
    assert llm.model == "gpt-5.5"


def test_get_llm_vllm_uses_env_base_url(monkeypatch):
    monkeypatch.setenv("VLLM_BASE_URL", "http://vllm.example/v1")
    monkeypatch.setenv("VLLM_API_KEY", "secret")
    from langchain_openai import ChatOpenAI

    llm = get_llm("vllm-qwen")
    assert isinstance(llm, ChatOpenAI)
    # ChatOpenAI는 base_url을 openai_api_base로 보관
    assert "vllm.example" in str(getattr(llm, "openai_api_base", "")) or "vllm.example" in str(getattr(llm, "base_url", ""))


def test_default_concurrency_per_backend():
    assert DEFAULT_CONCURRENCY["gpt-5.5"] == 2
    assert DEFAULT_CONCURRENCY["gpt-5.4"] == 2
    assert DEFAULT_CONCURRENCY["vllm-qwen"] == 16
