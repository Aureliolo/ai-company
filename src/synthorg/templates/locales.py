"""Latin-script Faker locale definitions for name generation.

Provides a curated registry of all Faker locales that produce
Latin-script names, grouped by world region for UI presentation.
"""

from types import MappingProxyType
from typing import Final

from synthorg.observability import get_logger

logger = get_logger(__name__)

# Sentinel value meaning "use all Latin-script locales".
ALL_LOCALES_SENTINEL: Final[str] = "__all__"

# Every region and its Faker locale codes.  Order matches the
# intended UI display order (global diversity first, then
# alphabetical within each group).
LOCALE_REGIONS: MappingProxyType[str, tuple[str, ...]] = MappingProxyType(
    {
        "Africa": (
            "en_KE",
            "en_NG",
            "fr_DZ",
            "ha_NG",
            "ig_NG",
            "sw",
            "tw_GH",
            "yo_NG",
            "zu_ZA",
        ),
        "South Asia": (
            "en_IN",
            "en_PK",
        ),
        "Southeast Asia": (
            "en_TH",
            "id_ID",
            "vi_VN",
        ),
        "Central Asia": (
            "az_AZ",
            "uz_UZ",
        ),
        "North America": (
            "en_US",
            "fr_CA",
        ),
        "Central America": ("es_MX",),
        "South America": (
            "es_AR",
            "es_CL",
            "es_CO",
            "pt_BR",
        ),
        "Pacific / Oceania": ("en_NZ",),
        "Western Europe": (
            "de_AT",
            "de_CH",
            "de_DE",
            "de_LI",
            "de_LU",
            "en_GB",
            "en_IE",
            "es_CA",
            "es_ES",
            "fr_BE",
            "fr_CH",
            "fr_FR",
            "ga_IE",
            "it_IT",
            "nl_BE",
            "nl_NL",
            "pt_PT",
        ),
        "Northern Europe": (
            "da_DK",
            "et_EE",
            "fi_FI",
            "is_IS",
            "lt_LT",
            "lv_LV",
            "no_NO",
            "sv_SE",
        ),
        "Central / Eastern Europe": (
            "cs_CZ",
            "hr_HR",
            "hu_HU",
            "pl_PL",
            "ro_RO",
            "sk_SK",
            "sl_SI",
            "tr_TR",
        ),
    }
)

# Flat tuple of every Latin-script locale (derived from LOCALE_REGIONS).
ALL_LATIN_LOCALES: Final[tuple[str, ...]] = tuple(
    locale for locales in LOCALE_REGIONS.values() for locale in locales
)

# Human-readable display names for individual locales.
LOCALE_DISPLAY_NAMES: MappingProxyType[str, str] = MappingProxyType(
    {
        "az_AZ": "Azerbaijani",
        "cs_CZ": "Czech",
        "da_DK": "Danish",
        "de_AT": "German (Austria)",
        "de_CH": "German (Switzerland)",
        "de_DE": "German",
        "de_LI": "German (Liechtenstein)",
        "de_LU": "German (Luxembourg)",
        "en_GB": "English (UK)",
        "en_IE": "English (Ireland)",
        "en_IN": "English (India)",
        "en_KE": "English (Kenya)",
        "en_NG": "English (Nigeria)",
        "en_NZ": "English (New Zealand)",
        "en_PK": "English (Pakistan)",
        "en_TH": "English (Thailand)",
        "en_US": "English (US)",
        "es_AR": "Spanish (Argentina)",
        "es_CA": "Catalan",
        "es_CL": "Spanish (Chile)",
        "es_CO": "Spanish (Colombia)",
        "es_ES": "Spanish (Spain)",
        "es_MX": "Spanish (Mexico)",
        "et_EE": "Estonian",
        "fi_FI": "Finnish",
        "fr_BE": "French (Belgium)",
        "fr_CA": "French (Canada)",
        "fr_CH": "French (Switzerland)",
        "fr_DZ": "French (Algeria)",
        "fr_FR": "French",
        "ga_IE": "Irish",
        "ha_NG": "Hausa (Nigeria)",
        "hr_HR": "Croatian",
        "hu_HU": "Hungarian",
        "id_ID": "Indonesian",
        "ig_NG": "Igbo (Nigeria)",
        "is_IS": "Icelandic",
        "it_IT": "Italian",
        "lt_LT": "Lithuanian",
        "lv_LV": "Latvian",
        "nl_BE": "Dutch (Belgium)",
        "nl_NL": "Dutch",
        "no_NO": "Norwegian",
        "pl_PL": "Polish",
        "pt_BR": "Portuguese (Brazil)",
        "pt_PT": "Portuguese",
        "ro_RO": "Romanian",
        "sk_SK": "Slovak",
        "sl_SI": "Slovenian",
        "sv_SE": "Swedish",
        "sw": "Swahili",
        "tr_TR": "Turkish",
        "tw_GH": "Twi (Ghana)",
        "uz_UZ": "Uzbek",
        "vi_VN": "Vietnamese",
        "yo_NG": "Yoruba (Nigeria)",
        "zu_ZA": "Zulu (South Africa)",
    }
)

# Valid locale codes (for input validation).
VALID_LOCALE_CODES: Final[frozenset[str]] = frozenset(ALL_LATIN_LOCALES)

# Validate registry consistency at import time.
assert len(ALL_LATIN_LOCALES) == len(VALID_LOCALE_CODES), (  # noqa: S101
    f"Duplicate locale codes across regions: "
    f"{len(ALL_LATIN_LOCALES)} total vs {len(VALID_LOCALE_CODES)} unique"
)
_missing_display_names = VALID_LOCALE_CODES - set(LOCALE_DISPLAY_NAMES)
if _missing_display_names:
    msg = f"Locales missing display names: {sorted(_missing_display_names)}"
    raise ValueError(msg)
del _missing_display_names


def resolve_locales(raw: list[str] | None) -> list[str]:
    """Resolve a stored locale list to concrete locale codes.

    Args:
        raw: Stored locale preference.  ``None``, ``[]``, or
            ``["__all__"]`` resolves to all Latin-script locales.

    Returns:
        List of concrete Faker locale codes.
    """
    if not raw or raw == [ALL_LOCALES_SENTINEL]:
        return list(ALL_LATIN_LOCALES)
    valid = []
    dropped = []
    for loc in raw:
        if loc in VALID_LOCALE_CODES:
            valid.append(loc)
        else:
            dropped.append(loc)
    if dropped:
        logger.warning(
            "locales.resolve_dropped_invalid",
            dropped=dropped,
            kept_count=len(valid),
        )
    return valid
