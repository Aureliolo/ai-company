"""Test fixtures for observability integration tests."""

from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    from collections.abc import Iterator

from tests.conftest import clear_logging_state


@pytest.fixture(autouse=True)
def _reset_logging() -> Iterator[None]:
    """Reset structlog and stdlib logging state before and after each test.

    Prevents configure_logging() calls from leaking handlers across tests.
    """
    clear_logging_state()
    yield
    clear_logging_state()
