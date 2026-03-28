"""Shared fixtures and helpers for setup controller tests."""

from typing import Any
from unittest.mock import AsyncMock, MagicMock

from litestar.testing import TestClient


def setup_mock_providers(
    test_client: TestClient[Any],
) -> tuple[Any, Any]:
    """Wire up mock providers on the app state. Returns (app_state, original)."""
    mock_model = MagicMock()
    mock_model.id = "test-small-001"
    mock_model.alias = None
    mock_model.cost_per_1k_input = 0.01
    mock_model.cost_per_1k_output = 0.02
    mock_model.max_context = 200_000
    mock_model.estimated_latency_ms = 100
    mock_provider_config = MagicMock()
    mock_provider_config.models = (mock_model,)

    mock_mgmt = MagicMock()
    mock_mgmt.list_providers = AsyncMock(
        return_value={"test-provider": mock_provider_config},
    )

    app_state = test_client.app.state.app_state
    original = app_state._provider_management
    app_state._provider_management = mock_mgmt
    return app_state, original
