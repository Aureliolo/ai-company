"""Agent identity versioning service layer.

Lifts the read-path of :class:`AgentIdentityVersionController`
(``api/controllers/agent_identity_versions.py``) into a reusable
service so MCP handlers and REST controllers can share one enforced
contract over the identity version repository.
"""

from synthorg.hr.identity.version_service import AgentVersionService

__all__ = ["AgentVersionService"]
