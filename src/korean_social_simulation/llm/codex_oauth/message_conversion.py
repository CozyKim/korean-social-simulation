"""Conversion between LangChain messages and Codex response input items."""

from __future__ import annotations

import json
from typing import Any


def messages_to_input_items(messages: list[Any]) -> list[dict[str, Any]]:
    """Convert LangChain messages or dict messages to Codex input items."""
    _, items = messages_to_codex_request_parts(messages)
    return items


def messages_to_codex_request_parts(messages: list[Any]) -> tuple[str, list[dict[str, Any]]]:
    """Split LangChain messages into Codex instructions and input items."""
    instructions: list[str] = []
    items: list[dict[str, Any]] = []
    for message in messages:
        role = _message_role(message)
        content = _message_content(message)
        tool_call_id = _message_tool_call_id(message)

        if role == "system":
            if content:
                instructions.append(content)
            continue

        if role == "tool":
            items.append(
                {
                    "type": "function_call_output",
                    "call_id": tool_call_id or "",
                    "output": content,
                }
            )
            continue

        tool_calls = _message_tool_calls(message)
        if role == "assistant" and tool_calls:
            if content:
                items.append({"role": role, "content": content})
            for tool_call in tool_calls:
                items.append(_tool_call_to_input_item(tool_call))
            continue

        items.append({"role": role, "content": content})
    return "\n\n".join(instructions), items


def _message_role(message: Any) -> str:
    """Return a Codex-compatible role for a message."""
    if isinstance(message, dict):
        return str(message.get("role") or "user")
    message_type = getattr(message, "type", None)
    if message_type == "human":
        return "user"
    if message_type == "ai":
        return "assistant"
    if message_type in {"system", "tool"}:
        return str(message_type)
    return "user"


def _message_content(message: Any) -> str:
    """Return message content as plain text."""
    content = (
        message.get("content")
        if isinstance(message, dict)
        else getattr(message, "content", "")
    )
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = []
        for item in content:
            if isinstance(item, str):
                parts.append(item)
            elif isinstance(item, dict):
                text = item.get("text")
                if isinstance(text, str):
                    parts.append(text)
        return "\n".join(parts)
    return str(content or "")


def _message_tool_call_id(message: Any) -> str | None:
    """Return a tool message call id if present."""
    if isinstance(message, dict):
        value = message.get("tool_call_id") or message.get("call_id")
    else:
        value = getattr(message, "tool_call_id", None)
    return str(value) if value else None


def _message_tool_calls(message: Any) -> list[dict[str, Any]]:
    """Return tool calls from an assistant message."""
    calls = (
        message.get("tool_calls")
        if isinstance(message, dict)
        else getattr(message, "tool_calls", None)
    )
    return calls if isinstance(calls, list) else []


def _tool_call_to_input_item(tool_call: dict[str, Any]) -> dict[str, Any]:
    """Convert a LangChain tool call to a Codex function_call input item."""
    args = tool_call.get("args") or tool_call.get("arguments") or {}
    return {
        "type": "function_call",
        "call_id": str(tool_call.get("id") or ""),
        "name": str(tool_call.get("name") or ""),
        "arguments": json.dumps(args) if isinstance(args, dict) else str(args),
    }
