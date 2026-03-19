"""Tests for the Uvicorn server runner."""

from unittest.mock import MagicMock, patch

import pytest

from synthorg.config.schema import RootConfig


@pytest.mark.unit
class TestRunServerUvicornParams:
    """Verify that run_server passes correct params to uvicorn.run."""

    def test_access_log_disabled_and_log_config_none(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Uvicorn access log is disabled; log_config is None."""
        # Prevent create_app from actually bootstrapping logging.
        monkeypatch.setattr(
            "synthorg.api.app._bootstrap_app_logging",
            lambda _config: None,
        )
        mock_run = MagicMock()
        with patch("synthorg.api.server.uvicorn.run", mock_run):
            from synthorg.api.server import run_server

            run_server(RootConfig(company_name="test-co"))

        mock_run.assert_called_once()
        kwargs = mock_run.call_args.kwargs
        assert kwargs["access_log"] is False
        assert kwargs["log_config"] is None
