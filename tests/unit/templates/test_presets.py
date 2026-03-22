"""Tests for template personality presets and auto-name generation."""

import pytest

from synthorg.core.agent import PersonalityConfig
from synthorg.templates.presets import (
    PERSONALITY_PRESETS,
    generate_auto_name,
    get_personality_preset,
)


@pytest.mark.unit
class TestGetPersonalityPreset:
    def test_valid_preset_returns_dict(self) -> None:
        result = get_personality_preset("visionary_leader")
        assert isinstance(result, dict)
        assert "traits" in result
        assert "communication_style" in result

    def test_case_insensitive(self) -> None:
        result = get_personality_preset("VISIONARY_LEADER")
        assert result == get_personality_preset("visionary_leader")

    def test_whitespace_stripped(self) -> None:
        result = get_personality_preset("  pragmatic_builder  ")
        assert result["communication_style"] == "concise"

    def test_returns_copy(self) -> None:
        a = get_personality_preset("eager_learner")
        b = get_personality_preset("eager_learner")
        assert a == b
        assert a is not b

    def test_unknown_preset_raises_key_error(self) -> None:
        with pytest.raises(KeyError, match="Unknown personality preset"):
            get_personality_preset("nonexistent")

    def test_all_presets_have_required_keys(self) -> None:
        required_keys = {"traits", "communication_style", "description"}
        for name in PERSONALITY_PRESETS:
            preset = get_personality_preset(name)
            assert required_keys.issubset(preset.keys()), f"{name} missing keys"

    def test_preset_count_at_least_20(self) -> None:
        assert len(PERSONALITY_PRESETS) >= 20

    @pytest.mark.parametrize(
        "preset_name",
        [
            "user_advocate",
            "process_optimizer",
            "growth_hacker",
            "technical_communicator",
            "systems_thinker",
        ],
    )
    def test_new_presets_produce_valid_personality_config(
        self,
        preset_name: str,
    ) -> None:
        preset = get_personality_preset(preset_name)
        config = PersonalityConfig(**preset)
        assert isinstance(config, PersonalityConfig)

    def test_all_presets_produce_valid_personality_config(self) -> None:
        for name in PERSONALITY_PRESETS:
            preset = get_personality_preset(name)
            config = PersonalityConfig(**preset)
            assert isinstance(config, PersonalityConfig), f"{name} invalid"

    def test_presets_include_big_five(self) -> None:
        big_five_keys = {
            "openness",
            "conscientiousness",
            "extraversion",
            "agreeableness",
            "stress_response",
        }
        for name in PERSONALITY_PRESETS:
            preset = get_personality_preset(name)
            assert big_five_keys.issubset(preset.keys()), (
                f"{name} missing Big Five keys"
            )


@pytest.mark.unit
class TestGenerateAutoName:
    def test_returns_nonempty_string(self) -> None:
        name = generate_auto_name("CEO", seed=0)
        assert isinstance(name, str)
        assert len(name) > 0

    def test_deterministic_with_seed(self) -> None:
        a = generate_auto_name("Backend Developer", seed=42)
        b = generate_auto_name("Backend Developer", seed=42)
        assert a == b

    def test_different_seeds_may_differ(self) -> None:
        names = {generate_auto_name("CEO", seed=i) for i in range(10)}
        # With 57 locales, should get diverse names.
        assert len(names) >= 2

    def test_accepts_locale_list(self) -> None:
        name = generate_auto_name("CEO", seed=42, locales=["en_US"])
        assert isinstance(name, str)
        assert len(name) > 0

    def test_multiple_locales(self) -> None:
        name = generate_auto_name(
            "CEO",
            seed=42,
            locales=["en_US", "fr_FR", "de_DE"],
        )
        assert isinstance(name, str)
        assert len(name) > 0

    def test_no_seed_still_works(self) -> None:
        name = generate_auto_name("CEO")
        assert isinstance(name, str)
        assert len(name) > 0


@pytest.mark.unit
class TestLocalesModule:
    def test_all_latin_locales_nonempty(self) -> None:
        from synthorg.templates.locales import ALL_LATIN_LOCALES

        assert len(ALL_LATIN_LOCALES) >= 50

    def test_locale_regions_cover_all_locales(self) -> None:
        from synthorg.templates.locales import ALL_LATIN_LOCALES, LOCALE_REGIONS

        region_locales = {loc for locs in LOCALE_REGIONS.values() for loc in locs}
        assert region_locales == set(ALL_LATIN_LOCALES)

    def test_display_names_cover_all_locales(self) -> None:
        from synthorg.templates.locales import ALL_LATIN_LOCALES, LOCALE_DISPLAY_NAMES

        for loc in ALL_LATIN_LOCALES:
            assert loc in LOCALE_DISPLAY_NAMES, f"Missing display name for {loc}"

    def test_resolve_locales_all_sentinel(self) -> None:
        from synthorg.templates.locales import ALL_LATIN_LOCALES, resolve_locales

        result = resolve_locales(["__all__"])
        assert result == list(ALL_LATIN_LOCALES)

    def test_resolve_locales_none(self) -> None:
        from synthorg.templates.locales import ALL_LATIN_LOCALES, resolve_locales

        result = resolve_locales(None)
        assert result == list(ALL_LATIN_LOCALES)

    def test_resolve_locales_specific(self) -> None:
        from synthorg.templates.locales import resolve_locales

        result = resolve_locales(["en_US", "fr_FR"])
        assert result == ["en_US", "fr_FR"]

    def test_resolve_locales_filters_invalid(self) -> None:
        from synthorg.templates.locales import resolve_locales

        result = resolve_locales(["en_US", "invalid_XX", "fr_FR"])
        assert result == ["en_US", "fr_FR"]

    def test_no_deprecated_locales(self) -> None:
        from synthorg.templates.locales import ALL_LATIN_LOCALES

        # fr_QC is deprecated in Faker, should not be in our list
        assert "fr_QC" not in ALL_LATIN_LOCALES
