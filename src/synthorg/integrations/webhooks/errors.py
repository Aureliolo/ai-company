"""Webhook-specific error re-exports for convenience."""

from synthorg.integrations.errors import (
    InvalidWebhookPayloadError,
    ReplayAttackDetectedError,
    SignatureVerificationFailedError,
    WebhookError,
    WebhookProcessingError,
)

__all__ = [
    "InvalidWebhookPayloadError",
    "ReplayAttackDetectedError",
    "SignatureVerificationFailedError",
    "WebhookError",
    "WebhookProcessingError",
]
