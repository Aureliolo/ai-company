"""Integration test configuration and fixtures."""

import os

import pytest


@pytest.fixture(autouse=True)
def _skip_in_ci(request: pytest.FixtureRequest) -> None:
    """Skip integration tests in CI unless explicitly enabled."""
    if os.environ.get("CI") and not os.environ.get("RUN_INTEGRATION_TESTS"):
        pytest.skip("Integration tests disabled in CI (set RUN_INTEGRATION_TESTS=1)")
