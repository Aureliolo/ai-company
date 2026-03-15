"""Tests for exception handlers with RFC 9457 structured error responses."""

import re
from typing import Any

import pytest
from litestar import Litestar, get, post
from litestar.exceptions import (
    HTTPException,
    NotAuthorizedException,
    PermissionDeniedException,
    ValidationException,
)
from litestar.testing import TestClient

from synthorg.api.errors import (
    ApiValidationError,
    ConflictError,
    ErrorCategory,
    ErrorCode,
    ForbiddenError,
    NotFoundError,
    ServiceUnavailableError,
    UnauthorizedError,
)
from synthorg.api.exception_handlers import EXCEPTION_HANDLERS
from synthorg.persistence.errors import (
    DuplicateRecordError,
    PersistenceError,
    RecordNotFoundError,
)

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


@pytest.mark.unit
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
            assert body["error"] == "Internal persistence error"
            _assert_error_detail(
                body,
                error_code=ErrorCode.PERSISTENCE_ERROR,
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

    def test_permission_denied_preserves_detail(self) -> None:
        """PermissionDeniedException with custom detail passes it through."""

        @get("/test")
        async def handler() -> None:
            raise PermissionDeniedException(detail="Write access denied")

        with TestClient(_make_app(handler)) as client:
            resp = client.get("/test")
            assert resp.status_code == 403
            body = resp.json()
            assert body["error"] == "Write access denied"
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
            assert body["error"] == "Unauthorized"
            _assert_error_detail(
                body,
                error_code=ErrorCode.UNAUTHORIZED,
                error_category=ErrorCategory.AUTH,
                retryable=False,
            )

    def test_not_authorized_preserves_detail(self) -> None:
        """NotAuthorizedException with custom detail passes it through."""

        @get("/test")
        async def handler() -> None:
            raise NotAuthorizedException(detail="Invalid JWT token")

        with TestClient(_make_app(handler)) as client:
            resp = client.get("/test")
            assert resp.status_code == 401
            body = resp.json()
            assert body["error"] == "Invalid JWT token"
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
        from unittest.mock import MagicMock

        from synthorg.api.exception_handlers import handle_http_exception

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


@pytest.mark.unit
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
        from unittest.mock import MagicMock

        from synthorg.api.exception_handlers import handle_unexpected

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
