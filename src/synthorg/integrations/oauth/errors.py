"""OAuth-specific error re-exports for convenience."""

from synthorg.integrations.errors import (
    DeviceFlowTimeoutError,
    InvalidStateError,
    OAuthError,
    OAuthFlowError,
    PKCEValidationError,
    TokenExchangeFailedError,
    TokenRefreshFailedError,
)

__all__ = [
    "DeviceFlowTimeoutError",
    "InvalidStateError",
    "OAuthError",
    "OAuthFlowError",
    "PKCEValidationError",
    "TokenExchangeFailedError",
    "TokenRefreshFailedError",
]
