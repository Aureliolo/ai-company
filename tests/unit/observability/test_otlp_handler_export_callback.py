"""Tests for the OTLP log handler's export callback hook (#1384).

The handler's ``set_export_callback`` lets startup wiring bridge
export outcomes into the Prometheus collector without the handler
depending on AppState.
"""

import logging
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from synthorg.observability.otlp_handler import OtlpHandler

pytestmark = pytest.mark.unit


def _make_record(level: int = logging.INFO, message: str = "x") -> logging.LogRecord:
    return logging.LogRecord(
        name="test",
        level=level,
        pathname=__file__,
        lineno=1,
        msg=message,
        args=None,
        exc_info=None,
    )


def test_export_callback_fires_on_success() -> None:
    handler = OtlpHandler(
        endpoint="http://example.invalid:4318",
        _start_flusher=False,
    )
    callback = MagicMock()
    handler.set_export_callback(callback)

    with patch("urllib.request.urlopen") as mock_open:
        mock_open.return_value.__enter__ = MagicMock(return_value=None)
        mock_open.return_value.__exit__ = MagicMock(return_value=None)
        handler._export_batch([_make_record()])

    callback.assert_called_once_with("success", 0)


def test_export_callback_fires_on_failure() -> None:
    handler = OtlpHandler(
        endpoint="http://example.invalid:4318",
        _start_flusher=False,
    )
    callback = MagicMock()
    handler.set_export_callback(callback)

    with patch("urllib.request.urlopen", side_effect=OSError("boom")):
        handler._export_batch([_make_record()])

    callback.assert_called_once_with("failure", 1)


def test_export_callback_exceptions_are_swallowed(
    capsys: pytest.CaptureFixture[str],
) -> None:
    handler = OtlpHandler(
        endpoint="http://example.invalid:4318",
        _start_flusher=False,
    )

    def _bad_callback(_outcome: str, _dropped: int) -> None:
        error_msg = "callback bug"
        raise RuntimeError(error_msg)

    handler.set_export_callback(_bad_callback)

    with patch("urllib.request.urlopen") as mock_open:
        mock_open.return_value.__enter__ = MagicMock(return_value=None)
        mock_open.return_value.__exit__ = MagicMock(return_value=None)
        handler._export_batch([_make_record()])

    captured = capsys.readouterr()
    assert "otlp export callback raised" in captured.err


def test_no_callback_is_noop() -> None:
    handler = OtlpHandler(
        endpoint="http://example.invalid:4318",
        _start_flusher=False,
    )
    # No callback registered -- export should still run cleanly.
    with patch("urllib.request.urlopen") as mock_open:
        mock_open.return_value.__enter__ = MagicMock(return_value=None)
        mock_open.return_value.__exit__ = MagicMock(return_value=None)
        handler._export_batch([_make_record()])
    # No assertion needed -- just verifies no exception raised.
    _: Any = None
