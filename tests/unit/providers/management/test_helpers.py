"""Tests for provider management helper functions."""

from datetime import UTC, datetime
from typing import Any
from unittest.mock import patch

import pytest

from synthorg.api.dto import UpdateProviderRequest
from synthorg.config.schema import ProviderConfig, ProviderModelConfig
from synthorg.core.resilience_config import RateLimiterConfig, RetryConfig
from synthorg.providers.enums import AuthType
from synthorg.providers.management._helpers import (
    _apply_credential_updates,
    apply_update,
    build_discovery_headers,
)


def _make_config(
    *,
    auth_type: AuthType = AuthType.API_KEY,
    api_key: str | None = None,
    base_url: str | None = None,
    **kwargs: Any,
) -> ProviderConfig:
    """Build a ProviderConfig with sensible defaults for testing."""
    return ProviderConfig(
        driver="litellm",
        auth_type=auth_type,
        api_key=api_key,
        base_url=base_url,
        models=(
            ProviderModelConfig(
                id="test-model-001",
                alias="medium",
            ),
        ),
        retry=RetryConfig(max_retries=0),
        rate_limiter=RateLimiterConfig(),
        **kwargs,
    )


@pytest.mark.unit
class TestBuildDiscoveryHeaders:
    def test_subscription_returns_bearer(self) -> None:
        """Subscription auth with token returns Authorization Bearer header."""
        config = _make_config(
            auth_type=AuthType.SUBSCRIPTION,
            subscription_token="test-subscription-token",
            tos_accepted_at=datetime(2026, 1, 1, tzinfo=UTC),
        )
        headers = build_discovery_headers(config)
        assert headers == {"Authorization": "Bearer test-subscription-token"}

    def test_subscription_no_token_returns_none(self) -> None:
        """Subscription auth without a token returns None."""
        config = _make_config(
            auth_type=AuthType.SUBSCRIPTION,
            subscription_token="test-subscription-token",
            tos_accepted_at=datetime(2026, 1, 1, tzinfo=UTC),
        )
        # Bypass frozen model to simulate a cleared token
        object.__setattr__(config, "subscription_token", None)
        headers = build_discovery_headers(config)
        assert headers is None


@pytest.mark.unit
class TestApplyCredentialUpdates:
    def test_switch_from_subscription_to_api_key_clears_fields(self) -> None:
        """Switching from subscription to api_key clears token and tos."""
        updates: dict[str, Any] = {}
        request = UpdateProviderRequest(
            auth_type=AuthType.API_KEY,
            api_key="sk-new",
        )
        _apply_credential_updates(updates, request, AuthType.API_KEY)
        assert updates["api_key"] == "sk-new"
        assert updates["subscription_token"] is None
        assert updates["tos_accepted_at"] is None

    def test_switch_to_subscription_sets_token(self) -> None:
        """Switching to subscription sets subscription_token when provided."""
        updates: dict[str, Any] = {}
        request = UpdateProviderRequest(
            subscription_token="test-subscription-token",
        )
        _apply_credential_updates(updates, request, AuthType.SUBSCRIPTION)
        assert updates["subscription_token"] == "test-subscription-token"

    def test_tos_accepted_stamps_timestamp(self) -> None:
        """Setting tos_accepted=True stamps tos_accepted_at."""
        updates: dict[str, Any] = {}
        request = UpdateProviderRequest(tos_accepted=True)
        frozen = datetime(2026, 3, 27, 12, 0, 0, tzinfo=UTC)
        with patch(
            "synthorg.providers.management._helpers.datetime",
        ) as mock_dt:
            mock_dt.now.return_value = frozen
            mock_dt.side_effect = datetime
            _apply_credential_updates(updates, request, AuthType.SUBSCRIPTION)
        assert updates["tos_accepted_at"] == frozen

    def test_clear_subscription_token(self) -> None:
        """Setting clear_subscription_token=True clears the token."""
        updates: dict[str, Any] = {}
        request = UpdateProviderRequest(clear_subscription_token=True)
        _apply_credential_updates(updates, request, AuthType.SUBSCRIPTION)
        assert updates["subscription_token"] is None


@pytest.mark.unit
class TestApplyUpdateAuthTransitions:
    """Integration-level tests for apply_update subscription transitions."""

    def test_switch_from_subscription_to_api_key_clears_owned_fields(
        self,
    ) -> None:
        """AUTH_OWNED_FIELDS cleanup clears subscription fields on switch."""
        existing = _make_config(
            auth_type=AuthType.SUBSCRIPTION,
            subscription_token="test-subscription-token",
            tos_accepted_at=datetime(2026, 1, 1, tzinfo=UTC),
        )
        request = UpdateProviderRequest(
            auth_type=AuthType.API_KEY,
            api_key="sk-new-key",
        )
        result = apply_update(existing, request)
        assert result.auth_type == AuthType.API_KEY
        assert result.api_key == "sk-new-key"
        assert result.subscription_token is None
        assert result.tos_accepted_at is None

    def test_switch_from_api_key_to_subscription_clears_api_key(
        self,
    ) -> None:
        """Switching to subscription clears api_key and sets token."""
        existing = _make_config(
            auth_type=AuthType.API_KEY,
            api_key="sk-old",
        )
        request = UpdateProviderRequest(
            auth_type=AuthType.SUBSCRIPTION,
            subscription_token="test-subscription-token",
            tos_accepted=True,
        )
        result = apply_update(existing, request)
        assert result.auth_type == AuthType.SUBSCRIPTION
        assert result.api_key is None
        assert result.subscription_token == "test-subscription-token"
        assert result.tos_accepted_at is not None
