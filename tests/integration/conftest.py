"""Integration test configuration and fixtures."""

import os

import pytest


@pytest.fixture(autouse=True)
def _skip_in_ci() -> None:
    """Skip integration tests in CI unless RUN_INTEGRATION_TESTS is set."""
    if os.environ.get("CI") and not os.environ.get("RUN_INTEGRATION_TESTS"):
        pytest.skip("Integration tests disabled in CI (set RUN_INTEGRATION_TESTS=1)")
