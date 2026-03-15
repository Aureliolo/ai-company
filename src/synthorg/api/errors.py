"""API error hierarchy and RFC 9457 error taxonomy.

All API-specific errors inherit from ``ApiError`` so callers
can catch the entire family with a single except clause.

``ErrorCategory`` and ``ErrorCode`` provide machine-readable error
metadata for structured error responses (RFC 9457 Phase 1).
"""

from enum import IntEnum, StrEnum


class ErrorCategory(StrEnum):
    """High-level error category for structured error responses.

    Values are lowercase strings suitable for JSON serialization.
    """

    AUTH = "auth"
    VALIDATION = "validation"
    NOT_FOUND = "not_found"
    CONFLICT = "conflict"
    RATE_LIMIT = "rate_limit"
    BUDGET_EXHAUSTED = "budget_exhausted"
    PROVIDER_ERROR = "provider_error"
    INTERNAL = "internal"


class ErrorCode(IntEnum):
    """Machine-readable error codes (4-digit, category-grouped).

    First digit encodes the category:
    1xxx = auth, 2xxx = validation, 3xxx = not_found, 4xxx = conflict,
    5xxx = rate_limit, 6xxx = budget_exhausted, 7xxx = provider_error,
    8xxx = internal.
    """

    # 1xxx — auth
    UNAUTHORIZED = 1000
    FORBIDDEN = 1001

    # 2xxx — validation
    VALIDATION_ERROR = 2000
    REQUEST_VALIDATION_ERROR = 2001

    # 3xxx — not_found
    RESOURCE_NOT_FOUND = 3000
    RECORD_NOT_FOUND = 3001
    ROUTE_NOT_FOUND = 3002

    # 4xxx — conflict
    RESOURCE_CONFLICT = 4000
    DUPLICATE_RECORD = 4001

    # 5xxx — rate_limit
    RATE_LIMITED = 5000

    # 6xxx — budget_exhausted
    BUDGET_EXHAUSTED = 6000

    # 7xxx — provider_error
    PROVIDER_ERROR = 7000

    # 8xxx — internal
    INTERNAL_ERROR = 8000
    SERVICE_UNAVAILABLE = 8001
    PERSISTENCE_ERROR = 8002


# Maps first digit of error code to its expected category.
_CODE_CATEGORY_PREFIX: dict[int, ErrorCategory] = {
    1: ErrorCategory.AUTH,
    2: ErrorCategory.VALIDATION,
    3: ErrorCategory.NOT_FOUND,
    4: ErrorCategory.CONFLICT,
    5: ErrorCategory.RATE_LIMIT,
    6: ErrorCategory.BUDGET_EXHAUSTED,
    7: ErrorCategory.PROVIDER_ERROR,
    8: ErrorCategory.INTERNAL,
}


class ApiError(Exception):
    """Base exception for API-layer errors.

    Attributes:
        default_message: Class-level default error message.
        status_code: HTTP status code associated with this error.
        error_category: RFC 9457 error category.
        error_code: RFC 9457 machine-readable error code.
        retryable: Whether the client should retry the request.
    """

    default_message: str = "Internal server error"
    error_category: ErrorCategory = ErrorCategory.INTERNAL
    error_code: ErrorCode = ErrorCode.INTERNAL_ERROR
    retryable: bool = False

    def __init__(self, message: str | None = None, *, status_code: int = 500) -> None:
        super().__init__(message or self.default_message)
        self.status_code = status_code


class NotFoundError(ApiError):
    """Raised when a requested resource does not exist (404)."""

    default_message: str = "Resource not found"
    error_category: ErrorCategory = ErrorCategory.NOT_FOUND
    error_code: ErrorCode = ErrorCode.RESOURCE_NOT_FOUND
    retryable: bool = False

    def __init__(self, message: str | None = None) -> None:
        super().__init__(message, status_code=404)


class ApiValidationError(ApiError):
    """Raised when request data fails validation (422)."""

    default_message: str = "Validation error"
    error_category: ErrorCategory = ErrorCategory.VALIDATION
    error_code: ErrorCode = ErrorCode.VALIDATION_ERROR
    retryable: bool = False

    def __init__(self, message: str | None = None) -> None:
        super().__init__(message, status_code=422)


class ConflictError(ApiError):
    """Raised when a resource conflict occurs (409)."""

    default_message: str = "Resource conflict"
    error_category: ErrorCategory = ErrorCategory.CONFLICT
    error_code: ErrorCode = ErrorCode.RESOURCE_CONFLICT
    retryable: bool = False

    def __init__(self, message: str | None = None) -> None:
        super().__init__(message, status_code=409)


class ForbiddenError(ApiError):
    """Raised when access is denied (403)."""

    default_message: str = "Forbidden"
    error_category: ErrorCategory = ErrorCategory.AUTH
    error_code: ErrorCode = ErrorCode.FORBIDDEN
    retryable: bool = False

    def __init__(self, message: str | None = None) -> None:
        super().__init__(message, status_code=403)


class UnauthorizedError(ApiError):
    """Raised when authentication is required or invalid (401)."""

    default_message: str = "Authentication required"
    error_category: ErrorCategory = ErrorCategory.AUTH
    error_code: ErrorCode = ErrorCode.UNAUTHORIZED
    retryable: bool = False

    def __init__(self, message: str | None = None) -> None:
        super().__init__(message, status_code=401)


class ServiceUnavailableError(ApiError):
    """Raised when a required service is not configured (503)."""

    default_message: str = "Service unavailable"
    error_category: ErrorCategory = ErrorCategory.INTERNAL
    error_code: ErrorCode = ErrorCode.SERVICE_UNAVAILABLE
    retryable: bool = True

    def __init__(self, message: str | None = None) -> None:
        super().__init__(message, status_code=503)
