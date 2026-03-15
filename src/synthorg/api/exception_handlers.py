"""Exception handlers mapping domain errors to HTTP responses.

Each handler returns an ``ApiResponse(error=...)`` with the
appropriate HTTP status code.  5xx responses return a generic
scrubbed message; 4xx responses pass through the exception detail
(authored by SynthOrg's guards/middleware and user-safe).  Detailed
error context is logged server-side for all status codes.

All handlers populate ``error_detail`` with structured RFC 9457
metadata (error code, category, retryability, request correlation ID).
"""

from http import HTTPStatus
from types import MappingProxyType
from typing import Any, Final

import structlog
from litestar import Request, Response
from litestar.exceptions import (
    HTTPException,
    NotAuthorizedException,
    NotFoundException,
    PermissionDeniedException,
    ValidationException,
)

from synthorg.api.dto import ApiResponse, ErrorDetail
from synthorg.api.errors import ApiError, ErrorCategory, ErrorCode
from synthorg.observability import get_logger
from synthorg.observability.correlation import generate_correlation_id
from synthorg.observability.events.api import (
    API_REQUEST_ERROR,
    API_ROUTE_NOT_FOUND,
)
from synthorg.persistence.errors import (
    DuplicateRecordError,
    PersistenceError,
    RecordNotFoundError,
)

logger = get_logger(__name__)

_SERVER_ERROR_THRESHOLD: Final[int] = 500

# Headers safe to forward from HTTPException to the client response.
_ALLOWED_PASSTHROUGH_HEADERS: Final[frozenset[str]] = frozenset(
    {"retry-after", "www-authenticate", "allow"},
)


def _get_instance_id() -> str:
    """Get request correlation ID from structlog context, or generate one.

    Wrapped defensively because this runs inside exception handlers,
    which are the last line of defense and must never crash.
    """
    try:
        ctx = structlog.contextvars.get_contextvars()
        request_id = ctx.get("request_id")
        if isinstance(request_id, str) and request_id:
            return request_id
    except Exception:
        logger.debug("correlation_id_fallback_generated")
    return generate_correlation_id()


def _build_error_response(
    *,
    message: str,
    error_code: ErrorCode,
    error_category: ErrorCategory,
    retryable: bool = False,
    retry_after: int | None = None,
) -> ApiResponse[None]:
    """Build an ``ApiResponse`` with structured ``ErrorDetail``.

    The ``instance`` field is auto-populated from the current structlog
    request context (falling back to a newly generated correlation ID
    if unavailable).
    """
    return ApiResponse[None](
        error=message,
        error_detail=ErrorDetail(
            message=message,
            error_code=error_code,
            error_category=error_category,
            retryable=retryable,
            retry_after=retry_after,
            instance=_get_instance_id(),
        ),
    )


_STATUS_TO_ERROR_META: MappingProxyType[int, tuple[ErrorCode, ErrorCategory, bool]] = (
    MappingProxyType(
        {
            401: (ErrorCode.UNAUTHORIZED, ErrorCategory.AUTH, False),
            403: (ErrorCode.FORBIDDEN, ErrorCategory.AUTH, False),
            404: (ErrorCode.ROUTE_NOT_FOUND, ErrorCategory.NOT_FOUND, False),
            409: (ErrorCode.RESOURCE_CONFLICT, ErrorCategory.CONFLICT, False),
            429: (ErrorCode.RATE_LIMITED, ErrorCategory.RATE_LIMIT, True),
            503: (ErrorCode.SERVICE_UNAVAILABLE, ErrorCategory.INTERNAL, True),
        }
    )
)

_CLIENT_ERROR_DEFAULT: tuple[ErrorCode, ErrorCategory, bool] = (
    ErrorCode.REQUEST_VALIDATION_ERROR,
    ErrorCategory.VALIDATION,
    False,
)

_SERVER_ERROR_DEFAULT: tuple[ErrorCode, ErrorCategory, bool] = (
    ErrorCode.INTERNAL_ERROR,
    ErrorCategory.INTERNAL,
    False,
)


def _category_for_status(
    status: int,
) -> tuple[ErrorCode, ErrorCategory, bool]:
    """Map HTTP status to error code, category, and retryability."""
    if status in _STATUS_TO_ERROR_META:
        return _STATUS_TO_ERROR_META[status]
    if status >= _SERVER_ERROR_THRESHOLD:
        return _SERVER_ERROR_DEFAULT
    return _CLIENT_ERROR_DEFAULT


def _log_error(
    request: Request[Any, Any, Any],
    exc: Exception,
    *,
    status: int,
) -> None:
    """Log an API error with request context.

    Uses ERROR level (with traceback) for 5xx server errors and
    WARNING for 4xx client errors.
    """
    log = logger.error if status >= _SERVER_ERROR_THRESHOLD else logger.warning
    log(
        API_REQUEST_ERROR,
        method=request.method,
        path=str(request.url.path),
        status_code=status,
        error_type=type(exc).__qualname__,
        error=str(exc),
        exc_info=status >= _SERVER_ERROR_THRESHOLD,
    )


def handle_record_not_found(
    request: Request[Any, Any, Any],
    exc: RecordNotFoundError,
) -> Response[ApiResponse[None]]:
    """Map ``RecordNotFoundError`` to 404."""
    _log_error(request, exc, status=404)
    return Response(
        content=_build_error_response(
            message="Resource not found",
            error_code=ErrorCode.RECORD_NOT_FOUND,
            error_category=ErrorCategory.NOT_FOUND,
        ),
        status_code=404,
    )


def handle_duplicate_record(
    request: Request[Any, Any, Any],
    exc: DuplicateRecordError,
) -> Response[ApiResponse[None]]:
    """Map ``DuplicateRecordError`` to 409."""
    _log_error(request, exc, status=409)
    return Response(
        content=_build_error_response(
            message="Resource already exists",
            error_code=ErrorCode.DUPLICATE_RECORD,
            error_category=ErrorCategory.CONFLICT,
        ),
        status_code=409,
    )


def handle_persistence_error(
    request: Request[Any, Any, Any],
    exc: PersistenceError,
) -> Response[ApiResponse[None]]:
    """Map ``PersistenceError`` to 500."""
    _log_error(request, exc, status=500)
    return Response(
        content=_build_error_response(
            message="Internal server error",
            error_code=ErrorCode.INTERNAL_ERROR,
            error_category=ErrorCategory.INTERNAL,
        ),
        status_code=500,
    )


def handle_api_error(
    request: Request[Any, Any, Any],
    exc: ApiError,
) -> Response[ApiResponse[None]]:
    """Map ``ApiError`` subclasses to their declared status code."""
    _log_error(request, exc, status=exc.status_code)
    # For 5xx errors return the generic class-level default to avoid
    # leaking internals.  For 4xx client errors return the actual
    # exception message — it was set by the controller and is user-safe.
    if exc.status_code >= _SERVER_ERROR_THRESHOLD:
        msg = type(exc).default_message
    else:
        msg = str(exc)
    return Response(
        content=_build_error_response(
            message=msg,
            error_code=exc.error_code,
            error_category=exc.error_category,
            retryable=exc.retryable,
        ),
        status_code=exc.status_code,
    )


def handle_unexpected(
    request: Request[Any, Any, Any],
    exc: Exception,
) -> Response[ApiResponse[None]]:
    """Catch-all for unexpected errors -> 500."""
    _log_error(request, exc, status=500)
    return Response(
        content=_build_error_response(
            message="Internal server error",
            error_code=ErrorCode.INTERNAL_ERROR,
            error_category=ErrorCategory.INTERNAL,
        ),
        status_code=500,
    )


def handle_permission_denied(
    request: Request[Any, Any, Any],
    exc: PermissionDeniedException,
) -> Response[ApiResponse[None]]:
    """Map ``PermissionDeniedException`` to 403."""
    _log_error(request, exc, status=403)
    return Response(
        content=_build_error_response(
            message="Forbidden",
            error_code=ErrorCode.FORBIDDEN,
            error_category=ErrorCategory.AUTH,
        ),
        status_code=403,
    )


def handle_validation_error(
    request: Request[Any, Any, Any],
    exc: ValidationException,
) -> Response[ApiResponse[None]]:
    """Map ``ValidationException`` to 400."""
    _log_error(request, exc, status=400)
    return Response(
        content=_build_error_response(
            message="Validation error",
            error_code=ErrorCode.REQUEST_VALIDATION_ERROR,
            error_category=ErrorCategory.VALIDATION,
        ),
        status_code=400,
    )


def handle_not_authorized(
    request: Request[Any, Any, Any],
    exc: NotAuthorizedException,
) -> Response[ApiResponse[None]]:
    """Map ``NotAuthorizedException`` to 401."""
    _log_error(request, exc, status=401)
    return Response(
        content=_build_error_response(
            message="Authentication required",
            error_code=ErrorCode.UNAUTHORIZED,
            error_category=ErrorCategory.AUTH,
        ),
        status_code=401,
    )


def handle_not_found(
    request: Request[Any, Any, Any],
    exc: NotFoundException,
) -> Response[ApiResponse[None]]:
    """Map Litestar ``NotFoundException`` to 404.

    Ensures unmatched routes return 404 instead of falling through
    to ``handle_unexpected`` (which returns 500), which ZAP flags
    as a security misconfiguration.
    """
    logger.warning(
        API_ROUTE_NOT_FOUND,
        method=request.method,
        path=str(request.url.path),
        status_code=404,
        error_type=type(exc).__qualname__,
        error=str(exc),
    )
    return Response(
        content=_build_error_response(
            message="Not found",
            error_code=ErrorCode.ROUTE_NOT_FOUND,
            error_category=ErrorCategory.NOT_FOUND,
        ),
        status_code=404,
    )


def handle_http_exception(
    request: Request[Any, Any, Any],
    exc: HTTPException,
) -> Response[ApiResponse[None]]:
    """Catch-all for unhandled Litestar ``HTTPException`` subclasses.

    Preserves the correct status code (e.g. 405, 429) instead of
    letting them fall through to ``handle_unexpected`` as 500.
    """
    status = exc.status_code
    _log_error(request, exc, status=status)
    if status >= _SERVER_ERROR_THRESHOLD:
        msg = "Internal server error"
    else:
        try:
            fallback = HTTPStatus(status).phrase
        except ValueError:
            fallback = "Request error"
        msg = exc.detail or fallback
    code, category, retryable = _category_for_status(status)
    return Response(
        content=_build_error_response(
            message=msg,
            error_code=code,
            error_category=category,
            retryable=retryable,
        ),
        status_code=status,
        headers={
            k: v
            for k, v in (exc.headers or {}).items()
            if k.lower() in _ALLOWED_PASSTHROUGH_HEADERS
        }
        or None,
    )


# Litestar resolves exception handlers by walking the raised exception's
# MRO — the first matching type found in this dict wins.  Dict insertion
# order does NOT affect resolution priority.  (For HTTPException subclasses,
# Litestar also checks integer status-code keys first, but this dict uses
# only type keys.)
EXCEPTION_HANDLERS: dict[type[Exception], object] = {
    RecordNotFoundError: handle_record_not_found,
    DuplicateRecordError: handle_duplicate_record,
    PersistenceError: handle_persistence_error,
    NotAuthorizedException: handle_not_authorized,
    PermissionDeniedException: handle_permission_denied,
    ValidationException: handle_validation_error,
    NotFoundException: handle_not_found,
    HTTPException: handle_http_exception,
    ApiError: handle_api_error,
    Exception: handle_unexpected,
}
