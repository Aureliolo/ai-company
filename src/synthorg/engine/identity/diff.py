"""Agent identity diff -- field-level changes between two AgentIdentity snapshots.

Compares ``model_dump(mode="json")`` representations recursively so nested
sub-models (e.g. ``personality.risk_tolerance``) produce dot-notation paths
like ``personality.risk_tolerance``.
"""

import json
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from synthorg.core.types import NotBlankStr  # noqa: TC001

__all__ = ["AgentIdentityDiff", "IdentityFieldChange", "compute_diff"]


ChangeType = Literal["modified", "added", "removed"]


class IdentityFieldChange(BaseModel):
    """A single field-level change between two identity versions.

    Attributes:
        field_path: Dot-notation path to the changed field (e.g.
            ``personality.risk_tolerance``).
        change_type: Whether the field was modified, added, or removed.
        old_value: JSON-serialized previous value, or ``None`` if added.
        new_value: JSON-serialized new value, or ``None`` if removed.
    """

    model_config = ConfigDict(frozen=True, allow_inf_nan=False)

    field_path: NotBlankStr
    change_type: ChangeType
    old_value: str | None = None
    new_value: str | None = None


class AgentIdentityDiff(BaseModel):
    """Summary of all field-level changes between two identity versions.

    Attributes:
        agent_id: Agent whose identity changed.
        from_version: Version number of the older snapshot.
        to_version: Version number of the newer snapshot.
        field_changes: All detected field changes, ordered by field path.
        summary: Human-readable one-line summary (e.g. ``"2 fields changed"``).
    """

    model_config = ConfigDict(frozen=True, allow_inf_nan=False)

    agent_id: NotBlankStr
    from_version: int = Field(ge=1)
    to_version: int = Field(ge=1)
    field_changes: tuple[IdentityFieldChange, ...] = ()
    summary: str = ""


def _serialize(value: Any) -> str:
    """Return a compact JSON string for a leaf value."""
    return json.dumps(value, sort_keys=True, default=str)


def _diff_dicts(
    old: dict[str, Any],
    new: dict[str, Any],
    prefix: str,
    changes: list[IdentityFieldChange],
) -> None:
    """Recursively compare two dicts and append changes to *changes*."""
    all_keys = old.keys() | new.keys()
    for key in sorted(all_keys):
        path = f"{prefix}.{key}" if prefix else key
        if key not in old:
            changes.append(
                IdentityFieldChange(
                    field_path=path,
                    change_type="added",
                    old_value=None,
                    new_value=_serialize(new[key]),
                )
            )
        elif key not in new:
            changes.append(
                IdentityFieldChange(
                    field_path=path,
                    change_type="removed",
                    old_value=_serialize(old[key]),
                    new_value=None,
                )
            )
        elif isinstance(old[key], dict) and isinstance(new[key], dict):
            _diff_dicts(old[key], new[key], path, changes)
        elif old[key] != new[key]:
            changes.append(
                IdentityFieldChange(
                    field_path=path,
                    change_type="modified",
                    old_value=_serialize(old[key]),
                    new_value=_serialize(new[key]),
                )
            )


def compute_diff(
    agent_id: str,
    old_snapshot: BaseModel,
    new_snapshot: BaseModel,
    from_version: int,
    to_version: int,
) -> AgentIdentityDiff:
    """Compute the field-level diff between two identity snapshots.

    Args:
        agent_id: Agent whose identity changed.
        old_snapshot: The older ``AgentIdentity`` (or any frozen Pydantic model).
        new_snapshot: The newer ``AgentIdentity``.
        from_version: Version number of the older snapshot.
        to_version: Version number of the newer snapshot.

    Returns:
        An :class:`AgentIdentityDiff` listing every changed field.
    """
    old_dict: dict[str, Any] = old_snapshot.model_dump(mode="json")
    new_dict: dict[str, Any] = new_snapshot.model_dump(mode="json")

    changes: list[IdentityFieldChange] = []
    _diff_dicts(old_dict, new_dict, "", changes)

    n = len(changes)
    if n == 0:
        summary = "no changes"
    elif n == 1:
        summary = "1 field changed"
    else:
        summary = f"{n} fields changed"

    return AgentIdentityDiff(
        agent_id=agent_id,
        from_version=from_version,
        to_version=to_version,
        field_changes=tuple(changes),
        summary=summary,
    )
