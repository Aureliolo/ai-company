"""Unified provider interface for LLM completion.

Exports protocols, base classes, domain models, enums, errors,
driver implementations, and the provider registry.
"""

from .base import BaseCompletionProvider
from .capabilities import ModelCapabilities
from .drivers import LiteLLMDriver
from .enums import FinishReason, MessageRole, StreamEventType
from .errors import (
    AuthenticationError,
    ContentFilterError,
    DriverAlreadyRegisteredError,
    DriverFactoryNotFoundError,
    DriverNotRegisteredError,
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
from .registry import ProviderRegistry

__all__ = [
    "AuthenticationError",
    "BaseCompletionProvider",
    "ChatMessage",
    "CompletionConfig",
    "CompletionProvider",
    "CompletionResponse",
    "ContentFilterError",
    "DriverAlreadyRegisteredError",
    "DriverFactoryNotFoundError",
    "DriverNotRegisteredError",
    "FinishReason",
    "InvalidRequestError",
    "LiteLLMDriver",
    "MessageRole",
    "ModelCapabilities",
    "ModelNotFoundError",
    "ProviderConnectionError",
    "ProviderError",
    "ProviderInternalError",
    "ProviderRegistry",
    "ProviderTimeoutError",
    "RateLimitError",
    "StreamChunk",
    "StreamEventType",
    "TokenUsage",
    "ToolCall",
    "ToolDefinition",
    "ToolResult",
]
