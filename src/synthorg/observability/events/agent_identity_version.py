"""Agent identity version event name constants for observability."""

from typing import Final

AGENT_IDENTITY_VERSION_LISTED: Final[str] = "agent.identity.version.listed"
"""Agent identity versions listed via REST API."""

AGENT_IDENTITY_VERSION_FETCHED: Final[str] = "agent.identity.version.fetched"
"""A single agent identity version was fetched."""

AGENT_IDENTITY_VERSION_NOT_FOUND: Final[str] = "agent.identity.version.not_found"
"""Requested agent identity version not found."""

AGENT_IDENTITY_DIFF_COMPUTED: Final[str] = "agent.identity.diff.computed"
"""Diff computed between two agent identity versions."""

AGENT_IDENTITY_INVALID_REQUEST: Final[str] = "agent.identity.version.invalid_request"
"""Request validation failed on an identity version endpoint."""

AGENT_IDENTITY_ROLLED_BACK: Final[str] = "agent.identity.rolled_back"
"""Agent identity rolled back to a previous version."""

AGENT_IDENTITY_ROLLBACK_FAILED: Final[str] = "agent.identity.rollback_failed"
"""Agent identity rollback failed."""

AGENT_IDENTITY_VERSION_OWNER_MISMATCH: Final[str] = (
    "agent.identity.version.owner_mismatch"
)
"""Stored snapshot's owner id does not match the path agent id."""
