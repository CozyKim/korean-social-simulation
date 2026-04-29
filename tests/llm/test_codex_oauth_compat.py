"""ChatCodexOAuth가 LangChain 1.x BaseChatModel 인터페이스에 호환되는지 검증."""

import inspect

from korean_social_simulation.llm.codex_oauth import ChatCodexOAuth


def test_chat_codex_oauth_is_base_chat_model_subclass():
    from langchain_core.language_models.chat_models import BaseChatModel

    assert issubclass(ChatCodexOAuth, BaseChatModel)


def test_chat_codex_oauth_implements_required_methods():
    assert hasattr(ChatCodexOAuth, "_generate")
    assert hasattr(ChatCodexOAuth, "_llm_type")
    assert hasattr(ChatCodexOAuth, "bind_tools")


def test_generate_signature_compatible_with_1x():
    sig = inspect.signature(ChatCodexOAuth._generate)
    params = sig.parameters
    # 1.x 표준 시그니처: self, messages, stop, run_manager, **kwargs
    assert "messages" in params
    assert "stop" in params
    assert "run_manager" in params


def test_with_structured_output_returns_runnable():
    """LangChain 1.x의 with_structured_output이 동작하는지."""
    from pydantic import BaseModel

    class Out(BaseModel):
        answer: str

    model = ChatCodexOAuth(model="gpt-5.5")
    runnable = model.with_structured_output(Out)
    assert runnable is not None
    assert hasattr(runnable, "invoke") or hasattr(runnable, "ainvoke")
