"""Pure mapping functions between domain models and LLM API dict formats.

These mappers convert between ``ai_company.providers.models`` and the
OpenAI-compatible dict format that LiteLLM (and most providers) consume.
Reusable by future native SDK drivers.
"""

import json
from typing import Any

from ai_company.providers.enums import FinishReason, MessageRole
from ai_company.providers.models import ChatMessage, ToolCall, ToolDefinition


def messages_to_dicts(messages: list[ChatMessage]) -> list[dict[str, object]]:
    """Convert a list of ``ChatMessage`` to OpenAI-compatible message dicts.

    Args:
        messages: Domain message objects.

    Returns:
        List of dicts ready for the ``messages`` parameter of
        ``litellm.acompletion``.
    """
    return [_message_to_dict(m) for m in messages]


def _message_to_dict(message: ChatMessage) -> dict[str, object]:
    """Convert a single ``ChatMessage`` to a dict."""
    result: dict[str, object] = {"role": message.role.value}

    match message.role:
        case MessageRole.TOOL:
            tr = message.tool_result
            result["content"] = tr.content if tr else ""
            result["tool_call_id"] = tr.tool_call_id if tr else ""
        case MessageRole.ASSISTANT:
            if message.content is not None:
                result["content"] = message.content
            if message.tool_calls:
                result["tool_calls"] = [
                    {
                        "id": tc.id,
                        "type": "function",
                        "function": {
                            "name": tc.name,
                            "arguments": json.dumps(tc.arguments),
                        },
                    }
                    for tc in message.tool_calls
                ]
        case _:
            result["content"] = message.content or ""

    return result


def tools_to_dicts(tools: list[ToolDefinition]) -> list[dict[str, object]]:
    """Convert a list of ``ToolDefinition`` to OpenAI-compatible tool dicts.

    Args:
        tools: Domain tool definitions.

    Returns:
        List of dicts ready for the ``tools`` parameter of
        ``litellm.acompletion``.
    """
    return [_tool_to_dict(t) for t in tools]


def _tool_to_dict(tool: ToolDefinition) -> dict[str, object]:
    """Convert a single ``ToolDefinition`` to an OpenAI tool dict."""
    return {
        "type": "function",
        "function": {
            "name": tool.name,
            "description": tool.description,
            "parameters": tool.parameters_schema,
        },
    }


_FINISH_REASON_MAP: dict[str | None, FinishReason] = {
    "stop": FinishReason.STOP,
    "length": FinishReason.MAX_TOKENS,
    "max_tokens": FinishReason.MAX_TOKENS,
    "tool_calls": FinishReason.TOOL_USE,
    "function_call": FinishReason.TOOL_USE,
    "content_filter": FinishReason.CONTENT_FILTER,
}


def map_finish_reason(reason: str | None) -> FinishReason:
    """Map a provider finish reason string to ``FinishReason``.

    Args:
        reason: Raw finish reason from the provider (e.g. ``"stop"``).

    Returns:
        The corresponding ``FinishReason`` enum member.  Unmapped values
        default to ``FinishReason.ERROR``.
    """
    return _FINISH_REASON_MAP.get(reason, FinishReason.ERROR)


def extract_tool_calls(raw: list[Any] | None) -> tuple[ToolCall, ...]:
    """Extract ``ToolCall`` objects from raw OpenAI-format tool call dicts.

    Handles both parsed dicts and objects with attribute access (as
    returned by LiteLLM response objects).

    Args:
        raw: List of tool call dicts/objects from the provider response,
            or ``None`` if no tool calls.

    Returns:
        Tuple of ``ToolCall`` domain objects.
    """
    if not raw:
        return ()

    calls: list[ToolCall] = []
    for item in raw:
        call_id = _get(item, "id", "")
        func = _get(item, "function", None)
        if func is None:
            continue
        name = _get(func, "name", "")
        raw_args = _get(func, "arguments", "{}")
        arguments = _parse_arguments(raw_args)
        if call_id and name:
            calls.append(ToolCall(id=call_id, name=name, arguments=arguments))

    return tuple(calls)


def _get(obj: Any, key: str, default: Any) -> Any:
    """Get a value from a dict or object attribute."""
    if isinstance(obj, dict):
        return obj.get(key, default)
    return getattr(obj, key, default)


def _parse_arguments(raw: str | dict[str, Any] | Any) -> dict[str, Any]:
    """Parse tool call arguments from string or dict form.

    Args:
        raw: JSON string or pre-parsed dict.

    Returns:
        Parsed arguments dict.  Returns empty dict on parse failure.
    """
    if isinstance(raw, dict):
        return raw
    if isinstance(raw, str):
        try:
            parsed = json.loads(raw)
        except json.JSONDecodeError, ValueError:
            return {}
        if isinstance(parsed, dict):
            return parsed
        return {}
    return {}
