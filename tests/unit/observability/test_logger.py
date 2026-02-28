"""Tests for the get_logger convenience wrapper."""

import pytest

from ai_company.observability._logger import get_logger
from ai_company.observability.setup import configure_logging

pytestmark = pytest.mark.timeout(30)


@pytest.mark.unit
class TestGetLogger:
    """Tests for get_logger function."""

    def test_returns_usable_logger(self) -> None:
        configure_logging()
        logger = get_logger("test.module")
        assert hasattr(logger, "info")
        assert hasattr(logger, "debug")
        assert hasattr(logger, "warning")
        assert hasattr(logger, "error")

    def test_logger_name_bound(self) -> None:
        configure_logging()
        logger = get_logger("my.module")
        # The logger should be usable without errors
        assert logger is not None

    def test_initial_bindings_applied(self) -> None:
        configure_logging()
        logger = get_logger("test.bindings", service="api")
        assert logger is not None

    def test_different_names_return_different_loggers(self) -> None:
        configure_logging()
        logger_a = get_logger("module.a")
        logger_b = get_logger("module.b")
        # They should be distinct instances
        assert logger_a is not logger_b
