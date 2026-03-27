"""Tests for provider presets."""

import pytest

from synthorg.providers.presets import (
    PROVIDER_PRESETS,
    get_preset,
    list_presets,
)


@pytest.mark.unit
class TestProviderPresets:
    def test_all_presets_valid_provider_configs(self) -> None:
        for preset in PROVIDER_PRESETS:
            assert preset.name
            assert preset.display_name
            assert preset.description
            assert preset.driver

    def test_preset_names_unique(self) -> None:
        names = [p.name for p in PROVIDER_PRESETS]
        assert len(names) == len(set(names))

    def test_get_preset_by_name(self) -> None:
        preset = get_preset("ollama")
        assert preset is not None
        assert preset.display_name == "Ollama"

    def test_get_preset_unknown_returns_none(self) -> None:
        assert get_preset("nonexistent") is None

    def test_list_presets_returns_all(self) -> None:
        presets = list_presets()
        assert len(presets) == len(PROVIDER_PRESETS)
        assert presets == PROVIDER_PRESETS

    def test_local_presets_have_candidate_urls(self) -> None:
        """Local presets with non-colliding ports have candidate URLs.

        vLLM is excluded: its default port (8000) is a common collision
        risk, so candidate_urls are intentionally empty.
        """
        for name in ("ollama", "lm-studio"):
            preset = get_preset(name)
            assert preset is not None, f"Preset {name!r} not found"
            assert len(preset.candidate_urls) > 0, (
                f"Preset {name!r} should have candidate_urls for auto-detection"
            )
            for url in preset.candidate_urls:
                assert url.startswith(("http://", "https://")), (
                    f"candidate_url {url!r} in preset {name!r} must have http(s) scheme"
                )

    def test_vllm_preset_has_no_candidate_urls(self) -> None:
        """vLLM preset must not have candidate_urls (port 8000 collision risk)."""
        preset = get_preset("vllm")
        assert preset is not None
        assert preset.candidate_urls == ()
        assert preset.default_base_url == "http://localhost:8000/v1"

    def test_cloud_presets_have_no_candidate_urls(self) -> None:
        """Cloud presets (openrouter) should not have candidate URLs."""
        preset = get_preset("openrouter")
        assert preset is not None
        assert len(preset.candidate_urls) == 0

    def test_presets_are_frozen(self) -> None:
        from pydantic import ValidationError

        preset = get_preset("ollama")
        assert preset is not None
        with pytest.raises(ValidationError, match="frozen"):
            preset.name = "changed"  # type: ignore[misc]

    def test_auth_type_not_in_supported_raises(self) -> None:
        """Creating a preset with auth_type not in supported_auth_types fails."""
        from pydantic import ValidationError

        from synthorg.providers.enums import AuthType
        from synthorg.providers.presets import ProviderPreset

        with pytest.raises(ValidationError, match=r"auth_type.*not in"):
            ProviderPreset(
                name="test-bad-preset",
                display_name="Bad Preset",
                description="Preset with mismatched auth_type",
                driver="litellm",
                litellm_provider="test",
                auth_type=AuthType.SUBSCRIPTION,
                supported_auth_types=(AuthType.API_KEY,),
            )
