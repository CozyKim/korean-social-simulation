"""Synchronous client for the ChatGPT Codex backend."""

from __future__ import annotations

import json
import random
import time
from collections.abc import Iterable, Iterator
from dataclasses import dataclass, field
from typing import Any

import requests

from .auth import (
    decode_jwt_payload,
    extract_chatgpt_account_id,
    refresh_access_token,
)
from .exceptions import CodexBackendError, NotAuthenticatedError
from .store import AuthStore, OAuthCredentials

CODEX_BASE_URL = "https://chatgpt.com/backend-api"
CODEX_RESPONSES_PATH = "/codex/responses"
DEFAULT_INCLUDE = ["reasoning.encrypted_content"]


@dataclass(frozen=True)
class ParsedCodexMessage:
    """Assistant message parsed from a Codex backend response."""

    content: str
    tool_calls: list[dict[str, Any]] = field(default_factory=list)
    response_metadata: dict[str, Any] = field(default_factory=dict)
    usage_metadata: dict[str, Any] | None = None


class CodexBackendClient:
    """Small client for the Codex consumer backend.

    This endpoint is not the public OpenAI API. It is intended for local,
    single-user research workflows where the user has authenticated with
    ChatGPT/Codex OAuth.
    """

    def __init__(
        self,
        auth_store: AuthStore | None = None,
        *,
        base_url: str = CODEX_BASE_URL,
        timeout_s: float = 60.0,
        max_retries: int = 2,
    ) -> None:
        """Initialize the backend client."""
        self._store = auth_store or AuthStore()
        self._base_url = base_url.rstrip("/")
        self._timeout_s = timeout_s
        self._max_retries = max_retries

    def complete(
        self,
        *,
        input_items: list[dict[str, Any]],
        model: str,
        tools: list[dict[str, Any]] | None = None,
        tool_choice: Any | None = None,
        temperature: float | None = None,
        max_output_tokens: int | None = None,
        reasoning_effort: str | None = None,
        text_verbosity: str | None = None,
        extra_instructions: str | None = None,
    ) -> ParsedCodexMessage:
        """Create one non-streaming completion by consuming the SSE stream."""
        last_response: Any = None
        output_items: list[dict[str, Any]] = []
        for event in self.stream_events(
            input_items=input_items,
            model=model,
            tools=tools,
            tool_choice=tool_choice,
            temperature=temperature,
            max_output_tokens=max_output_tokens,
            reasoning_effort=reasoning_effort,
            text_verbosity=text_verbosity,
            extra_instructions=extra_instructions,
        ):
            if event.get("type") == "response.output_item.done" and isinstance(
                event.get("item"), dict
            ):
                output_items.append(event["item"])
                continue

            if _is_terminal_event(event):
                last_response = event.get("response")
                if isinstance(last_response, dict) and output_items:
                    last_output = last_response.get("output")
                    if not isinstance(last_output, list) or not last_output:
                        last_response = {**last_response, "output": output_items}
                break
        return parse_assistant_message(last_response)

    def stream_events(
        self,
        *,
        input_items: list[dict[str, Any]],
        model: str,
        tools: list[dict[str, Any]] | None = None,
        tool_choice: Any | None = None,
        temperature: float | None = None,
        max_output_tokens: int | None = None,
        reasoning_effort: str | None = None,
        text_verbosity: str | None = None,
        extra_instructions: str | None = None,
    ) -> Iterator[dict[str, Any]]:
        """Yield SSE events from the Codex backend."""
        request_body = self._build_request_body(
            input_items=input_items,
            model=model,
            tools=tools,
            tool_choice=tool_choice,
            temperature=temperature,
            max_output_tokens=max_output_tokens,
            reasoning_effort=reasoning_effort,
            text_verbosity=text_verbosity,
            extra_instructions=extra_instructions,
        )
        url = f"{self._base_url}{CODEX_RESPONSES_PATH}"
        creds = self._load_valid_credentials()
        headers = self._headers(creds)

        attempt = 0
        while True:
            try:
                with requests.post(
                    url,
                    headers=headers,
                    json=request_body,
                    stream=True,
                    timeout=self._timeout_s,
                ) as response:
                    if response.status_code >= 400:
                        error = self._to_backend_error(response)
                        if _is_retryable_status(error.status_code) and attempt < self._max_retries:
                            time.sleep(_backoff_s(attempt))
                            attempt += 1
                            continue
                        raise error

                    yield from _iter_sse_events(response.iter_lines(decode_unicode=True))
                    return
            except requests.RequestException as exc:
                if attempt < self._max_retries:
                    time.sleep(_backoff_s(attempt))
                    attempt += 1
                    continue
                raise CodexBackendError("Network error calling Codex backend") from exc

    def _load_valid_credentials(self) -> OAuthCredentials:
        """Load credentials and refresh them when expired."""
        creds = self._store.load()
        if creds.expires > int(time.time() * 1000):
            return creds

        refreshed = refresh_access_token(refresh_token=creds.refresh)
        payload = decode_jwt_payload(refreshed.access)
        if not payload:
            raise NotAuthenticatedError("Refreshed Codex OAuth token is invalid.")
        account_id = extract_chatgpt_account_id(payload)
        if not account_id:
            raise NotAuthenticatedError("Could not derive ChatGPT account id.")
        new_creds = OAuthCredentials(
            access=refreshed.access,
            refresh=refreshed.refresh,
            expires=refreshed.expires_at_ms,
            account_id=account_id,
        )
        self._store.save(new_creds)
        return new_creds

    @staticmethod
    def _headers(creds: OAuthCredentials) -> dict[str, str]:
        """Build headers expected by the Codex backend."""
        return {
            "Authorization": f"Bearer {creds.access}",
            "chatgpt-account-id": creds.account_id,
            "OpenAI-Beta": "responses=experimental",
            "originator": "codex_cli_rs",
            "Accept": "text/event-stream",
        }

    @staticmethod
    def _build_request_body(
        *,
        input_items: list[dict[str, Any]],
        model: str,
        tools: list[dict[str, Any]] | None,
        tool_choice: Any | None,
        temperature: float | None,
        max_output_tokens: int | None,
        reasoning_effort: str | None,
        text_verbosity: str | None,
        extra_instructions: str | None,
    ) -> dict[str, Any]:
        """Build the Codex responses request body."""
        body: dict[str, Any] = {
            "model": model,
            "store": False,
            "stream": True,
            "input": input_items,
            "include": DEFAULT_INCLUDE,
        }
        if tools is not None:
            body["tools"] = tools
        if tool_choice is not None:
            body["tool_choice"] = tool_choice
        if temperature is not None:
            body["temperature"] = temperature
        if max_output_tokens is not None:
            body["max_output_tokens"] = max_output_tokens
        if reasoning_effort:
            body["reasoning"] = {"effort": reasoning_effort}
        if text_verbosity:
            body["text"] = {"verbosity": text_verbosity}
        if extra_instructions:
            body["instructions"] = extra_instructions
        return body

    @staticmethod
    def _to_backend_error(response: requests.Response) -> CodexBackendError:
        """Convert an HTTP error response to a safe exception."""
        status = response.status_code
        text = response.text[:1000]
        message = f"Codex backend request failed (HTTP {status})."
        try:
            parsed = response.json()
            if isinstance(parsed, dict) and isinstance(parsed.get("error"), dict):
                code = parsed["error"].get("code") or parsed["error"].get("type")
                if code:
                    message = f"Codex backend request failed (HTTP {status}, {code})."
        except ValueError:
            pass

        if status == 404 and _looks_like_usage_limit(text):
            status = 429
            message = "Codex usage limit reached for the ChatGPT subscription."
        if status == 400 and "not supported when using codex with a chatgpt account" in text.lower():
            message = (
                f"{message} Use a ChatGPT-account model such as "
                "`gpt-5.5`, `gpt-5.4-mini`, or `gpt-5.1-codex-max`."
            )
        if text:
            message = f"{message} Response excerpt: {text}"
        return CodexBackendError(message, status_code=status)


def _backoff_s(attempt: int) -> float:
    """Return a jittered exponential backoff duration."""
    base = min(8.0, 0.5 * (2**attempt))
    return base * (1.0 + random.random() * 0.1)


def _is_retryable_status(status_code: int | None) -> bool:
    """Return whether an HTTP status should be retried."""
    return status_code in {429, 500, 502, 503, 504}


def _looks_like_usage_limit(text: str) -> bool:
    """Return whether a response body looks like a subscription usage limit."""
    lower = text.lower()
    return any(
        token in lower
        for token in (
            "usage_limit_reached",
            "usage_not_included",
            "rate_limit_exceeded",
            "usage limit",
            "too many requests",
        )
    )


def _iter_sse_events(lines: Iterable[str]) -> Iterator[dict[str, Any]]:
    """Parse server-sent event lines into JSON event dictionaries."""
    buffer: list[str] = []
    for raw_line in lines:
        line = raw_line.decode("utf-8") if isinstance(raw_line, bytes) else raw_line
        if line == "":
            yield from _flush_sse_buffer(buffer)
            buffer = []
            continue
        if line.startswith("data:"):
            buffer.append(line[5:].strip())
    yield from _flush_sse_buffer(buffer)


def _flush_sse_buffer(buffer: list[str]) -> Iterator[dict[str, Any]]:
    """Parse a buffered SSE data block."""
    if not buffer:
        return
    data = "\n".join(buffer)
    if data == "[DONE]":
        return
    try:
        parsed = json.loads(data)
    except ValueError:
        return
    if isinstance(parsed, dict):
        yield parsed


def _is_terminal_event(event: dict[str, Any]) -> bool:
    """Return whether an SSE event contains the final response object."""
    event_type = str(event.get("type") or "")
    return event_type in {"response.completed", "response.done"}


def parse_assistant_message(response: Any) -> ParsedCodexMessage:
    """Parse assistant text and tool calls from a Codex response object."""
    if not isinstance(response, dict):
        return ParsedCodexMessage(content="")

    content_parts: list[str] = []
    tool_calls: list[dict[str, Any]] = []
    for item in _walk_response_items(response):
        item_type = item.get("type")
        if item_type in {"output_text", "text"}:
            text = item.get("text")
            if isinstance(text, str):
                content_parts.append(text)
        elif item_type in {"message", "assistant"}:
            _collect_message_content(item, content_parts)
        elif item_type in {"function_call", "tool_call"}:
            parsed_tool = _parse_tool_call(item)
            if parsed_tool:
                tool_calls.append(parsed_tool)

    content = "\n".join(part for part in content_parts if part).strip()
    metadata = {
        "id": response.get("id"),
        "model": response.get("model"),
        "finish_reason": response.get("finish_reason") or response.get("status"),
    }
    usage = response.get("usage")
    return ParsedCodexMessage(
        content=content,
        tool_calls=tool_calls,
        response_metadata={k: v for k, v in metadata.items() if v is not None},
        usage_metadata=usage if isinstance(usage, dict) else None,
    )


def _walk_response_items(response: dict[str, Any]) -> Iterator[dict[str, Any]]:
    """Yield likely output items from a response dictionary."""
    for key in ("output", "items", "content"):
        value = response.get(key)
        if isinstance(value, list):
            for item in value:
                if isinstance(item, dict):
                    yield item
                    nested = item.get("content")
                    if isinstance(nested, list):
                        for nested_item in nested:
                            if isinstance(nested_item, dict):
                                yield nested_item


def _collect_message_content(item: dict[str, Any], parts: list[str]) -> None:
    """Collect text content from a message-like response item."""
    content = item.get("content")
    if isinstance(content, str):
        parts.append(content)


def _parse_tool_call(item: dict[str, Any]) -> dict[str, Any] | None:
    """Parse a LangChain-compatible tool call dictionary."""
    name = item.get("name")
    if not isinstance(name, str) or not name:
        function = item.get("function")
        if isinstance(function, dict):
            name = function.get("name")
    if not isinstance(name, str) or not name:
        return None

    raw_args = item.get("arguments")
    if raw_args is None and isinstance(item.get("function"), dict):
        raw_args = item["function"].get("arguments")
    args: dict[str, Any]
    if isinstance(raw_args, str):
        try:
            loaded = json.loads(raw_args)
            args = loaded if isinstance(loaded, dict) else {}
        except ValueError:
            args = {}
    elif isinstance(raw_args, dict):
        args = raw_args
    else:
        args = {}

    return {
        "name": name,
        "args": args,
        "id": str(item.get("call_id") or item.get("id") or f"call_{name}"),
    }
