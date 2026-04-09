"""Unit tests for strategic lenses."""

import pytest

from synthorg.engine.strategy.lenses import (
    DEFAULT_LENSES,
    LENS_DEFINITIONS,
    LensDefinition,
    StrategicLens,
    get_lens_definitions,
)


class TestStrategicLens:
    """Tests for the StrategicLens enum."""

    @pytest.mark.unit
    def test_has_eight_members(self) -> None:
        assert len(StrategicLens) == 8

    @pytest.mark.unit
    def test_default_lenses(self) -> None:
        assert StrategicLens.CONTRARIAN in DEFAULT_LENSES
        assert StrategicLens.RISK_FOCUSED in DEFAULT_LENSES
        assert StrategicLens.COST_FOCUSED in DEFAULT_LENSES
        assert StrategicLens.STATUS_QUO in DEFAULT_LENSES
        assert len(DEFAULT_LENSES) == 4


class TestLensDefinitions:
    """Tests for the lens definitions registry."""

    @pytest.mark.unit
    def test_all_lenses_defined(self) -> None:
        for lens in StrategicLens:
            assert lens in LENS_DEFINITIONS

    @pytest.mark.unit
    def test_definitions_are_lens_definition_type(self) -> None:
        for defn in LENS_DEFINITIONS.values():
            assert isinstance(defn, LensDefinition)

    @pytest.mark.unit
    def test_default_lenses_have_is_default_true(self) -> None:
        for lens in DEFAULT_LENSES:
            assert LENS_DEFINITIONS[lens].is_default is True

    @pytest.mark.unit
    def test_optional_lenses_have_is_default_false(self) -> None:
        optional = set(StrategicLens) - set(DEFAULT_LENSES)
        for lens in optional:
            assert LENS_DEFINITIONS[lens].is_default is False

    @pytest.mark.unit
    def test_all_definitions_have_prompt_fragments(self) -> None:
        for defn in LENS_DEFINITIONS.values():
            assert len(defn.prompt_fragment) > 10


class TestGetLensDefinitions:
    """Tests for the get_lens_definitions lookup function."""

    @pytest.mark.unit
    def test_valid_lookup(self) -> None:
        defs = get_lens_definitions(("contrarian", "risk_focused"))
        assert len(defs) == 2
        assert defs[0].name == "Contrarian"

    @pytest.mark.unit
    def test_case_insensitive(self) -> None:
        defs = get_lens_definitions(("CONTRARIAN",))
        assert len(defs) == 1

    @pytest.mark.unit
    def test_unknown_lens_raises(self) -> None:
        with pytest.raises(KeyError, match="Unknown lens"):
            get_lens_definitions(("nonexistent",))

    @pytest.mark.unit
    def test_empty_input(self) -> None:
        defs = get_lens_definitions(())
        assert defs == ()
