"""Unified provider interface for LLM completion.

Exports protocols, base classes, domain models, enums, and errors
for the provider layer.
"""

from .base import BaseCompletionProvider
from .capabilities import ModelCapabilities
from .enums import FinishReason, MessageRole, StreamEventType
from .errors import (
    AuthenticationError,
    ContentFilterError,
    InvalidRequestError,
    ModelNotFoundError,
    ProviderConnectionError,
    ProviderError,
    ProviderInternalError,
    ProviderTimeoutError,
    RateLimitError,
)
from .models import (
    ChatMessage,
    CompletionConfig,
    CompletionResponse,
    StreamChunk,
    TokenUsage,
    ToolCall,
    ToolDefinition,
    ToolResult,
)
from .protocol import CompletionProvider

__all__ = [
    "AuthenticationError",
    "BaseCompletionProvider",
    "ChatMessage",
    "CompletionConfig",
    "CompletionProvider",
    "CompletionResponse",
    "ContentFilterError",
    "FinishReason",
    "InvalidRequestError",
    "MessageRole",
    "ModelCapabilities",
    "ModelNotFoundError",
    "ProviderConnectionError",
    "ProviderError",
    "ProviderInternalError",
    "ProviderTimeoutError",
    "RateLimitError",
    "StreamChunk",
    "StreamEventType",
    "TokenUsage",
    "ToolCall",
    "ToolDefinition",
    "ToolResult",
]
