"""Personality preset service layer (MCP-facing facade).

Wraps :class:`PersonalityPresetService` from
``synthorg.templates.preset_service`` so MCP handlers talk to a
facade with the pagination + ``None``-on-missing conventions the rest
of the MCP surface uses. The underlying service keeps its
:class:`NotFoundError`-raising contract for the REST controllers.
"""

from synthorg.hr.personalities.service import PersonalityService

__all__ = ["PersonalityService"]
