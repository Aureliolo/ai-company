"""Tests for ``load_self_improvement_config``.

Pins the merge semantics: an empty object, missing setting, or malformed
JSON all fall back to code defaults; valid overrides merge onto the
default.
"""

from unittest.mock import AsyncMock, MagicMock

import pytest

from synthorg.meta.config import SelfImprovementConfig, load_self_improvement_config
from synthorg.settings.models import SettingEntry

pytestmark = pytest.mark.unit


def _fake_service(value: str) -> MagicMock:
    """Build a settings-service fake with a single ``get`` entry."""
    service = MagicMock()
    entry = MagicMock(spec=SettingEntry)
    entry.value = value
    service.get = AsyncMock(return_value=entry)
    return service


async def test_missing_service_returns_default() -> None:
    """``None`` service falls back to ``SelfImprovementConfig()`` defaults."""
    config = await load_self_improvement_config(None)
    assert config == SelfImprovementConfig()


async def test_empty_object_returns_default() -> None:
    """``{}`` (the shipped default value) yields pure code defaults."""
    service = _fake_service("{}")
    config = await load_self_improvement_config(service)
    assert config == SelfImprovementConfig()


async def test_malformed_json_falls_back_to_default() -> None:
    """Corrupt JSON never crashes the controller."""
    service = _fake_service("not-json{]}")
    config = await load_self_improvement_config(service)
    assert config == SelfImprovementConfig()


async def test_non_dict_json_falls_back_to_default() -> None:
    """A JSON array (or scalar) is not a valid override envelope."""
    service = _fake_service("[1, 2, 3]")
    config = await load_self_improvement_config(service)
    assert config == SelfImprovementConfig()


async def test_unknown_keys_fall_back_to_default() -> None:
    """Unknown top-level keys fail model validation; loader returns default."""
    service = _fake_service('{"not_a_real_field": true}')
    config = await load_self_improvement_config(service)
    assert config == SelfImprovementConfig()


async def test_valid_override_lands() -> None:
    """A recognized override flips the documented field."""
    service = _fake_service('{"enabled": true, "chief_of_staff_enabled": true}')
    config = await load_self_improvement_config(service)
    assert config.enabled is True
    assert config.chief_of_staff_enabled is True
    # Non-overridden fields keep their defaults.
    assert config.rules == SelfImprovementConfig().rules


async def test_settings_service_error_falls_back_to_default() -> None:
    """A raised get() does not propagate; defaults are always safe."""
    service = MagicMock()
    service.get = AsyncMock(side_effect=RuntimeError("backend unavailable"))
    config = await load_self_improvement_config(service)
    assert config == SelfImprovementConfig()
