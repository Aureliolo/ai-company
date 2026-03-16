"""Unit tests for the settings registry."""

import pytest

from synthorg.settings.enums import SettingNamespace, SettingType
from synthorg.settings.models import SettingDefinition
from synthorg.settings.registry import SettingsRegistry


def _make_definition(
    *,
    namespace: SettingNamespace = SettingNamespace.BUDGET,
    key: str = "total_monthly",
    **kwargs: object,
) -> SettingDefinition:
    """Create a SettingDefinition with sensible defaults."""
    defaults: dict[str, object] = {
        "type": SettingType.FLOAT,
        "description": "test setting",
        "group": "test",
    }
    defaults.update(kwargs)
    return SettingDefinition(namespace=namespace, key=key, **defaults)  # type: ignore[arg-type]


@pytest.mark.unit
class TestSettingsRegistry:
    """Tests for SettingsRegistry CRUD operations."""

    def test_register_and_get(self) -> None:
        registry = SettingsRegistry()
        defn = _make_definition()
        registry.register(defn)
        result = registry.get("budget", "total_monthly")
        assert result is defn

    def test_get_returns_none_for_missing(self) -> None:
        registry = SettingsRegistry()
        assert registry.get("budget", "nonexistent") is None

    def test_duplicate_registration_raises(self) -> None:
        registry = SettingsRegistry()
        defn = _make_definition()
        registry.register(defn)
        with pytest.raises(ValueError, match="Duplicate setting"):
            registry.register(defn)

    def test_list_namespace(self) -> None:
        registry = SettingsRegistry()
        registry.register(_make_definition(key="b_setting"))
        registry.register(_make_definition(key="a_setting"))
        registry.register(
            _make_definition(
                namespace=SettingNamespace.SECURITY,
                key="enabled",
            )
        )
        budget_defs = registry.list_namespace("budget")
        assert len(budget_defs) == 2
        assert budget_defs[0].key == "a_setting"
        assert budget_defs[1].key == "b_setting"

    def test_list_namespace_empty(self) -> None:
        registry = SettingsRegistry()
        assert registry.list_namespace("nonexistent") == ()

    def test_list_all(self) -> None:
        registry = SettingsRegistry()
        registry.register(_make_definition(key="total_monthly"))
        registry.register(
            _make_definition(
                namespace=SettingNamespace.SECURITY,
                key="enabled",
            )
        )
        all_defs = registry.list_all()
        assert len(all_defs) == 2
        # Sorted by (namespace, key)
        assert all_defs[0].namespace == SettingNamespace.BUDGET
        assert all_defs[1].namespace == SettingNamespace.SECURITY

    def test_namespaces(self) -> None:
        registry = SettingsRegistry()
        registry.register(_make_definition(key="total_monthly"))
        registry.register(
            _make_definition(
                namespace=SettingNamespace.SECURITY,
                key="enabled",
            )
        )
        ns = registry.namespaces()
        assert ns == ("budget", "security")

    def test_namespaces_empty(self) -> None:
        registry = SettingsRegistry()
        assert registry.namespaces() == ()

    def test_size(self) -> None:
        registry = SettingsRegistry()
        assert registry.size == 0
        registry.register(_make_definition(key="a"))
        assert registry.size == 1
        registry.register(_make_definition(key="b"))
        assert registry.size == 2
