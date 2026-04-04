"""Unit tests for engine namespace setting definitions."""

import pytest

import synthorg.settings.definitions  # noqa: F401 -- trigger registration
from synthorg.settings.enums import SettingNamespace, SettingType
from synthorg.settings.registry import get_registry


@pytest.mark.unit
class TestEngineSettingDefinitions:
    """Tests for engine namespace settings registration."""

    def test_engine_namespace_exists(self) -> None:
        """ENGINE namespace is registered in the settings registry."""
        registry = get_registry()
        assert SettingNamespace.ENGINE.value in registry.namespaces()

    def test_personality_trimming_enabled_registered(self) -> None:
        """personality_trimming_enabled is a BOOLEAN setting."""
        defn = get_registry().get("engine", "personality_trimming_enabled")

        assert defn is not None
        assert defn.type == SettingType.BOOLEAN
        assert defn.default == "true"

    def test_personality_max_tokens_override_registered(self) -> None:
        """personality_max_tokens_override is an INTEGER setting."""
        defn = get_registry().get("engine", "personality_max_tokens_override")

        assert defn is not None
        assert defn.type == SettingType.INTEGER
        assert defn.default == "0"
        assert defn.min_value == 0
        assert defn.max_value == 10000

    def test_engine_settings_count(self) -> None:
        """Engine namespace has exactly 2 settings."""
        registry = get_registry()
        engine_defs = [
            d
            for d in registry.list_all()
            if d.namespace == SettingNamespace.ENGINE.value
        ]
        assert len(engine_defs) == 2
