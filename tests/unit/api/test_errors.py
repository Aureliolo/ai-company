"""Tests for API error hierarchy and RFC 9457 error taxonomy."""

import pytest

from synthorg.api.errors import (
    _CODE_CATEGORY_PREFIX,
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

pytestmark = pytest.mark.unit

_EXPECTED_CODES: dict[str, int] = {
    "UNAUTHORIZED": 1000,
    "FORBIDDEN": 1001,
    "VALIDATION_ERROR": 2000,
    "REQUEST_VALIDATION_ERROR": 2001,
    "RESOURCE_NOT_FOUND": 3000,
    "RECORD_NOT_FOUND": 3001,
    "ROUTE_NOT_FOUND": 3002,
    "RESOURCE_CONFLICT": 4000,
    "DUPLICATE_RECORD": 4001,
    "RATE_LIMITED": 5000,
    "BUDGET_EXHAUSTED": 6000,
    "PROVIDER_ERROR": 7000,
    "INTERNAL_ERROR": 8000,
    "SERVICE_UNAVAILABLE": 8001,
    "PERSISTENCE_ERROR": 8002,
}


class TestErrorCategory:
    """ErrorCategory enum completeness and values."""

    def test_has_all_eight_members(self) -> None:
        assert len(ErrorCategory) == 8

    @pytest.mark.parametrize(
        ("member", "value"),
        [
            (ErrorCategory.AUTH, "auth"),
            (ErrorCategory.VALIDATION, "validation"),
            (ErrorCategory.NOT_FOUND, "not_found"),
            (ErrorCategory.CONFLICT, "conflict"),
            (ErrorCategory.RATE_LIMIT, "rate_limit"),
            (ErrorCategory.BUDGET_EXHAUSTED, "budget_exhausted"),
            (ErrorCategory.PROVIDER_ERROR, "provider_error"),
            (ErrorCategory.INTERNAL, "internal"),
        ],
    )
    def test_member_values(self, member: ErrorCategory, value: str) -> None:
        assert member.value == value


class TestErrorCode:
    """ErrorCode enum completeness and values."""

    def test_has_all_codes(self) -> None:
        assert len(ErrorCode) == len(_EXPECTED_CODES)

    @pytest.mark.parametrize(
        ("name", "value"),
        list(_EXPECTED_CODES.items()),
    )
    def test_code_values(self, name: str, value: int) -> None:
        assert ErrorCode[name].value == value

    def test_no_duplicate_values(self) -> None:
        values = [c.value for c in ErrorCode]
        assert len(values) == len(set(values))

    def test_code_category_prefix_consistency(self) -> None:
        """First digit of each code matches _CODE_CATEGORY_PREFIX."""
        for code in ErrorCode:
            prefix = code.value // 1000
            assert prefix in _CODE_CATEGORY_PREFIX, (
                f"{code.name} has prefix {prefix} not in mapping"
            )


class TestApiErrorMetadata:
    """Class-level error metadata on ApiError hierarchy."""

    @pytest.mark.parametrize(
        ("cls", "category", "code", "retryable"),
        [
            (ApiError, ErrorCategory.INTERNAL, ErrorCode.INTERNAL_ERROR, False),
            (
                NotFoundError,
                ErrorCategory.NOT_FOUND,
                ErrorCode.RESOURCE_NOT_FOUND,
                False,
            ),
            (
                ApiValidationError,
                ErrorCategory.VALIDATION,
                ErrorCode.VALIDATION_ERROR,
                False,
            ),
            (
                ConflictError,
                ErrorCategory.CONFLICT,
                ErrorCode.RESOURCE_CONFLICT,
                False,
            ),
            (ForbiddenError, ErrorCategory.AUTH, ErrorCode.FORBIDDEN, False),
            (UnauthorizedError, ErrorCategory.AUTH, ErrorCode.UNAUTHORIZED, False),
            (
                ServiceUnavailableError,
                ErrorCategory.INTERNAL,
                ErrorCode.SERVICE_UNAVAILABLE,
                True,
            ),
        ],
    )
    def test_class_level_metadata(
        self,
        cls: type[ApiError],
        category: ErrorCategory,
        code: ErrorCode,
        retryable: bool,
    ) -> None:
        assert cls.error_category == category
        assert cls.error_code == code
        assert cls.retryable is retryable

    def test_service_unavailable_is_retryable(self) -> None:
        exc = ServiceUnavailableError()
        assert exc.retryable is True
        assert exc.status_code == 503

    def test_init_subclass_rejects_mismatched_category(self) -> None:
        """Subclass with code/category mismatch raises TypeError."""
        with pytest.raises(TypeError, match="implies category"):

            class _BadError(ApiError):
                error_category = ErrorCategory.AUTH
                error_code = ErrorCode.INTERNAL_ERROR  # 8xxx != auth
