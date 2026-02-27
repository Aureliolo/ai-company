"""Root test configuration and shared fixtures."""

import pytest


@pytest.fixture(params=["asyncio"])
def anyio_backend(request: pytest.FixtureRequest) -> str:
    """Configure async backend for anyio-based tests."""
    return str(request.param)
