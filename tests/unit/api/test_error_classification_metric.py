"""Tests for ``synthorg_api_error_classification_total`` emission.

``_build_response`` (in ``synthorg.api.exception_handlers``) fires
``record_api_error`` on every 4xx/5xx response it builds, so every
structured error out of the API surface increments the counter
partitioned by RFC 9457 category and HTTP status class.
"""

from types import SimpleNamespace
from typing import Any
from unittest.mock import MagicMock

import pytest

from synthorg.api import exception_handlers
from synthorg.api.errors import ErrorCategory, ErrorCode

pytestmark = pytest.mark.unit


def _fake_request() -> Any:
    """Build a minimal request-shaped object.

    ``_build_response`` calls ``_wants_problem_json(request)``, which
    inspects ``request.accept.best_match``; returning a match that is
    not the problem+json type keeps the code path on the envelope
    branch and avoids touching Litestar internals we don't care about
    for metric emission.
    """
    accept = SimpleNamespace(
        best_match=lambda _types: "application/json",
    )
    return SimpleNamespace(accept=accept)


def test_build_response_emits_api_error_metric_for_5xx(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    recorder = MagicMock()
    monkeypatch.setattr(exception_handlers, "record_api_error", recorder)

    exception_handlers._build_response(
        _fake_request(),
        detail="boom",
        error_code=ErrorCode.PROVIDER_ERROR,
        error_category=ErrorCategory.INTERNAL,
        status_code=500,
    )

    recorder.assert_called_once_with(category="internal", status_code=500)


def test_build_response_emits_api_error_metric_for_4xx(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    recorder = MagicMock()
    monkeypatch.setattr(exception_handlers, "record_api_error", recorder)

    exception_handlers._build_response(
        _fake_request(),
        detail="bad",
        error_code=ErrorCode.VALIDATION_ERROR,
        error_category=ErrorCategory.VALIDATION,
        status_code=422,
    )

    recorder.assert_called_once_with(category="validation", status_code=422)


def test_build_response_skips_metric_on_success(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Non-error (< 400) status codes must not touch the counter."""
    recorder = MagicMock()
    monkeypatch.setattr(exception_handlers, "record_api_error", recorder)

    exception_handlers._build_response(
        _fake_request(),
        detail="ok",
        error_code=ErrorCode.PROVIDER_ERROR,
        error_category=ErrorCategory.INTERNAL,
        status_code=200,
    )

    recorder.assert_not_called()
