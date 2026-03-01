"""Tests for provider error hierarchy."""

import pytest

from ai_company.providers.errors import (
    AuthenticationError,
    ContentFilterError,
    InvalidRequestError,
    ModelNotFoundError,
    ProviderConnectionError,
    ProviderError,
    ProviderInternalError,
    ProviderTimeoutError,
    RateLimitError,
)

pytestmark = pytest.mark.timeout(30)


@pytest.mark.unit
class TestProviderError:
    """Tests for the base ProviderError."""

    def test_message_stored(self) -> None:
        err = ProviderError("something broke")
        assert err.message == "something broke"

    def test_context_defaults_to_empty(self) -> None:
        err = ProviderError("oops")
        assert err.context == {}

    def test_context_stored(self) -> None:
        ctx = {"provider": "anthropic", "model": "sonnet"}
        err = ProviderError("oops", context=ctx)
        assert err.context == ctx

    def test_str_without_context(self) -> None:
        err = ProviderError("broken")
        assert str(err) == "broken"

    def test_str_with_context(self) -> None:
        err = ProviderError("broken", context={"key": "val"})
        assert "broken" in str(err)
        assert "key='val'" in str(err)

    def test_is_exception(self) -> None:
        assert issubclass(ProviderError, Exception)

    def test_base_not_retryable(self) -> None:
        err = ProviderError("base")
        assert err.is_retryable is False


@pytest.mark.unit
class TestErrorHierarchy:
    """Tests for all typed error subclasses."""

    def test_all_subclass_provider_error(self) -> None:
        subclasses = [
            AuthenticationError,
            RateLimitError,
            ModelNotFoundError,
            InvalidRequestError,
            ContentFilterError,
            ProviderTimeoutError,
            ProviderConnectionError,
            ProviderInternalError,
        ]
        for cls in subclasses:
            assert issubclass(cls, ProviderError)

    @pytest.mark.parametrize(
        ("cls", "expected"),
        [
            (AuthenticationError, False),
            (RateLimitError, True),
            (ModelNotFoundError, False),
            (InvalidRequestError, False),
            (ContentFilterError, False),
            (ProviderTimeoutError, True),
            (ProviderConnectionError, True),
            (ProviderInternalError, True),
        ],
    )
    def test_is_retryable(
        self,
        cls: type[ProviderError],
        expected: bool,
    ) -> None:
        err = cls("test error")
        assert err.is_retryable is expected

    def test_retryable_errors_are_catchable_as_provider_error(self) -> None:
        err = RateLimitError("too fast")
        with pytest.raises(ProviderError):
            raise err

    def test_non_retryable_errors_are_catchable_as_provider_error(self) -> None:
        err = AuthenticationError("bad key")
        with pytest.raises(ProviderError):
            raise err


@pytest.mark.unit
class TestRateLimitError:
    """Tests specific to RateLimitError."""

    def test_retry_after_stored(self) -> None:
        err = RateLimitError("slow down", retry_after=30.0)
        assert err.retry_after == 30.0

    def test_retry_after_defaults_to_none(self) -> None:
        err = RateLimitError("slow down")
        assert err.retry_after is None

    def test_context_passed_through(self) -> None:
        err = RateLimitError(
            "slow down",
            retry_after=5.0,
            context={"provider": "openai"},
        )
        assert err.context == {"provider": "openai"}
        assert err.retry_after == 5.0


@pytest.mark.unit
class TestErrorFormatting:
    """Tests for __str__ formatting across error types."""

    def test_all_errors_include_message_in_str(self) -> None:
        for cls in (
            AuthenticationError,
            RateLimitError,
            ModelNotFoundError,
            InvalidRequestError,
            ContentFilterError,
            ProviderTimeoutError,
            ProviderConnectionError,
            ProviderInternalError,
        ):
            err = cls("test msg", context={"model": "gpt-4"})
            result = str(err)
            assert "test msg" in result
            assert "model='gpt-4'" in result
