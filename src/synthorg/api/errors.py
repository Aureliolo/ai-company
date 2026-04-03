"""API error hierarchy and RFC 9457 error taxonomy.

All API-specific errors inherit from ``ApiError`` so callers
can catch the entire family with a single except clause.

``ErrorCategory`` and ``ErrorCode`` provide machine-readable error
metadata for structured error responses (RFC 9457).
"""

from enum import IntEnum, StrEnum
from types import MappingProxyType
from typing import ClassVar, Final


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

    # 1xxx -- auth
    UNAUTHORIZED = 1000
    FORBIDDEN = 1001
    SESSION_REVOKED = 1002

    # 2xxx -- validation
    VALIDATION_ERROR = 2000
    REQUEST_VALIDATION_ERROR = 2001

    # 3xxx -- not_found
    RESOURCE_NOT_FOUND = 3000
    RECORD_NOT_FOUND = 3001
    ROUTE_NOT_FOUND = 3002

    # 4xxx -- conflict
    RESOURCE_CONFLICT = 4000
    DUPLICATE_RECORD = 4001
    VERSION_CONFLICT = 4002

    # 5xxx -- rate_limit
    RATE_LIMITED = 5000

    # 6xxx -- budget_exhausted
    BUDGET_EXHAUSTED = 6000

    # 7xxx -- provider_error
    PROVIDER_ERROR = 7000

    # 8xxx -- internal
    INTERNAL_ERROR = 8000
    SERVICE_UNAVAILABLE = 8001
    PERSISTENCE_ERROR = 8002


# Maps first digit of error code to its expected category.
# Used by ``__init_subclass__`` to validate that error code prefixes
# match their declared category.
_CODE_CATEGORY_PREFIX: MappingProxyType[int, ErrorCategory] = MappingProxyType(
    {
        1: ErrorCategory.AUTH,
        2: ErrorCategory.VALIDATION,
        3: ErrorCategory.NOT_FOUND,
        4: ErrorCategory.CONFLICT,
        5: ErrorCategory.RATE_LIMIT,
        6: ErrorCategory.BUDGET_EXHAUSTED,
        7: ErrorCategory.PROVIDER_ERROR,
        8: ErrorCategory.INTERNAL,
    }
)


CATEGORY_TITLES: MappingProxyType[ErrorCategory, str] = MappingProxyType(
    {
        ErrorCategory.AUTH: "Authentication Error",
        ErrorCategory.VALIDATION: "Validation Error",
        ErrorCategory.NOT_FOUND: "Resource Not Found",
        ErrorCategory.CONFLICT: "Resource Conflict",
        ErrorCategory.RATE_LIMIT: "Rate Limit Exceeded",
        ErrorCategory.BUDGET_EXHAUSTED: "Budget Exhausted",
        ErrorCategory.PROVIDER_ERROR: "Provider Error",
        ErrorCategory.INTERNAL: "Internal Server Error",
    }
)

_ERROR_DOCS_BASE: Final[str] = "https://synthorg.io/docs/errors"


def category_title(cat: ErrorCategory) -> str:
    """Return the RFC 9457 ``title`` for a category.

    Args:
        cat: Error category.

    Returns:
        Human-readable title string.
    """
    return CATEGORY_TITLES[cat]


def category_type_uri(cat: ErrorCategory) -> str:
    """Return the RFC 9457 ``type`` URI for a category.

    Args:
        cat: Error category.

    Returns:
        Documentation URI with fragment anchor for the error category.
    """
    return f"{_ERROR_DOCS_BASE}#{cat.value}"


class ApiError(Exception):
    """Base exception for API-layer errors.

    Class Attributes:
        default_message: Fallback error message used when none is provided
            and for 5xx response scrubbing.
        error_category: RFC 9457 error category.
        error_code: RFC 9457 machine-readable error code.
        retryable: Whether the client should retry the request.

    Instance Attributes:
        status_code: HTTP status code (set via ``__init__``, fixed per
            subclass).
    """

    default_message: ClassVar[str] = "Internal server error"
    error_category: ClassVar[ErrorCategory] = ErrorCategory.INTERNAL
    error_code: ClassVar[ErrorCode] = ErrorCode.INTERNAL_ERROR
    retryable: ClassVar[bool] = False

    def __init__(self, message: str | None = None, *, status_code: int = 500) -> None:
        super().__init__(message or self.default_message)
        self.status_code = status_code

    def __init_subclass__(cls, **kwargs: object) -> None:
        """Validate error_code/error_category consistency at class creation."""
        super().__init_subclass__(**kwargs)
        prefix = cls.error_code.value // 1000
        expected = _CODE_CATEGORY_PREFIX.get(prefix)
        if expected is not None and cls.error_category != expected:
            msg = (
                f"{cls.__name__}: error_code {cls.error_code.name} "
                f"(prefix {prefix}) implies category {expected.name}, "
                f"but error_category is {cls.error_category.name}"
            )
            raise TypeError(msg)


class NotFoundError(ApiError):
    """Raised when a requested resource does not exist (404)."""

    default_message: ClassVar[str] = "Resource not found"
    error_category: ClassVar[ErrorCategory] = ErrorCategory.NOT_FOUND
    error_code: ClassVar[ErrorCode] = ErrorCode.RESOURCE_NOT_FOUND

    def __init__(self, message: str | None = None) -> None:
        super().__init__(message, status_code=404)


class ApiValidationError(ApiError):
    """Raised when request data fails validation (422)."""

    default_message: ClassVar[str] = "Validation error"
    error_category: ClassVar[ErrorCategory] = ErrorCategory.VALIDATION
    error_code: ClassVar[ErrorCode] = ErrorCode.VALIDATION_ERROR

    def __init__(self, message: str | None = None) -> None:
        super().__init__(message, status_code=422)


class ConflictError(ApiError):
    """Raised when a resource conflict occurs (409)."""

    default_message: ClassVar[str] = "Resource conflict"
    error_category: ClassVar[ErrorCategory] = ErrorCategory.CONFLICT
    error_code: ClassVar[ErrorCode] = ErrorCode.RESOURCE_CONFLICT

    def __init__(self, message: str | None = None) -> None:
        super().__init__(message, status_code=409)


class VersionConflictError(ApiError):
    """Raised when an ETag/If-Match version check fails (409).

    Used for ETag/If-Match optimistic concurrency checks --
    currently on settings endpoints.
    """

    default_message: ClassVar[str] = "Version conflict"
    error_category: ClassVar[ErrorCategory] = ErrorCategory.CONFLICT
    error_code: ClassVar[ErrorCode] = ErrorCode.VERSION_CONFLICT

    def __init__(self, message: str | None = None) -> None:
        super().__init__(message, status_code=409)


class ForbiddenError(ApiError):
    """Raised when access is denied (403)."""

    default_message: ClassVar[str] = "Forbidden"
    error_category: ClassVar[ErrorCategory] = ErrorCategory.AUTH
    error_code: ClassVar[ErrorCode] = ErrorCode.FORBIDDEN

    def __init__(self, message: str | None = None) -> None:
        super().__init__(message, status_code=403)


class SessionRevokedError(ApiError):
    """Raised when a revoked session token is used (401).

    Gives clients a distinct error code (``SESSION_REVOKED``) so
    they can show a "you were logged out" message instead of a
    generic auth failure.
    """

    default_message: ClassVar[str] = "Session has been revoked"
    error_category: ClassVar[ErrorCategory] = ErrorCategory.AUTH
    error_code: ClassVar[ErrorCode] = ErrorCode.SESSION_REVOKED

    def __init__(self, message: str | None = None) -> None:
        super().__init__(message, status_code=401)


class UnauthorizedError(ApiError):
    """Raised when authentication is required or invalid (401)."""

    default_message: ClassVar[str] = "Authentication required"
    error_category: ClassVar[ErrorCategory] = ErrorCategory.AUTH
    error_code: ClassVar[ErrorCode] = ErrorCode.UNAUTHORIZED

    def __init__(self, message: str | None = None) -> None:
        super().__init__(message, status_code=401)


class ServiceUnavailableError(ApiError):
    """Raised when a required service is not configured (503)."""

    default_message: ClassVar[str] = "Service unavailable"
    error_category: ClassVar[ErrorCategory] = ErrorCategory.INTERNAL
    error_code: ClassVar[ErrorCode] = ErrorCode.SERVICE_UNAVAILABLE
    retryable: ClassVar[bool] = True

    def __init__(self, message: str | None = None) -> None:
        super().__init__(message, status_code=503)
