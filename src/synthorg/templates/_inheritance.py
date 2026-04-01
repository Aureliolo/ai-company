"""Template inheritance resolution.

Handles parent chain loading, circular detection, depth limits,
parent-child merge, variable flow, and post-merge name deduplication.
Extracted from ``renderer.py`` to keep file sizes under 800 lines.
"""

from typing import TYPE_CHECKING, Any, Protocol

from synthorg.observability import get_logger
from synthorg.observability.events.template import (
    TEMPLATE_INHERIT_CIRCULAR,
    TEMPLATE_INHERIT_DEPTH_EXCEEDED,
    TEMPLATE_INHERIT_MERGE_ERROR,
    TEMPLATE_INHERIT_RESOLVE_START,
    TEMPLATE_INHERIT_RESOLVE_SUCCESS,
)
from synthorg.templates.errors import TemplateInheritanceError
from synthorg.templates.merge import merge_template_configs

if TYPE_CHECKING:
    from collections.abc import Mapping

    from synthorg.templates.loader import LoadedTemplate
    from synthorg.templates.schema import CompanyTemplate


class _RenderToDictFn(Protocol):
    """Callback protocol for ``_render_to_dict``."""

    def __call__(
        self,
        loaded: LoadedTemplate,
        variables: dict[str, Any] | None = ...,
        *,
        locales: list[str] | None = ...,
        _chain: frozenset[str] = ...,
        custom_presets: Mapping[str, dict[str, Any]] | None = ...,
        _as_parent: bool = ...,
    ) -> dict[str, Any]: ...


logger = get_logger(__name__)

# Maximum inheritance chain depth.
_MAX_INHERITANCE_DEPTH = 10


def resolve_inheritance(  # noqa: PLR0913
    *,
    child_config: dict[str, Any],
    loaded: LoadedTemplate,
    vars_dict: dict[str, Any],
    locales: list[str] | None = None,
    _chain: frozenset[str],
    custom_presets: Mapping[str, dict[str, Any]] | None = None,
    render_to_dict_fn: _RenderToDictFn,
) -> dict[str, Any]:
    """Resolve template inheritance for a child config.

    Loads and renders the parent, detects circular dependencies and
    depth violations, then merges parent + child.

    Args:
        child_config: Already-rendered child config dict.
        loaded: The child's :class:`LoadedTemplate`.
        vars_dict: Child's resolved variables.
        locales: Faker locale codes for auto-name generation.
        _chain: Already-visited parent names for circular detection.
        custom_presets: Optional custom preset mapping.
        render_to_dict_fn: Callback to ``_render_to_dict``.

    Returns:
        Merged config dict (parent + child).

    Raises:
        TemplateInheritanceError: On circular chains or depth overflow.
    """
    if loaded.template.extends is None:
        msg = (
            f"resolve_inheritance called for {loaded.source_name!r} "
            "but template has no 'extends' -- caller contract violated"
        )
        logger.error(
            TEMPLATE_INHERIT_MERGE_ERROR,
            action="resolve_no_extends",
            template=loaded.source_name,
        )
        raise TemplateInheritanceError(msg)
    parent_name: str = loaded.template.extends
    child_id = loaded.source_name

    logger.info(
        TEMPLATE_INHERIT_RESOLVE_START,
        child=child_id,
        parent=parent_name,
    )

    _validate_inheritance_chain(child_id, parent_name, _chain)

    merged = _render_and_merge_parent(
        parent_name,
        child_config,
        vars_dict,
        _chain,
        locales=locales,
        custom_presets=custom_presets,
        render_to_dict_fn=render_to_dict_fn,
    )

    # Deduplicate agent names that may collide across parent/child
    # expansion passes (each pass auto-generates names independently).
    _deduplicate_merged_agent_names(merged)

    logger.info(
        TEMPLATE_INHERIT_RESOLVE_SUCCESS,
        child=child_id,
        parent=parent_name,
    )
    return merged


def _validate_inheritance_chain(
    child_id: str,
    parent_name: str,
    _chain: frozenset[str],
) -> None:
    """Check for circular inheritance and depth overflow."""
    if parent_name in _chain:
        logger.error(
            TEMPLATE_INHERIT_CIRCULAR,
            child=child_id,
            parent=parent_name,
            chain=sorted(_chain),
        )
        msg = (
            f"Circular template inheritance: {child_id!r} extends "
            f"{parent_name!r}, which is already in the inheritance chain"
        )
        raise TemplateInheritanceError(msg)

    if len(_chain) >= _MAX_INHERITANCE_DEPTH:
        logger.error(
            TEMPLATE_INHERIT_DEPTH_EXCEEDED,
            child=child_id,
            depth=len(_chain),
            max_depth=_MAX_INHERITANCE_DEPTH,
        )
        msg = (
            f"Template inheritance depth exceeded ({len(_chain)} >= "
            f"{_MAX_INHERITANCE_DEPTH}): {child_id!r}"
        )
        raise TemplateInheritanceError(msg)


def _render_and_merge_parent(  # noqa: PLR0913
    parent_name: str,
    child_config: dict[str, Any],
    vars_dict: dict[str, Any],
    _chain: frozenset[str],
    *,
    locales: list[str] | None = None,
    custom_presets: Mapping[str, dict[str, Any]] | None = None,
    render_to_dict_fn: _RenderToDictFn,
) -> dict[str, Any]:
    """Load, render, and merge a parent template with a child config."""
    from synthorg.templates.loader import load_template  # noqa: PLC0415

    parent_loaded = load_template(parent_name)
    parent_vars = collect_parent_variables(
        parent_loaded.template,
        vars_dict,
    )
    parent_config = render_to_dict_fn(
        parent_loaded,
        parent_vars,
        locales=locales,
        _chain=_chain | {parent_name},
        custom_presets=custom_presets,
        _as_parent=True,
    )
    return merge_template_configs(parent_config, child_config)


def _deduplicate_merged_agent_names(merged: dict[str, Any]) -> None:
    """Ensure agent names are unique after merging parent + child.

    Parent and child agent names are auto-generated independently, so
    collisions can occur.  This mirrors the per-pass deduplication in
    ``_expand_single_agent`` but operates on the post-merge agent list.

    Mutates ``merged`` in place.

    Args:
        merged: Post-merge config dict; its ``agents`` list is modified
            directly.
    """
    agents = merged.get("agents")
    if not agents:
        return
    used: set[str] = set()
    for agent in agents:
        name = agent.get("name", "")
        if not name:
            continue
        if name in used:
            base = name
            counter = 2
            while name in used:
                name = f"{base} {counter}"
                counter += 1
            agent["name"] = name
        used.add(name)


def collect_parent_variables(
    parent_template: CompanyTemplate,
    child_vars: dict[str, Any],
) -> dict[str, Any]:
    """Collect variables for a parent template.

    Child's resolved variables take priority over the parent's own
    defaults.  Parent-declared defaults fill any remaining gaps.

    Args:
        parent_template: The parent template.
        child_vars: Child's resolved variables.

    Returns:
        Variable dict for parent rendering.
    """
    result: dict[str, Any] = dict(child_vars)
    for var in parent_template.variables:
        if var.name not in result and var.default is not None:
            result[var.name] = var.default
    return result
