"""Tests for template personality presets and auto-name generation."""

import pytest

from synthorg.core.agent import PersonalityConfig
from synthorg.core.enums import (
    CollaborationPreference,
    ConflictApproach,
    DecisionMakingStyle,
    RiskTolerance,
)
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

    def test_preset_count_is_23(self) -> None:
        assert len(PERSONALITY_PRESETS) == 23

    def test_client_advisor_profile(self) -> None:
        preset = get_personality_preset("client_advisor")
        config = PersonalityConfig(**preset)
        assert config.agreeableness >= 0.7
        assert config.collaboration == CollaborationPreference.TEAM
        assert config.decision_making == DecisionMakingStyle.CONSULTATIVE
        assert config.communication_style == "warm"
        assert "consultative" in config.traits

    def test_code_craftsman_profile(self) -> None:
        preset = get_personality_preset("code_craftsman")
        config = PersonalityConfig(**preset)
        assert config.conscientiousness >= 0.85
        assert config.risk_tolerance == RiskTolerance.LOW
        assert config.collaboration == CollaborationPreference.PAIR
        assert config.communication_style == "precise"
        assert "meticulous" in config.traits

    def test_devil_advocate_profile(self) -> None:
        preset = get_personality_preset("devil_advocate")
        config = PersonalityConfig(**preset)
        assert config.agreeableness <= 0.3
        assert config.conflict_approach == ConflictApproach.COMPETE
        assert config.collaboration == CollaborationPreference.INDEPENDENT
        assert config.communication_style == "direct"
        assert "contrarian" in config.traits

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

    def test_role_does_not_affect_output(self) -> None:
        """Role parameter is unused -- same seed produces same name."""
        a = generate_auto_name("CEO", seed=42)
        b = generate_auto_name("CFO", seed=42)
        assert a == b


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

    def test_resolve_locales_empty_list(self) -> None:
        """Empty list is falsy, so resolve_locales returns all locales."""
        from synthorg.templates.locales import ALL_LATIN_LOCALES, resolve_locales

        result = resolve_locales([])
        assert result == list(ALL_LATIN_LOCALES)

    def test_resolve_locales_all_invalid(self) -> None:
        """All invalid locale codes are filtered out, returning empty list."""
        from synthorg.templates.locales import resolve_locales

        result = resolve_locales(["invalid_XX", "bogus_YY"])
        assert result == []
