"""Tests for bootstrap_logging()."""

from unittest.mock import patch

import pytest

from ai_company.config.loader import bootstrap_logging
from ai_company.config.schema import RootConfig
from ai_company.observability.config import DEFAULT_SINKS, LogConfig

pytestmark = pytest.mark.timeout(30)


@pytest.mark.unit
class TestBootstrapLogging:
    def test_calls_configure_logging_with_none(self) -> None:
        with patch(
            "ai_company.observability.configure_logging",
        ) as mock_configure:
            bootstrap_logging(None)
        mock_configure.assert_called_once_with(None)

    def test_calls_configure_logging_with_config_logging(self) -> None:
        log_cfg = LogConfig(sinks=DEFAULT_SINKS)
        config = RootConfig(
            company_name="Test",
            logging=log_cfg,
        )
        with patch(
            "ai_company.observability.configure_logging",
        ) as mock_configure:
            bootstrap_logging(config)
        mock_configure.assert_called_once_with(log_cfg)

    def test_is_idempotent(self) -> None:
        with patch(
            "ai_company.observability.configure_logging",
        ) as mock_configure:
            bootstrap_logging(None)
            bootstrap_logging(None)
        assert mock_configure.call_count == 2
