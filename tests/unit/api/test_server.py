"""Tests for the Uvicorn server runner."""

from unittest.mock import MagicMock, patch

import pytest

from synthorg.config.schema import RootConfig

pytestmark = pytest.mark.unit


class TestRunServerUvicornParams:
    """Verify that run_server passes correct params to uvicorn.run."""

    def test_access_log_disabled_and_log_config_none(self) -> None:
        """Uvicorn access log is disabled; log_config is None."""
        dummy_app = MagicMock()
        mock_run = MagicMock()
        with (
            patch(
                "synthorg.api.server.create_app",
                return_value=dummy_app,
            ),
            patch("synthorg.api.server.uvicorn.run", mock_run),
        ):
            from synthorg.api.server import run_server

            run_server(RootConfig(company_name="test-co"))

        mock_run.assert_called_once()
        call_kwargs = mock_run.call_args
        # access_log and log_config are keyword args to uvicorn.run.
        assert call_kwargs.kwargs["access_log"] is False
        assert call_kwargs.kwargs["log_config"] is None
        # The dummy app was passed as the first positional arg.
        assert call_kwargs.args[0] is dummy_app
