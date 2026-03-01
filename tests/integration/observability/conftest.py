"""Test fixtures for observability integration tests."""

import logging
from typing import TYPE_CHECKING

import pytest
import structlog

if TYPE_CHECKING:
    from collections.abc import Iterator


def _clear_logging_state() -> None:
    """Clear structlog context and stdlib root handlers."""
    structlog.reset_defaults()
    structlog.contextvars.clear_contextvars()
    root = logging.getLogger()
    for handler in root.handlers[:]:
        root.removeHandler(handler)
        handler.close()
    root.setLevel(logging.WARNING)


@pytest.fixture(autouse=True)
def _reset_logging() -> Iterator[None]:
    """Reset structlog and stdlib logging state before and after each test.

    Prevents configure_logging() calls from leaking handlers across tests.
    """
    _clear_logging_state()
    yield
    _clear_logging_state()
