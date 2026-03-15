"""Tests for exception handlers with RFC 9457 structured error responses."""

import re
from typing import Any
from unittest.mock import MagicMock, patch

import pytest
import structlog
from litestar import Litestar, get, post
from litestar.exceptions import (
    HTTPException,
    NotAuthorizedException,
    PermissionDeniedException,
    ValidationException,
)
from litestar.testing import TestClient

from synthorg.api.errors import (
    ApiError,
    ApiValidationError,
    ConflictError,
    ErrorCategory,
    ErrorCode,
    ForbiddenError,
    NotFoundError,
    ServiceUnavailableError,
    UnauthorizedError,
)
from synthorg.api.exception_handlers import (
    EXCEPTION_HANDLERS,
    _build_error_response,
    _category_for_status,
    _get_instance_id,
    handle_http_exception,
    handle_unexpected,
)
from synthorg.persistence.errors import (
    DuplicateRecordError,
    PersistenceError,
    RecordNotFoundError,
)

pytestmark = pytest.mark.unit

_UUID_RE = re.compile(
    r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$",
)


def _make_app(handler: Any) -> Litestar:
    return Litestar(
        route_handlers=[handler],
        exception_handlers=EXCEPTION_HANDLERS,  # type: ignore[arg-type]
    )


def _assert_error_detail(
    body: dict[str, Any],
    *,
    error_code: int,
    error_category: str,
    retryable: bool,
    retry_after: int | None = None,
) -> None:
    """Assert common error_detail structure."""
    detail = body["error_detail"]
    assert detail is not None
    assert detail["error_code"] == error_code
    assert detail["error_category"] == error_category
    assert detail["retryable"] is retryable
    assert detail["retry_after"] == retry_after
    assert detail["message"] == body["error"]
    # instance should be a non-empty string (UUID format when middleware runs)
    assert isinstance(detail["instance"], str)
    assert len(detail["instance"]) > 0


class TestExceptionHandlers:
    def test_record_not_found_maps_to_404(self) -> None:
        @get("/test")
        async def handler() -> None:
            msg = "gone"
            raise RecordNotFoundError(msg)

        with TestClient(_make_app(handler)) as client:
            resp = client.get("/test")
            assert resp.status_code == 404
            body = resp.json()
            assert body["success"] is False
            # Error message is scrubbed — internal details not exposed.
            assert body["error"] == "Resource not found"
            _assert_error_detail(
                body,
                error_code=ErrorCode.RECORD_NOT_FOUND,
                error_category=ErrorCategory.NOT_FOUND,
                retryable=False,
            )

    def test_duplicate_record_maps_to_409(self) -> None:
        @get("/test")
        async def handler() -> None:
            msg = "exists"
            raise DuplicateRecordError(msg)

        with TestClient(_make_app(handler)) as client:
            resp = client.get("/test")
            assert resp.status_code == 409
            body = resp.json()
            assert body["error"] == "Resource already exists"
            _assert_error_detail(
                body,
                error_code=ErrorCode.DUPLICATE_RECORD,
                error_category=ErrorCategory.CONFLICT,
                retryable=False,
            )

    def test_persistence_error_maps_to_500(self) -> None:
        @get("/test")
        async def handler() -> None:
            msg = "db fail"
            raise PersistenceError(msg)

        with TestClient(_make_app(handler)) as client:
            resp = client.get("/test")
            assert resp.status_code == 500
            body = resp.json()
            assert body["success"] is False
            assert body["error"] == "Internal server error"
            _assert_error_detail(
                body,
                error_code=ErrorCode.INTERNAL_ERROR,
                error_category=ErrorCategory.INTERNAL,
                retryable=False,
            )

    def test_api_not_found_error_maps_to_404(self) -> None:
        @get("/test")
        async def handler() -> None:
            msg = "nope"
            raise NotFoundError(msg)

        with TestClient(_make_app(handler)) as client:
            resp = client.get("/test")
            assert resp.status_code == 404
            body = resp.json()
            # 4xx errors return the actual exception message
            assert body["error"] == "nope"
            _assert_error_detail(
                body,
                error_code=ErrorCode.RESOURCE_NOT_FOUND,
                error_category=ErrorCategory.NOT_FOUND,
                retryable=False,
            )

    def test_api_conflict_error_maps_to_409(self) -> None:
        @get("/test")
        async def handler() -> None:
            msg = "conflict"
            raise ConflictError(msg)

        with TestClient(_make_app(handler)) as client:
            resp = client.get("/test")
            assert resp.status_code == 409
            body = resp.json()
            assert body["error"] == "conflict"
            _assert_error_detail(
                body,
                error_code=ErrorCode.RESOURCE_CONFLICT,
                error_category=ErrorCategory.CONFLICT,
                retryable=False,
            )

    def test_api_forbidden_error_maps_to_403(self) -> None:
        @get("/test")
        async def handler() -> None:
            msg = "denied"
            raise ForbiddenError(msg)

        with TestClient(_make_app(handler)) as client:
            resp = client.get("/test")
            assert resp.status_code == 403
            body = resp.json()
            assert body["error"] == "denied"
            _assert_error_detail(
                body,
                error_code=ErrorCode.FORBIDDEN,
                error_category=ErrorCategory.AUTH,
                retryable=False,
            )

    def test_value_error_falls_through_to_catch_all(self) -> None:
        @get("/test")
        async def handler() -> None:
            msg = "bad input"
            raise ValueError(msg)

        with TestClient(_make_app(handler)) as client:
            resp = client.get("/test")
            assert resp.status_code == 500
            body = resp.json()
            _assert_error_detail(
                body,
                error_code=ErrorCode.INTERNAL_ERROR,
                error_category=ErrorCategory.INTERNAL,
                retryable=False,
            )

    def test_unexpected_error_maps_to_500(self) -> None:
        @get("/test")
        async def handler() -> None:
            msg = "boom"
            raise RuntimeError(msg)

        with TestClient(_make_app(handler)) as client:
            resp = client.get("/test")
            assert resp.status_code == 500
            body = resp.json()
            assert body["success"] is False
            assert body["error"] == "Internal server error"
            _assert_error_detail(
                body,
                error_code=ErrorCode.INTERNAL_ERROR,
                error_category=ErrorCategory.INTERNAL,
                retryable=False,
            )

    def test_unauthorized_error_maps_to_401(self) -> None:
        @get("/test")
        async def handler() -> None:
            msg = "Invalid credentials"
            raise UnauthorizedError(msg)

        with TestClient(_make_app(handler)) as client:
            resp = client.get("/test")
            assert resp.status_code == 401
            body = resp.json()
            # 4xx returns the actual message, not the generic default
            assert body["error"] == "Invalid credentials"
            _assert_error_detail(
                body,
                error_code=ErrorCode.UNAUTHORIZED,
                error_category=ErrorCategory.AUTH,
                retryable=False,
            )

    def test_validation_error_maps_to_422(self) -> None:
        @get("/test")
        async def handler() -> None:
            msg = "Bad field"
            raise ApiValidationError(msg)

        with TestClient(_make_app(handler)) as client:
            resp = client.get("/test")
            assert resp.status_code == 422
            body = resp.json()
            assert body["error"] == "Bad field"
            _assert_error_detail(
                body,
                error_code=ErrorCode.VALIDATION_ERROR,
                error_category=ErrorCategory.VALIDATION,
                retryable=False,
            )

    def test_unmatched_route_returns_404(self) -> None:
        """NotFoundException for unknown routes returns 404, not 500."""

        @get("/test")
        async def handler() -> str:
            return "ok"

        with TestClient(_make_app(handler)) as client:
            resp = client.get("/nonexistent")
            assert resp.status_code == 404
            body = resp.json()
            assert body["success"] is False
            assert body["error"] == "Not found"
            _assert_error_detail(
                body,
                error_code=ErrorCode.ROUTE_NOT_FOUND,
                error_category=ErrorCategory.NOT_FOUND,
                retryable=False,
            )

    def test_litestar_permission_denied_maps_to_403(self) -> None:
        """PermissionDeniedException with no detail falls back to 'Forbidden'."""

        @get("/test")
        async def handler() -> None:
            raise PermissionDeniedException

        with TestClient(_make_app(handler)) as client:
            resp = client.get("/test")
            assert resp.status_code == 403
            body = resp.json()
            assert body["success"] is False
            assert body["error"] == "Forbidden"
            _assert_error_detail(
                body,
                error_code=ErrorCode.FORBIDDEN,
                error_category=ErrorCategory.AUTH,
                retryable=False,
            )

    def test_permission_denied_scrubs_custom_detail(self) -> None:
        """PermissionDeniedException always returns fixed 'Forbidden' message."""

        @get("/test")
        async def handler() -> None:
            raise PermissionDeniedException(detail="Write access denied")

        with TestClient(_make_app(handler)) as client:
            resp = client.get("/test")
            assert resp.status_code == 403
            body = resp.json()
            assert body["error"] == "Forbidden"
            _assert_error_detail(
                body,
                error_code=ErrorCode.FORBIDDEN,
                error_category=ErrorCategory.AUTH,
                retryable=False,
            )

    def test_litestar_not_authorized_maps_to_401(self) -> None:
        """NotAuthorizedException with default detail returns 401."""

        @get("/test")
        async def handler() -> None:
            raise NotAuthorizedException

        with TestClient(_make_app(handler)) as client:
            resp = client.get("/test")
            assert resp.status_code == 401
            body = resp.json()
            assert body["success"] is False
            assert body["error"] == "Authentication required"
            _assert_error_detail(
                body,
                error_code=ErrorCode.UNAUTHORIZED,
                error_category=ErrorCategory.AUTH,
                retryable=False,
            )

    def test_not_authorized_scrubs_custom_detail(self) -> None:
        """NotAuthorizedException always returns fixed message."""

        @get("/test")
        async def handler() -> None:
            raise NotAuthorizedException(detail="Invalid JWT token")

        with TestClient(_make_app(handler)) as client:
            resp = client.get("/test")
            assert resp.status_code == 401
            body = resp.json()
            assert body["error"] == "Authentication required"
            _assert_error_detail(
                body,
                error_code=ErrorCode.UNAUTHORIZED,
                error_category=ErrorCategory.AUTH,
                retryable=False,
            )

    def test_litestar_validation_exception_maps_to_400(self) -> None:
        """Litestar ValidationException returns static 400."""

        @get("/test")
        async def handler() -> None:
            raise ValidationException

        with TestClient(_make_app(handler)) as client:
            resp = client.get("/test")
            assert resp.status_code == 400
            body = resp.json()
            assert body["success"] is False
            assert body["error"] == "Validation error"
            _assert_error_detail(
                body,
                error_code=ErrorCode.REQUEST_VALIDATION_ERROR,
                error_category=ErrorCategory.VALIDATION,
                retryable=False,
            )

    def test_method_not_allowed_maps_to_405(self) -> None:
        """Router-level MethodNotAllowed returns 405 via HTTPException handler."""

        @post("/test")
        async def handler() -> str:
            return "ok"

        with TestClient(_make_app(handler)) as client:
            resp = client.get("/test")
            assert resp.status_code == 405
            body = resp.json()
            assert body["success"] is False
            assert body["error"] == "Method Not Allowed"
            assert "POST" in resp.headers.get("allow", "")
            _assert_error_detail(
                body,
                error_code=ErrorCode.REQUEST_VALIDATION_ERROR,
                error_category=ErrorCategory.VALIDATION,
                retryable=False,
            )

    def test_http_exception_5xx_returns_scrubbed_message(self) -> None:
        """5xx HTTPException scrubs detail to prevent info leakage."""

        @get("/test")
        async def handler() -> None:
            raise HTTPException(
                status_code=502,
                detail="upstream db connection refused",
            )

        with TestClient(_make_app(handler)) as client:
            resp = client.get("/test")
            assert resp.status_code == 502
            body = resp.json()
            assert body["success"] is False
            assert body["error"] == "Internal server error"
            _assert_error_detail(
                body,
                error_code=ErrorCode.INTERNAL_ERROR,
                error_category=ErrorCategory.INTERNAL,
                retryable=False,
            )

    def test_http_exception_empty_detail_uses_phrase(self) -> None:
        """HTTPException with empty detail falls back to HTTP phrase."""

        @get("/test")
        async def handler() -> None:
            raise HTTPException(status_code=429)

        with TestClient(_make_app(handler)) as client:
            resp = client.get("/test")
            assert resp.status_code == 429
            body = resp.json()
            assert body["error"] == "Too Many Requests"
            _assert_error_detail(
                body,
                error_code=ErrorCode.RATE_LIMITED,
                error_category=ErrorCategory.RATE_LIMIT,
                retryable=True,
            )

    def test_http_exception_nonstandard_status_uses_fallback(self) -> None:
        """Non-standard status code falls back to generic message."""
        exc = MagicMock(spec=HTTPException)
        exc.status_code = 499
        exc.detail = ""
        exc.headers = None

        request = MagicMock()
        request.method = "GET"
        request.url.path = "/test"

        resp = handle_http_exception(request, exc)
        assert resp.status_code == 499
        assert resp.content.error == "Request error"
        assert resp.content.error_detail is not None
        assert resp.content.error_detail.error_category == ErrorCategory.VALIDATION


class TestStructuredErrorMetadata:
    """Tests specifically for RFC 9457 structured error features."""

    def test_service_unavailable_is_retryable(self) -> None:
        @get("/test")
        async def handler() -> None:
            raise ServiceUnavailableError

        with TestClient(_make_app(handler)) as client:
            resp = client.get("/test")
            assert resp.status_code == 503
            body = resp.json()
            assert body["error"] == "Service unavailable"
            _assert_error_detail(
                body,
                error_code=ErrorCode.SERVICE_UNAVAILABLE,
                error_category=ErrorCategory.INTERNAL,
                retryable=True,
            )

    def test_http_429_is_retryable(self) -> None:
        @get("/test")
        async def handler() -> None:
            raise HTTPException(status_code=429, detail="Slow down")

        with TestClient(_make_app(handler)) as client:
            resp = client.get("/test")
            assert resp.status_code == 429
            body = resp.json()
            _assert_error_detail(
                body,
                error_code=ErrorCode.RATE_LIMITED,
                error_category=ErrorCategory.RATE_LIMIT,
                retryable=True,
            )

    def test_http_503_is_retryable(self) -> None:
        @get("/test")
        async def handler() -> None:
            raise HTTPException(status_code=503)

        with TestClient(_make_app(handler)) as client:
            resp = client.get("/test")
            assert resp.status_code == 503
            body = resp.json()
            _assert_error_detail(
                body,
                error_code=ErrorCode.SERVICE_UNAVAILABLE,
                error_category=ErrorCategory.INTERNAL,
                retryable=True,
            )

    def test_instance_is_valid_uuid_format(self) -> None:
        """instance field should be a UUID when middleware is not active."""

        exc = RuntimeError("boom")
        request = MagicMock()
        request.method = "GET"
        request.url.path = "/test"

        resp = handle_unexpected(request, exc)
        instance = resp.content.error_detail.instance  # type: ignore[union-attr]
        assert _UUID_RE.match(instance), f"Expected UUID, got {instance!r}"

    def test_error_detail_message_matches_error_field(self) -> None:
        """error_detail.message must match the top-level error field."""

        @get("/test")
        async def handler() -> None:
            msg = "custom not found"
            raise NotFoundError(msg)

        with TestClient(_make_app(handler)) as client:
            resp = client.get("/test")
            body = resp.json()
            assert body["error_detail"]["message"] == body["error"]

    def test_retry_after_is_none_for_non_rate_limit(self) -> None:
        """retry_after should be None for non-rate-limit errors."""

        @get("/test")
        async def handler() -> None:
            msg = "dup"
            raise ConflictError(msg)

        with TestClient(_make_app(handler)) as client:
            resp = client.get("/test")
            body = resp.json()
            assert body["error_detail"]["retry_after"] is None

    def test_5xx_scrubs_custom_message(self) -> None:
        """ServiceUnavailableError with custom message returns default."""

        @get("/test")
        async def handler() -> None:
            msg = "Connection pool exhausted: 10.0.0.5:5432"
            raise ServiceUnavailableError(msg)

        with TestClient(_make_app(handler)) as client:
            resp = client.get("/test")
            assert resp.status_code == 503
            body = resp.json()
            # 5xx must scrub to class-level default, not leak internals
            assert body["error"] == "Service unavailable"
            assert "10.0.0.5" not in body["error"]


class TestGetInstanceId:
    """Direct unit tests for _get_instance_id helper."""

    def test_returns_request_id_from_context(self) -> None:
        structlog.contextvars.bind_contextvars(request_id="req-known-123")
        try:
            result = _get_instance_id()
            assert result == "req-known-123"
        finally:
            structlog.contextvars.unbind_contextvars("request_id")

    def test_falls_back_to_uuid_when_no_context(self) -> None:
        structlog.contextvars.unbind_contextvars("request_id")

        result = _get_instance_id()
        assert _UUID_RE.match(result)

    def test_falls_back_for_non_string_request_id(self) -> None:
        structlog.contextvars.bind_contextvars(request_id=12345)
        try:
            result = _get_instance_id()
            assert _UUID_RE.match(result)
        finally:
            structlog.contextvars.unbind_contextvars("request_id")

    def test_falls_back_for_empty_string_request_id(self) -> None:
        structlog.contextvars.bind_contextvars(request_id="")
        try:
            result = _get_instance_id()
            assert _UUID_RE.match(result)
        finally:
            structlog.contextvars.unbind_contextvars("request_id")


class TestCategoryForStatus:
    """Direct unit tests for _category_for_status helper."""

    @pytest.mark.parametrize(
        ("status", "expected_code", "expected_category", "expected_retryable"),
        [
            (401, ErrorCode.UNAUTHORIZED, ErrorCategory.AUTH, False),
            (403, ErrorCode.FORBIDDEN, ErrorCategory.AUTH, False),
            (404, ErrorCode.ROUTE_NOT_FOUND, ErrorCategory.NOT_FOUND, False),
            (409, ErrorCode.RESOURCE_CONFLICT, ErrorCategory.CONFLICT, False),
            (429, ErrorCode.RATE_LIMITED, ErrorCategory.RATE_LIMIT, True),
            (503, ErrorCode.SERVICE_UNAVAILABLE, ErrorCategory.INTERNAL, True),
        ],
    )
    def test_mapped_status_codes(
        self,
        status: int,
        expected_code: ErrorCode,
        expected_category: ErrorCategory,
        expected_retryable: bool,
    ) -> None:
        code, category, retryable = _category_for_status(status)
        assert code == expected_code
        assert category == expected_category
        assert retryable is expected_retryable

    def test_unmapped_server_error(self) -> None:
        code, category, retryable = _category_for_status(507)
        assert code == ErrorCode.INTERNAL_ERROR
        assert category == ErrorCategory.INTERNAL
        assert retryable is False

    def test_unmapped_client_error(self) -> None:
        code, category, retryable = _category_for_status(418)
        assert code == ErrorCode.REQUEST_VALIDATION_ERROR
        assert category == ErrorCategory.VALIDATION
        assert retryable is False


class TestApiErrorInstantiation:
    """Tests for ApiError and subclass instantiation behavior."""

    @pytest.mark.parametrize(
        ("cls", "expected_status", "expected_default"),
        [
            (NotFoundError, 404, "Resource not found"),
            (ConflictError, 409, "Resource conflict"),
            (ForbiddenError, 403, "Forbidden"),
            (UnauthorizedError, 401, "Authentication required"),
            (ServiceUnavailableError, 503, "Service unavailable"),
        ],
    )
    def test_default_message_and_status(
        self,
        cls: type[ApiError],
        expected_status: int,
        expected_default: str,
    ) -> None:
        exc = cls()
        assert str(exc) == expected_default
        assert exc.status_code == expected_status

    def test_custom_message_takes_precedence(self) -> None:
        exc = NotFoundError("Custom not found")
        assert str(exc) == "Custom not found"
        assert exc.status_code == 404


class TestGetInstanceIdExceptionFallback:
    """Test that _get_instance_id falls back when get_contextvars raises."""

    def test_falls_back_when_get_contextvars_raises(self) -> None:
        with patch(
            "structlog.contextvars.get_contextvars",
            side_effect=RuntimeError("broken"),
        ):
            result = _get_instance_id()
            assert _UUID_RE.match(result)


class TestBuildErrorResponseRetryAfter:
    """Test _build_error_response with non-None retry_after."""

    def test_retry_after_propagated(self) -> None:
        resp = _build_error_response(
            message="Slow down",
            error_code=ErrorCode.RATE_LIMITED,
            error_category=ErrorCategory.RATE_LIMIT,
            retryable=True,
            retry_after=120,
        )
        assert resp.error_detail is not None
        assert resp.error_detail.retry_after == 120
        assert resp.error_detail.retryable is True
