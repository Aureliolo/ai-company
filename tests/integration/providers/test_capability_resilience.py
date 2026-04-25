"""Integration tests for retry + rate limiting on capability lookups.

Mirrors ``test_retry_integration.py`` but exercises the
``get_model_capabilities()`` and ``batch_get_capabilities()`` paths.
The CLAUDE.md contract states "all provider calls go through
BaseCompletionProvider" -- these tests assert that capability lookups
honour the same retry handler + rate limiter as ``complete()`` /
``stream()``.

The LiteLLM driver overrides ``batch_get_capabilities`` with a tight
in-process loop over its preset catalog, so tests stub the
``_do_get_model_capabilities`` boundary on the provider directly to
exercise the resilience path that would matter for any future driver
that does network I/O on capability lookups.
"""

import asyncio

import pytest

from synthorg.config.schema import ProviderConfig, ProviderModelConfig
from synthorg.core.resilience_config import RateLimiterConfig, RetryConfig
from synthorg.providers.capabilities import ModelCapabilities
from synthorg.providers.drivers.litellm_driver import LiteLLMDriver
from synthorg.providers.errors import (
    AuthenticationError,
    ProviderTimeoutError,
)
from synthorg.providers.resilience.errors import RetryExhaustedError

pytestmark = pytest.mark.integration


def _make_config(
    *,
    max_retries: int = 2,
    max_requests_per_minute: int = 0,
    max_concurrent: int = 0,
) -> ProviderConfig:
    return ProviderConfig(
        driver="litellm",
        api_key="sk-test-key",
        models=(
            ProviderModelConfig(
                id="test-model-001",
                alias="test-model",
                cost_per_1k_input=0.001,
                cost_per_1k_output=0.002,
            ),
            ProviderModelConfig(
                id="test-model-002",
                alias="test-model-2",
                cost_per_1k_input=0.001,
                cost_per_1k_output=0.002,
            ),
        ),
        retry=RetryConfig(
            max_retries=max_retries,
            base_delay=0.001,
            max_delay=0.01,
            jitter=False,
        ),
        rate_limiter=RateLimiterConfig(
            max_requests_per_minute=max_requests_per_minute,
            max_concurrent=max_concurrent,
        ),
    )


def _stub_capabilities(model_id: str) -> ModelCapabilities:
    return ModelCapabilities(
        model_id=model_id,
        provider="test-provider",
        max_context_tokens=8_000,
        max_output_tokens=2_000,
        cost_per_1k_input=0.001,
        cost_per_1k_output=0.002,
        supports_tools=True,
        supports_vision=False,
    )


class TestGetModelCapabilitiesResilience:
    """``get_model_capabilities`` honours retry + rate-limit budget."""

    async def test_succeeds_after_transient_failure(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Transient ProviderTimeoutError on first call; second succeeds."""
        driver = LiteLLMDriver("test-provider", _make_config())
        call_count = {"n": 0}

        async def _stub_do(model: str) -> ModelCapabilities:
            call_count["n"] += 1
            if call_count["n"] < 2:
                msg = "transient"
                raise ProviderTimeoutError(
                    msg,
                    context={"provider": "test-provider", "model": model},
                )
            return _stub_capabilities(model)

        monkeypatch.setattr(driver, "_do_get_model_capabilities", _stub_do)
        result = await driver.get_model_capabilities("test-model-001")
        assert result.model_id == "test-model-001"
        assert call_count["n"] == 2

    async def test_exhausts_retries_raises_retry_exhausted(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """All attempts raise transient; ``RetryExhaustedError`` propagates."""
        driver = LiteLLMDriver("test-provider", _make_config(max_retries=2))

        async def _stub_do(model: str) -> ModelCapabilities:
            msg = "always transient"
            raise ProviderTimeoutError(
                msg,
                context={"provider": "test-provider", "model": model},
            )

        monkeypatch.setattr(driver, "_do_get_model_capabilities", _stub_do)
        with pytest.raises(RetryExhaustedError) as exc_info:
            await driver.get_model_capabilities("test-model-001")
        assert isinstance(exc_info.value.original_error, ProviderTimeoutError)

    async def test_non_retryable_not_retried(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """``AuthenticationError`` is not retryable; surfaces immediately."""
        driver = LiteLLMDriver("test-provider", _make_config())
        call_count = {"n": 0}

        async def _stub_do(model: str) -> ModelCapabilities:
            call_count["n"] += 1
            msg = "bad key"
            raise AuthenticationError(
                msg,
                context={"provider": "test-provider", "model": model},
            )

        monkeypatch.setattr(driver, "_do_get_model_capabilities", _stub_do)
        with pytest.raises(AuthenticationError):
            await driver.get_model_capabilities("test-model-001")
        assert call_count["n"] == 1

    async def test_consumes_rate_limiter_slot(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """``max_concurrent=1`` serialises two parallel capability lookups.

        Uses an ``asyncio.Lock`` around the counter so the assertion does
        not depend on the rate limiter for atomicity. If the wrap regresses
        to ``max_concurrent=0`` the counter would still update consistently
        and the peak assertion would catch the parallelism.
        """
        driver = LiteLLMDriver(
            "test-provider",
            _make_config(max_concurrent=1),
        )
        in_flight = {"current": 0, "peak": 0}
        counter_lock = asyncio.Lock()

        async def _stub_do(model: str) -> ModelCapabilities:
            async with counter_lock:
                in_flight["current"] += 1
                in_flight["peak"] = max(in_flight["peak"], in_flight["current"])
            await asyncio.sleep(0.01)
            async with counter_lock:
                in_flight["current"] -= 1
            return _stub_capabilities(model)

        monkeypatch.setattr(driver, "_do_get_model_capabilities", _stub_do)
        await asyncio.gather(
            driver.get_model_capabilities("test-model-001"),
            driver.get_model_capabilities("test-model-002"),
        )
        # max_concurrent=1 means only one in-flight at a time.
        assert in_flight["peak"] == 1


class TestBatchGetCapabilitiesResilience:
    """``BaseCompletionProvider.batch_get_capabilities`` default impl."""

    async def test_surfaces_retry_exhausted_via_exception_group(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """``RetryExhaustedError`` propagates out of the TaskGroup batch.

        ``asyncio.TaskGroup`` wraps any in-flight raised exception in an
        ``ExceptionGroup``; the test asserts the wrapper contract
        explicitly so a future refactor that loses the wrapping is
        caught.
        """
        driver = LiteLLMDriver("test-provider", _make_config(max_retries=1))

        async def _stub_do(model: str) -> ModelCapabilities:
            msg = "transient"
            raise ProviderTimeoutError(
                msg,
                context={"provider": "test-provider", "model": model},
            )

        monkeypatch.setattr(driver, "_do_get_model_capabilities", _stub_do)
        # The LiteLLM override has its own in-process batch path; call
        # the base default directly to exercise the per-model fan-out.
        from synthorg.providers.base import BaseCompletionProvider

        with pytest.raises(ExceptionGroup) as exc_info:
            await BaseCompletionProvider.batch_get_capabilities(
                driver,
                ("test-model-001", "test-model-002"),
            )
        inner = exc_info.value.exceptions
        assert any(isinstance(e, RetryExhaustedError) for e in inner)

    @pytest.mark.parametrize(
        "exception_factory",
        [
            pytest.param(MemoryError, id="memory-error"),
            pytest.param(RecursionError, id="recursion-error"),
        ],
    )
    async def test_propagates_resource_exhaustion_errors(
        self,
        monkeypatch: pytest.MonkeyPatch,
        exception_factory: type[BaseException],
    ) -> None:
        """``MemoryError`` / ``RecursionError`` escape uncaught.

        These are bare ``BaseException`` subclasses that signal runtime
        resource exhaustion -- the batch loop must NOT degrade them to
        ``None`` (would silently mask a critical signal).  Verifies the
        ``except (MemoryError, RecursionError, RetryExhaustedError)``
        re-raise path in ``_one()``.
        """
        driver = LiteLLMDriver("test-provider", _make_config(max_retries=0))

        async def _stub_do(model: str) -> ModelCapabilities:
            del model
            raise exception_factory()

        monkeypatch.setattr(driver, "_do_get_model_capabilities", _stub_do)
        from synthorg.providers.base import BaseCompletionProvider

        with pytest.raises(ExceptionGroup) as exc_info:
            await BaseCompletionProvider.batch_get_capabilities(
                driver,
                ("test-model-001",),
            )
        assert any(isinstance(e, exception_factory) for e in exc_info.value.exceptions)

    async def test_swallows_classification_errors(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Per-model non-retryable errors degrade to ``None`` entries."""
        driver = LiteLLMDriver("test-provider", _make_config(max_retries=0))

        async def _stub_do(model: str) -> ModelCapabilities:
            if model == "test-model-001":
                msg = "bad-key"
                raise AuthenticationError(
                    msg,
                    context={"provider": "test-provider", "model": model},
                )
            return _stub_capabilities(model)

        monkeypatch.setattr(driver, "_do_get_model_capabilities", _stub_do)
        from synthorg.providers.base import BaseCompletionProvider

        # Per-model non-retryable errors collapse to ``None`` while the
        # rest of the batch resolves normally -- this is the expected
        # behaviour. Only ``RetryExhaustedError`` / ``MemoryError`` /
        # ``RecursionError`` propagate.
        result = await BaseCompletionProvider.batch_get_capabilities(
            driver,
            ("test-model-001", "test-model-002"),
        )
        assert result["test-model-001"] is None
        assert result["test-model-002"] is not None
        assert result["test-model-002"].model_id == "test-model-002"

    async def test_litellm_driver_batch_unaffected(self) -> None:
        """Sanity: LiteLLM's in-process batch override returns shape-stable."""
        driver = LiteLLMDriver("test-provider", _make_config())
        result = await driver.batch_get_capabilities(("test-model-001",))
        assert "test-model-001" in result
        assert result["test-model-001"] is not None
        assert result["test-model-001"].model_id == "test-model-001"
