"""Tests for ProviderModelDefaults config (HYG-2)."""

import pytest
from pydantic import ValidationError

from synthorg.providers.defaults_config import ProviderModelDefaults

pytestmark = pytest.mark.unit


class TestProviderModelDefaults:
    """Default fallback values and bounds."""

    def test_default_fallback_is_4096(self) -> None:
        # Matches the previously-inlined literal in
        # ``LiteLLMDriver._do_get_model_capabilities`` so the extraction
        # is a pure refactor -- zero behaviour change on day one.
        assert ProviderModelDefaults().fallback_max_output_tokens == 4096

    def test_frozen(self) -> None:
        cfg = ProviderModelDefaults()
        with pytest.raises(ValidationError):
            cfg.fallback_max_output_tokens = 8192  # type: ignore[misc]

    def test_zero_rejected(self) -> None:
        with pytest.raises(ValidationError, match="fallback_max_output_tokens"):
            ProviderModelDefaults(fallback_max_output_tokens=0)

    def test_negative_rejected(self) -> None:
        with pytest.raises(ValidationError, match="fallback_max_output_tokens"):
            ProviderModelDefaults(fallback_max_output_tokens=-1)

    def test_exceeds_ceiling_rejected(self) -> None:
        with pytest.raises(ValidationError, match="fallback_max_output_tokens"):
            ProviderModelDefaults(fallback_max_output_tokens=32_769)

    def test_at_ceiling_accepted(self) -> None:
        cfg = ProviderModelDefaults(fallback_max_output_tokens=32_768)
        assert cfg.fallback_max_output_tokens == 32_768

    def test_custom_value_accepted(self) -> None:
        # Operators running long-context models can raise the fallback
        # without editing source.
        cfg = ProviderModelDefaults(fallback_max_output_tokens=16_384)
        assert cfg.fallback_max_output_tokens == 16_384
