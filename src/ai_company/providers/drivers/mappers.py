"""Pure mapping functions between domain models and LLM API dict formats.

These mappers convert between ``ai_company.providers.models`` and the
OpenAI-compatible dict format that LiteLLM (and most providers) consume.
Reusable by future native SDK drivers.
"""

import copy
import json
import logging
from typing import Any

from ai_company.providers.enums import FinishReason, MessageRole
from ai_company.providers.models import ChatMessage, ToolCall, ToolDefinition

_logger = logging.getLogger(__name__)


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
            "parameters": copy.deepcopy(tool.parameters_schema),
        },
    }


# OpenAI uses "function_call" (legacy) and "tool_calls" (current);
# Anthropic uses "end_turn", "stop_sequence", and "tool_use" natively.
# LiteLLM normalises most responses but some pass through raw.
_FINISH_REASON_MAP: dict[str | None, FinishReason] = {
    "stop": FinishReason.STOP,
    "end_turn": FinishReason.STOP,
    "stop_sequence": FinishReason.STOP,
    "length": FinishReason.MAX_TOKENS,
    "max_tokens": FinishReason.MAX_TOKENS,
    "tool_calls": FinishReason.TOOL_USE,
    "function_call": FinishReason.TOOL_USE,
    "tool_use": FinishReason.TOOL_USE,
    "content_filter": FinishReason.CONTENT_FILTER,
}


def map_finish_reason(reason: str | None) -> FinishReason:
    """Map a provider finish reason string to ``FinishReason``.

    Args:
        reason: Raw finish reason from the provider (e.g. ``"stop"``),
            or ``None`` if no finish reason was provided (common in
            streaming intermediate chunks).

    Returns:
        The corresponding ``FinishReason`` enum member.  Unmapped values
        (including ``None``) default to ``FinishReason.ERROR``.
    """
    result = _FINISH_REASON_MAP.get(reason)
    if result is None:
        if reason is not None:
            _logger.warning(
                "Unknown finish reason %r, defaulting to ERROR",
                reason,
            )
        return FinishReason.ERROR
    return result


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
            _logger.warning(
                "Tool call item missing 'function' field, skipping: %r",
                item,
            )
            continue
        name = _get(func, "name", "")
        raw_args = _get(func, "arguments", "{}")
        arguments = _parse_arguments(raw_args)
        if call_id and name:
            calls.append(ToolCall(id=call_id, name=name, arguments=arguments))
        else:
            _logger.warning(
                "Incomplete tool call (id=%r, name=%r), skipping",
                call_id,
                name,
            )

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
        return dict(raw)
    if isinstance(raw, str):
        try:
            parsed = json.loads(raw)
        except json.JSONDecodeError, ValueError:
            _logger.warning(
                "Failed to parse tool call arguments: %r",
                raw[:200],
            )
            return {}
        if isinstance(parsed, dict):
            return dict(parsed)
        return {}
    return {}
