"""LangChain chat model adapter for Codex OAuth."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from .client import CodexBackendClient
from .message_conversion import messages_to_codex_request_parts
from .store import AuthStore
from .tooling import convert_tools, normalize_tool_choice


class _MissingLangChainChatModel:
    """Placeholder used when LangChain is not installed in the environment."""

    pass


try:
    from langchain_core.callbacks import CallbackManagerForLLMRun
    from langchain_core.language_models.chat_models import BaseChatModel
    from langchain_core.messages import AIMessage, BaseMessage
    from langchain_core.outputs import ChatGeneration, ChatResult
except ModuleNotFoundError:  # pragma: no cover - exercised only without deps.
    CallbackManagerForLLMRun = Any
    BaseChatModel = _MissingLangChainChatModel
    AIMessage = None
    BaseMessage = Any
    ChatGeneration = None
    ChatResult = None


class ChatCodexOAuth(BaseChatModel):
    """LangChain-compatible chat model backed by Codex OAuth.

    This model targets the ChatGPT Codex consumer backend, not the public
    OpenAI API. It is suitable for local single-user workflows.
    """

    model: str = "gpt-5.5"
    timeout: float = 60.0
    max_retries: int = 2
    reasoning_effort: str | None = None
    temperature: float | None = None
    max_tokens: int | None = None
    text_verbosity: str | None = None
    auth_path: str | None = None
    bound_tools: list[dict[str, Any]] | None = None
    tool_choice: Any | None = None
    extra_instructions: str | None = None

    @property
    def _llm_type(self) -> str:
        """Return the LangChain model type identifier."""
        return "codex_oauth"

    @property
    def _identifying_params(self) -> dict[str, Any]:
        """Return identifying parameters for LangChain tracing."""
        return {
            "model": self.model,
            "reasoning_effort": self.reasoning_effort,
            "text_verbosity": self.text_verbosity,
        }

    def bind_tools(self, tools: list[Any], **kwargs: Any) -> ChatCodexOAuth:
        """Return a copy of this model with Codex-compatible tools bound."""
        return self.copy(
            update={
                "bound_tools": convert_tools(tools),
                "tool_choice": normalize_tool_choice(
                    kwargs.get("tool_choice", self.tool_choice)
                ),
            }
        )

    def _generate(
        self,
        messages: list[BaseMessage],
        stop: list[str] | None = None,
        run_manager: CallbackManagerForLLMRun | None = None,
        **kwargs: Any,
    ) -> ChatResult:
        """Generate one chat response."""
        if AIMessage is None or ChatGeneration is None or ChatResult is None:
            raise ModuleNotFoundError("langchain_core is required to use ChatCodexOAuth")

        instructions, input_items = messages_to_codex_request_parts(messages)
        if self.extra_instructions:
            instructions = (
                f"{instructions}\n\n{self.extra_instructions}"
                if instructions
                else self.extra_instructions
            )
        if not instructions:
            instructions = "You are a helpful assistant."

        parsed = self._client().complete(
            input_items=input_items,
            model=self.model,
            tools=self.bound_tools,
            tool_choice=self.tool_choice,
            temperature=kwargs.get("temperature", self.temperature),
            max_output_tokens=kwargs.get("max_tokens", self.max_tokens),
            reasoning_effort=kwargs.get("reasoning_effort", self.reasoning_effort),
            text_verbosity=kwargs.get("text_verbosity", self.text_verbosity),
            extra_instructions=instructions,
        )
        message = AIMessage(
            content=parsed.content,
            tool_calls=parsed.tool_calls,
            response_metadata=parsed.response_metadata,
            usage_metadata=parsed.usage_metadata,
        )
        return ChatResult(generations=[ChatGeneration(message=message)])

    def _client(self) -> CodexBackendClient:
        """Create a backend client for the current model invocation."""
        auth_store = AuthStore(Path(self.auth_path).expanduser()) if self.auth_path else AuthStore()
        return CodexBackendClient(
            auth_store=auth_store,
            timeout_s=self.timeout,
            max_retries=self.max_retries,
        )
