"""Tests for the ``display`` namespace setting definitions."""

import re

import pytest

import synthorg.settings.definitions  # noqa: F401 -- trigger registration
from synthorg.settings.definitions.display import _BCP47_PATTERN
from synthorg.settings.enums import SettingNamespace, SettingType
from synthorg.settings.registry import get_registry

pytestmark = pytest.mark.unit


class TestDisplayLocaleDefinition:
    """The ``display.locale`` setting exists and has the expected shape."""

    def test_registered(self) -> None:
        defn = get_registry().get(SettingNamespace.DISPLAY, "locale")
        assert defn is not None
        assert defn.type == SettingType.STRING
        # Unset default means "follow browser"; having an explicit
        # fallback here would bias the system toward one locale.
        assert defn.default is None

    def test_yaml_path(self) -> None:
        defn = get_registry().get(SettingNamespace.DISPLAY, "locale")
        assert defn is not None
        assert defn.yaml_path == "display.locale"


class TestBcp47Pattern:
    """The BCP 47 validator accepts common tags and rejects garbage."""

    _pattern = re.compile(_BCP47_PATTERN)

    @pytest.mark.parametrize(
        "tag",
        [
            "en",
            "de",
            "fr",
            "zh",
            "en-US",
            "en-GB",
            "de-CH",
            "fr-FR",
            "pt-BR",
            "zh-Hant-HK",
            "zh-Hans-CN",
            "sr-Latn-RS",
            "es-419",
        ],
    )
    def test_accepts_valid_tags(self, tag: str) -> None:
        assert self._pattern.fullmatch(tag) is not None

    @pytest.mark.parametrize(
        "tag",
        [
            "",
            "english",  # language subtag too long
            "en_US",  # underscore separator is invalid in BCP 47
            "en-",  # dangling separator
            "-US",
            "12-US",  # language subtag must be alpha
            "!!!",
            # Pathological: four variant subtags exceeds the cap.
            # Keeps the total tag length bounded so a config-edit-
            # capable operator cannot paste hundreds of subtags.
            "en-variant1-variant2-variant3-variant4",
        ],
    )
    def test_rejects_invalid_tags(self, tag: str) -> None:
        assert self._pattern.fullmatch(tag) is None
