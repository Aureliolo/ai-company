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
from .routing import (
    CostAwareStrategy,
    ManualStrategy,
    ModelResolutionError,
    ModelResolver,
    ModelRouter,
    NoAvailableModelError,
    ResolvedModel,
    RoleBasedStrategy,
    RoutingDecision,
    RoutingError,
    RoutingRequest,
    RoutingStrategy,
    SmartStrategy,
    UnknownStrategyError,
)

__all__ = [
    "AuthenticationError",
    "BaseCompletionProvider",
    "ChatMessage",
    "CompletionConfig",
    "CompletionProvider",
    "CompletionResponse",
    "ContentFilterError",
    "CostAwareStrategy",
    "DriverAlreadyRegisteredError",
    "DriverFactoryNotFoundError",
    "DriverNotRegisteredError",
    "FinishReason",
    "InvalidRequestError",
    "LiteLLMDriver",
    "ManualStrategy",
    "MessageRole",
    "ModelCapabilities",
    "ModelNotFoundError",
    "ModelResolutionError",
    "ModelResolver",
    "ModelRouter",
    "NoAvailableModelError",
    "ProviderConnectionError",
    "ProviderError",
    "ProviderInternalError",
    "ProviderRegistry",
    "ProviderTimeoutError",
    "RateLimitError",
    "ResolvedModel",
    "RoleBasedStrategy",
    "RoutingDecision",
    "RoutingError",
    "RoutingRequest",
    "RoutingStrategy",
    "SmartStrategy",
    "StreamChunk",
    "StreamEventType",
    "TokenUsage",
    "ToolCall",
    "ToolDefinition",
    "ToolResult",
    "UnknownStrategyError",
]
