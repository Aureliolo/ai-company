"""Tests for RFC 9457 content negotiation (application/problem+json)."""

from typing import Any
from unittest.mock import MagicMock

import pytest
from litestar import Litestar, get
from litestar.exceptions import HTTPException, ValidationException
from litestar.testing import TestClient

from synthorg.api.errors import (
    ErrorCategory,
    ErrorCode,
    ServiceUnavailableError,
    UnauthorizedError,
    category_title,
    category_type_uri,
)
from synthorg.api.exception_handlers import (
    EXCEPTION_HANDLERS,
    _wants_problem_json,
)
from synthorg.persistence.errors import (
    DuplicateRecordError,
    RecordNotFoundError,
)

pytestmark = pytest.mark.unit

_PROBLEM_JSON = "application/problem+json"


def _make_app(handler: Any) -> Litestar:
    return Litestar(
        route_handlers=[handler],
        exception_handlers=EXCEPTION_HANDLERS,  # type: ignore[arg-type]
    )


class TestContentNegotiation:
    """Tests for application/problem+json content negotiation."""

    def _assert_problem_detail(  # noqa: PLR0913
        self,
        body: dict[str, Any],
        *,
        status: int,
        error_code: int,
        error_category: str,
        retryable: bool,
        retry_after: int | None = None,
    ) -> None:
        """Assert bare RFC 9457 ProblemDetail structure."""
        # Must have RFC 9457 fields
        assert body["status"] == status
        assert body["error_code"] == error_code
        assert body["error_category"] == error_category
        assert body["retryable"] is retryable
        assert body["retry_after"] == retry_after
        assert isinstance(body["title"], str)
        assert len(body["title"]) > 0
        assert isinstance(body["type"], str)
        assert body["type"].startswith("https://")
        assert isinstance(body["detail"], str)
        assert len(body["detail"]) > 0
        assert isinstance(body["instance"], str)
        assert len(body["instance"]) > 0
        # Must NOT have envelope keys
        assert "data" not in body
        assert "error" not in body
        assert "success" not in body
        assert "error_detail" not in body

    def test_problem_json_for_not_found(self) -> None:
        """Accept: application/problem+json returns bare RFC 9457 body."""

        @get("/test")
        async def handler() -> None:
            msg = "gone"
            raise RecordNotFoundError(msg)

        with TestClient(_make_app(handler)) as client:
            resp = client.get(
                "/test",
                headers={"Accept": _PROBLEM_JSON},
            )
            assert resp.status_code == 404
            assert _PROBLEM_JSON in resp.headers.get("content-type", "")
            body = resp.json()
            self._assert_problem_detail(
                body,
                status=404,
                error_code=ErrorCode.RECORD_NOT_FOUND,
                error_category=ErrorCategory.NOT_FOUND,
                retryable=False,
            )
            assert body["detail"] == "Resource not found"
            assert body["title"] == category_title(ErrorCategory.NOT_FOUND)
            assert body["type"] == category_type_uri(ErrorCategory.NOT_FOUND)

    def test_problem_json_for_auth_error(self) -> None:
        @get("/test")
        async def handler() -> None:
            msg = "bad token"
            raise UnauthorizedError(msg)

        with TestClient(_make_app(handler)) as client:
            resp = client.get(
                "/test",
                headers={"Accept": _PROBLEM_JSON},
            )
            assert resp.status_code == 401
            assert _PROBLEM_JSON in resp.headers.get("content-type", "")
            body = resp.json()
            self._assert_problem_detail(
                body,
                status=401,
                error_code=ErrorCode.UNAUTHORIZED,
                error_category=ErrorCategory.AUTH,
                retryable=False,
            )

    def test_problem_json_for_conflict(self) -> None:
        @get("/test")
        async def handler() -> None:
            msg = "already exists"
            raise DuplicateRecordError(msg)

        with TestClient(_make_app(handler)) as client:
            resp = client.get(
                "/test",
                headers={"Accept": _PROBLEM_JSON},
            )
            assert resp.status_code == 409
            assert _PROBLEM_JSON in resp.headers.get("content-type", "")
            body = resp.json()
            self._assert_problem_detail(
                body,
                status=409,
                error_code=ErrorCode.DUPLICATE_RECORD,
                error_category=ErrorCategory.CONFLICT,
                retryable=False,
            )

    def test_problem_json_for_validation_error(self) -> None:
        @get("/test")
        async def handler() -> None:
            raise ValidationException

        with TestClient(_make_app(handler)) as client:
            resp = client.get(
                "/test",
                headers={"Accept": _PROBLEM_JSON},
            )
            assert resp.status_code == 400
            assert _PROBLEM_JSON in resp.headers.get("content-type", "")
            body = resp.json()
            self._assert_problem_detail(
                body,
                status=400,
                error_code=ErrorCode.REQUEST_VALIDATION_ERROR,
                error_category=ErrorCategory.VALIDATION,
                retryable=False,
            )

    def test_problem_json_for_retryable_error(self) -> None:
        """Retryable error includes retry metadata in problem+json."""

        @get("/test")
        async def handler() -> None:
            raise ServiceUnavailableError

        with TestClient(_make_app(handler)) as client:
            resp = client.get(
                "/test",
                headers={"Accept": _PROBLEM_JSON},
            )
            assert resp.status_code == 503
            body = resp.json()
            self._assert_problem_detail(
                body,
                status=503,
                error_code=ErrorCode.SERVICE_UNAVAILABLE,
                error_category=ErrorCategory.INTERNAL,
                retryable=True,
            )

    def test_problem_json_5xx_scrubs_detail(self) -> None:
        """5xx problem+json responses scrub internal details."""

        @get("/test")
        async def handler() -> None:
            msg = "Connection pool exhausted: 10.0.0.5:5432"
            raise ServiceUnavailableError(msg)

        with TestClient(_make_app(handler)) as client:
            resp = client.get(
                "/test",
                headers={"Accept": _PROBLEM_JSON},
            )
            assert resp.status_code == 503
            body = resp.json()
            assert body["detail"] == "Service unavailable"
            assert "10.0.0.5" not in body["detail"]

    def test_problem_json_for_unexpected_error(self) -> None:
        @get("/test")
        async def handler() -> None:
            msg = "boom"
            raise RuntimeError(msg)

        with TestClient(_make_app(handler)) as client:
            resp = client.get(
                "/test",
                headers={"Accept": _PROBLEM_JSON},
            )
            assert resp.status_code == 500
            assert _PROBLEM_JSON in resp.headers.get("content-type", "")
            body = resp.json()
            self._assert_problem_detail(
                body,
                status=500,
                error_code=ErrorCode.INTERNAL_ERROR,
                error_category=ErrorCategory.INTERNAL,
                retryable=False,
            )

    def test_problem_json_for_http_exception_headers(self) -> None:
        """HTTPException safe headers pass through in problem+json."""

        @get("/test")
        async def handler() -> None:
            raise HTTPException(
                status_code=429,
                detail="Slow down",
                headers={"Retry-After": "60", "X-Internal": "secret"},
            )

        with TestClient(_make_app(handler)) as client:
            resp = client.get(
                "/test",
                headers={"Accept": _PROBLEM_JSON},
            )
            assert resp.status_code == 429
            assert _PROBLEM_JSON in resp.headers.get("content-type", "")
            assert resp.headers.get("retry-after") == "60"
            assert "x-internal" not in resp.headers

    def test_default_accept_returns_envelope(self) -> None:
        """No Accept header returns the envelope format."""

        @get("/test")
        async def handler() -> None:
            msg = "gone"
            raise RecordNotFoundError(msg)

        with TestClient(_make_app(handler)) as client:
            resp = client.get("/test")
            assert resp.status_code == 404
            body = resp.json()
            assert "success" in body
            assert "error" in body
            assert "error_detail" in body

    def test_accept_json_returns_envelope(self) -> None:
        """Accept: application/json returns the envelope format."""

        @get("/test")
        async def handler() -> None:
            msg = "gone"
            raise RecordNotFoundError(msg)

        with TestClient(_make_app(handler)) as client:
            resp = client.get(
                "/test",
                headers={"Accept": "application/json"},
            )
            assert resp.status_code == 404
            body = resp.json()
            assert "success" in body
            assert "error" in body
            assert "error_detail" in body

    def test_accept_wildcard_returns_envelope(self) -> None:
        """Accept: */* returns the envelope format."""

        @get("/test")
        async def handler() -> None:
            msg = "gone"
            raise RecordNotFoundError(msg)

        with TestClient(_make_app(handler)) as client:
            resp = client.get(
                "/test",
                headers={"Accept": "*/*"},
            )
            assert resp.status_code == 404
            body = resp.json()
            assert "success" in body
            assert "error_detail" in body

    def test_problem_json_preferred_over_json(self) -> None:
        """problem+json preferred when listed with higher quality."""

        @get("/test")
        async def handler() -> None:
            msg = "gone"
            raise RecordNotFoundError(msg)

        with TestClient(_make_app(handler)) as client:
            resp = client.get(
                "/test",
                headers={
                    "Accept": "application/problem+json, application/json;q=0.9",
                },
            )
            assert resp.status_code == 404
            assert _PROBLEM_JSON in resp.headers.get("content-type", "")
            body = resp.json()
            assert "status" in body
            assert "success" not in body


class TestWantsProblemJson:
    """Direct unit tests for _wants_problem_json helper."""

    def test_returns_true_for_problem_json(self) -> None:
        request = MagicMock()
        request.accept.best_match.return_value = _PROBLEM_JSON
        assert _wants_problem_json(request) is True

    def test_returns_false_for_json(self) -> None:
        request = MagicMock()
        request.accept.best_match.return_value = "application/json"
        assert _wants_problem_json(request) is False

    def test_returns_false_for_none(self) -> None:
        request = MagicMock()
        request.accept.best_match.return_value = None
        assert _wants_problem_json(request) is False

    def test_returns_false_on_exception(self) -> None:
        """Defensive: returns False if Accept parsing raises."""
        request = MagicMock()
        request.accept.best_match.side_effect = RuntimeError("broken")
        assert _wants_problem_json(request) is False
