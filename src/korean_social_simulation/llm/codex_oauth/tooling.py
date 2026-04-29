"""Tool schema helpers for the ChatGPT/Codex OAuth backend."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

from langchain_core.utils.function_calling import convert_to_openai_function


def _as_dict(value: object) -> dict[str, Any] | None:
    """Return a plain dict for mapping values."""
    if isinstance(value, dict):
        return value
    if isinstance(value, Mapping):
        return dict(value)
    return None


def convert_tools(tools: Sequence[Any]) -> list[dict[str, Any]]:
    """Convert tool-like objects into Codex Responses-style function tools."""
    converted: list[dict[str, Any]] = []
    for tool in tools:
        tool_dict = _as_dict(tool)
        if tool_dict is not None:
            if tool_dict.get("type") == "function" and isinstance(
                tool_dict.get("function"), dict
            ):
                converted.append({"type": "function", **tool_dict["function"]})
                continue

            if tool_dict.get("type") == "function" and isinstance(
                tool_dict.get("name"), str
            ):
                converted.append(tool_dict)
                continue

            if isinstance(tool_dict.get("name"), str) and isinstance(
                tool_dict.get("parameters"), dict
            ):
                converted.append({"type": "function", **tool_dict})
                continue

        function = convert_to_openai_function(tool)
        if not isinstance(function, dict):
            raise TypeError("Tool conversion produced a non-dict schema")
        converted.append({"type": "function", **function})

    return converted


def normalize_tool_choice(tool_choice: Any | None) -> Any | None:
    """Normalize LangChain/OpenAI-style tool_choice for the Codex backend."""
    if tool_choice is None:
        return None

    choice_dict = _as_dict(tool_choice)
    if choice_dict is not None:
        if choice_dict.get("type") == "function" and isinstance(
            choice_dict.get("function"), dict
        ):
            name = choice_dict["function"].get("name")
            if isinstance(name, str) and name:
                return {"type": "function", "name": name}

        if choice_dict.get("type") == "function" and isinstance(
            choice_dict.get("name"), str
        ):
            return choice_dict

        return choice_dict

    if not isinstance(tool_choice, str):
        return tool_choice

    value = tool_choice.strip()
    lowered = value.lower()
    if lowered == "any":
        return "required"
    if lowered in {"auto", "none", "required"}:
        return lowered
    return {"type": "function", "name": value}
