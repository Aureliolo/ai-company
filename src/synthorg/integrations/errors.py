"""Error hierarchy for the integrations subsystem.

All integration errors inherit from ``IntegrationError`` so callers
can catch the entire family with a single except clause.
"""


class IntegrationError(Exception):
    """Base exception for all integration operations."""


# -- Connection errors ---------------------------------------------------


class ConnectionNotFoundError(IntegrationError):
    """A connection with the given name does not exist."""


class DuplicateConnectionError(IntegrationError):
    """A connection with the given name already exists."""


class InvalidConnectionAuthError(IntegrationError):
    """Connection authentication configuration is invalid."""


class ConnectionHealthError(IntegrationError):
    """A health check operation failed."""


# -- Secret errors -------------------------------------------------------


class SecretRetrievalError(IntegrationError):
    """A secret could not be retrieved from the backend."""


class SecretStorageError(IntegrationError):
    """A secret could not be stored in the backend."""


class SecretRotationError(IntegrationError):
    """A secret rotation operation failed."""


class MasterKeyError(IntegrationError):
    """The master encryption key is missing or invalid."""


# -- OAuth errors --------------------------------------------------------


class OAuthError(IntegrationError):
    """Base exception for OAuth flow failures."""


class OAuthFlowError(OAuthError):
    """An OAuth flow could not be initiated or completed."""


class TokenExchangeFailedError(OAuthError):
    """The authorization code could not be exchanged for tokens."""


class TokenRefreshFailedError(OAuthError):
    """A token refresh attempt failed."""


class InvalidStateError(OAuthError):
    """The OAuth state parameter is invalid, expired, or already used."""


class DeviceFlowTimeoutError(OAuthError):
    """The device flow polling timed out before user authorization."""


class PKCEValidationError(OAuthError):
    """PKCE code verifier or challenge validation failed."""


# -- Webhook errors ------------------------------------------------------


class WebhookError(IntegrationError):
    """Base exception for webhook operations."""


class SignatureVerificationFailedError(WebhookError):
    """The webhook signature did not match."""


class ReplayAttackDetectedError(WebhookError):
    """A replayed webhook request was detected (nonce or timestamp)."""


class InvalidWebhookPayloadError(WebhookError):
    """The webhook payload could not be parsed."""


class WebhookProcessingError(WebhookError):
    """An error occurred while processing a verified webhook event."""


# -- Rate limiting errors ------------------------------------------------


class ConnectionRateLimitError(IntegrationError):
    """The connection's rate limit has been exceeded."""


# -- Tunnel errors -------------------------------------------------------


class TunnelError(IntegrationError):
    """An error occurred starting or operating the tunnel."""


# -- MCP catalog errors --------------------------------------------------


class CatalogEntryNotFoundError(IntegrationError):
    """A catalog entry with the given ID does not exist."""


class MCPInstallError(IntegrationError):
    """An MCP server installation failed."""
