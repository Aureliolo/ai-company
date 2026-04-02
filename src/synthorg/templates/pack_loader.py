"""Template pack loading from built-in and user directory sources.

Packs are small, focused template fragments (same schema as full
templates) that can be applied additively to a running org or
composed into templates via the ``uses_packs`` field.

Discovery mirrors the template loader: built-in packs ship inside
the ``synthorg.templates.packs`` package, and user packs live in
``~/.synthorg/template-packs/``.
"""

from dataclasses import dataclass
from importlib import resources
from pathlib import Path
from types import MappingProxyType
from typing import Literal

from synthorg.config.errors import ConfigLocation
from synthorg.observability import get_logger
from synthorg.observability.events.template import (
    TEMPLATE_PACK_LIST,
    TEMPLATE_PACK_LOAD_NOT_FOUND,
    TEMPLATE_PACK_LOAD_START,
    TEMPLATE_PACK_LOAD_SUCCESS,
)
from synthorg.templates.errors import (
    TemplateNotFoundError,
    TemplateRenderError,
    TemplateValidationError,
)
from synthorg.templates.loader import LoadedTemplate

logger = get_logger(__name__)

_USER_PACKS_DIR = Path.home() / ".synthorg" / "template-packs"

BUILTIN_PACKS: MappingProxyType[str, str] = MappingProxyType(
    {
        "security-team": "security-team.yaml",
        "data-team": "data-team.yaml",
        "qa-pipeline": "qa-pipeline.yaml",
        "creative-marketing": "creative-marketing.yaml",
        "design-team": "design-team.yaml",
    }
)


@dataclass(frozen=True)
class PackInfo:
    """Summary information about an available template pack.

    Attributes:
        name: Pack identifier (e.g. ``"security-team"``).
        display_name: Human-readable display name.
        description: Short description.
        source: Where the pack was found.
        tags: Free-form categorization tags.
        agent_count: Number of agents defined in the pack.
        department_count: Number of departments defined in the pack.
    """

    name: str
    display_name: str
    description: str
    source: Literal["builtin", "user"]
    tags: tuple[str, ...] = ()
    agent_count: int = 0
    department_count: int = 0


def list_builtin_packs() -> tuple[str, ...]:
    """Return names of all built-in packs.

    Returns:
        Sorted tuple of built-in pack names.
    """
    return tuple(sorted(BUILTIN_PACKS))


def list_packs() -> tuple[PackInfo, ...]:
    """Return all available packs (user directory + built-in).

    User packs override built-in ones by name. Sorted by name.

    Returns:
        Sorted tuple of :class:`PackInfo` objects.
    """
    seen: dict[str, PackInfo] = {}

    # User packs (higher priority).
    _collect_user_packs(seen)

    # Built-in packs (lower priority).
    for name in sorted(BUILTIN_PACKS):
        if name not in seen:
            try:
                loaded = _load_builtin(name)
                seen[name] = _pack_info_from_loaded(name, loaded, "builtin")
            except (
                TemplateRenderError,
                TemplateValidationError,
                OSError,
            ) as exc:
                logger.warning(
                    TEMPLATE_PACK_LIST,
                    pack_name=name,
                    action="skip_invalid",
                    error=str(exc),
                )

    return tuple(info for _, info in sorted(seen.items()))


def load_pack(name: str) -> LoadedTemplate:
    """Load a template pack by name: user directory first, then builtins.

    Args:
        name: Pack name (e.g. ``"security-team"``).

    Returns:
        :class:`LoadedTemplate` with validated data and raw YAML.

    Raises:
        TemplateNotFoundError: If no pack with *name* exists.
    """
    name_clean = name.strip().lower()
    logger.debug(TEMPLATE_PACK_LOAD_START, pack_name=name_clean)

    # Sanitize to prevent path traversal (OS-independent).
    if "/" in name_clean or "\\" in name_clean or ".." in name_clean:
        msg = f"Invalid pack name {name!r}: must not contain path separators"
        logger.warning(TEMPLATE_PACK_LOAD_NOT_FOUND, pack_name=name)
        raise TemplateNotFoundError(
            msg,
            locations=(ConfigLocation(file_path=f"<pack:{name}>"),),
        )

    # Try user directory first.
    if _USER_PACKS_DIR.is_dir():
        user_path = _USER_PACKS_DIR / f"{name_clean}.yaml"
        if user_path.is_file():
            result = _load_from_file(user_path)
            logger.debug(
                TEMPLATE_PACK_LOAD_SUCCESS,
                pack_name=name_clean,
                source="user",
            )
            return result

    # Fall back to builtins.
    if name_clean in BUILTIN_PACKS:
        result = _load_builtin(name_clean)
        logger.debug(
            TEMPLATE_PACK_LOAD_SUCCESS,
            pack_name=name_clean,
            source="builtin",
        )
        return result

    available = list_builtin_packs()
    logger.warning(
        TEMPLATE_PACK_LOAD_NOT_FOUND,
        pack_name=name,
        available=list(available),
    )
    msg = f"Unknown template pack {name!r}. Available: {list(available)}"
    raise TemplateNotFoundError(
        msg,
        locations=(ConfigLocation(file_path=f"<pack:{name}>"),),
    )


# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------


def _pack_info_from_loaded(
    name: str,
    loaded: LoadedTemplate,
    source: Literal["builtin", "user"],
) -> PackInfo:
    """Build a :class:`PackInfo` from a loaded pack."""
    meta = loaded.template.metadata
    return PackInfo(
        name=name,
        display_name=meta.name,
        description=meta.description,
        source=source,
        tags=meta.tags,
        agent_count=len(loaded.template.agents),
        department_count=len(loaded.template.departments),
    )


def _collect_user_packs(seen: dict[str, PackInfo]) -> None:
    """Scan user packs directory and populate *seen*."""
    if not _USER_PACKS_DIR.is_dir():
        return
    for path in sorted(p for p in _USER_PACKS_DIR.glob("*.yaml") if p.is_file()):
        name = path.stem
        try:
            loaded = _load_from_file(path)
            seen[name] = _pack_info_from_loaded(name, loaded, "user")
        except (
            TemplateRenderError,
            TemplateValidationError,
            OSError,
        ) as exc:
            logger.warning(
                TEMPLATE_PACK_LIST,
                pack_path=str(path),
                action="skip_invalid",
                error=str(exc),
            )


def _load_builtin(name: str) -> LoadedTemplate:
    """Load a built-in pack by name."""
    # Import here to avoid circular dependency at module level.
    from synthorg.templates.loader import (  # noqa: PLC0415
        _parse_template_yaml,
    )

    filename = BUILTIN_PACKS.get(name)
    if filename is None:
        msg = f"Unknown built-in pack: {name!r}"
        logger.warning(TEMPLATE_PACK_LOAD_NOT_FOUND, pack_name=name)
        raise TemplateNotFoundError(
            msg,
            locations=(ConfigLocation(file_path=f"<builtin-pack:{name}>"),),
        )
    source_name = f"<builtin-pack:{name}>"
    try:
        ref = resources.files("synthorg.templates.packs") / filename
        yaml_text = ref.read_text(encoding="utf-8")
    except (OSError, ImportError, TypeError) as exc:
        msg = f"Failed to read built-in pack resource {filename!r}: {exc}"
        logger.exception(
            TEMPLATE_PACK_LOAD_NOT_FOUND,
            source=source_name,
            error=str(exc),
        )
        raise TemplateRenderError(
            msg,
            locations=(ConfigLocation(file_path=source_name),),
        ) from exc
    template = _parse_template_yaml(yaml_text, source_name=source_name)
    return LoadedTemplate(
        template=template,
        raw_yaml=yaml_text,
        source_name=source_name,
    )


def _load_from_file(path: Path) -> LoadedTemplate:
    """Load a pack from a file path."""
    from synthorg.templates.loader import (  # noqa: PLC0415
        _parse_template_yaml,
    )

    source_name = str(path)
    try:
        yaml_text = path.read_text(encoding="utf-8")
    except OSError as exc:
        msg = f"Unable to read pack file: {path}"
        logger.warning(
            TEMPLATE_PACK_LOAD_NOT_FOUND,
            path=str(path),
            error=str(exc),
        )
        raise TemplateRenderError(
            msg,
            locations=(ConfigLocation(file_path=source_name),),
        ) from exc
    except UnicodeDecodeError as exc:
        msg = f"Pack file is not valid UTF-8: {path}"
        logger.warning(
            TEMPLATE_PACK_LOAD_NOT_FOUND,
            path=str(path),
            error=str(exc),
        )
        raise TemplateRenderError(
            msg,
            locations=(ConfigLocation(file_path=source_name),),
        ) from exc
    template = _parse_template_yaml(yaml_text, source_name=source_name)
    return LoadedTemplate(
        template=template,
        raw_yaml=yaml_text,
        source_name=source_name,
    )
