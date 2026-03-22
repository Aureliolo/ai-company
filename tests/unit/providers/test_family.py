"""Tests for provider family utilities."""

from unittest.mock import MagicMock

import pytest

from synthorg.providers.family import get_family, providers_excluding_family


def _mock_config(family: str | None = None) -> MagicMock:
    config = MagicMock()
    config.family = family
    return config


# -- get_family ------------------------------------------------------------


@pytest.mark.unit
def test_get_family_returns_explicit_family() -> None:
    configs = {"prov-a": _mock_config(family="family-a")}
    assert get_family("prov-a", configs) == "family-a"


@pytest.mark.unit
def test_get_family_falls_back_to_provider_name() -> None:
    configs = {"prov-a": _mock_config(family=None)}
    assert get_family("prov-a", configs) == "prov-a"


@pytest.mark.unit
def test_get_family_unknown_provider_returns_name() -> None:
    assert get_family("unknown", {}) == "unknown"


# -- providers_excluding_family --------------------------------------------


@pytest.mark.unit
def test_excludes_matching_family() -> None:
    configs = {
        "prov-a": _mock_config(family="family-a"),
        "prov-b": _mock_config(family="family-b"),
        "prov-c": _mock_config(family="family-a"),
    }
    result = providers_excluding_family("family-a", configs)
    assert result == ("prov-b",)


@pytest.mark.unit
def test_excludes_all_when_only_one_family() -> None:
    configs = {
        "prov-a": _mock_config(family="family-a"),
        "prov-b": _mock_config(family="family-a"),
    }
    result = providers_excluding_family("family-a", configs)
    assert result == ()


@pytest.mark.unit
def test_returns_all_when_no_match() -> None:
    configs = {
        "prov-a": _mock_config(family="family-b"),
        "prov-b": _mock_config(family="family-c"),
    }
    result = providers_excluding_family("family-a", configs)
    assert result == ("prov-a", "prov-b")


@pytest.mark.unit
def test_empty_configs_returns_empty() -> None:
    result = providers_excluding_family("family-a", {})
    assert result == ()


@pytest.mark.unit
def test_family_defaults_to_provider_name_in_exclusion() -> None:
    """Provider without explicit family uses name as family."""
    configs = {
        "prov-a": _mock_config(family=None),
        "prov-b": _mock_config(family=None),
    }
    result = providers_excluding_family("prov-a", configs)
    assert result == ("prov-b",)
