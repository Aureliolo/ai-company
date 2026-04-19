"""Org fact store protocol -- re-exported from the persistence layer.

Canonical definition now lives at
``synthorg.persistence.memory_protocol.OrgFactRepository``; this shim
keeps existing imports working until callers migrate to the new name.
"""

from synthorg.persistence.memory_protocol import (
    OrgFactRepository as OrgFactStore,
)

__all__ = ["OrgFactStore"]
