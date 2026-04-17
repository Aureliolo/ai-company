"""Display namespace setting definitions.

User-facing formatting preferences (locale, and in the future
timezone / number / date formats). Separate from ``budget`` because
the values apply across the entire UI, not just money rendering.
"""

from synthorg.settings.enums import SettingNamespace, SettingType
from synthorg.settings.models import SettingDefinition
from synthorg.settings.registry import get_registry

_r = get_registry()

# BCP 47 language tag. Accepts plain language subtags (e.g. ``en``,
# ``de``), language-region pairs (``en-US``, ``de-CH``), and
# language-script-region (``zh-Hant-HK``). Variant subtags are allowed
# but capped: at most ``_MAX_VARIANT_SUBTAGS`` repetitions keep the
# total tag length under the RFC 5646 ~35-character practical ceiling
# so an operator cannot paste a pathologically long string.
_MAX_VARIANT_SUBTAGS = 3
_BCP47_PATTERN = (
    r"^[A-Za-z]{2,3}"  # language subtag
    r"(?:-[A-Za-z]{4})?"  # optional script subtag
    r"(?:-[A-Za-z]{2}|-[0-9]{3})?"  # optional region subtag
    r"(?:-[A-Za-z0-9]{5,8}|-[0-9][A-Za-z0-9]{3})"  # variant subtag body
    rf"{{0,{_MAX_VARIANT_SUBTAGS}}}"  # up to _MAX_VARIANT_SUBTAGS repetitions
    r"$"
)

_r.register(
    SettingDefinition(
        namespace=SettingNamespace.DISPLAY,
        key="locale",
        type=SettingType.STRING,
        default=None,
        description=(
            "BCP 47 locale tag overriding the browser default for "
            "dates, numbers, and currency rendering (e.g. 'en', "
            "'en-GB', 'de-CH'). Unset means 'follow browser'."
        ),
        group="Formatting",
        validator_pattern=_BCP47_PATTERN,
        yaml_path="display.locale",
    ),
)
