"""Extracted helper functions for system prompt construction.

Pure data-building helpers used by :mod:`synthorg.engine.prompt` to assemble
template context and metadata dicts.  Separated to keep ``prompt.py`` under
the 800-line limit.
"""

from typing import TYPE_CHECKING, Any

from synthorg.engine.prompt_template import AUTONOMY_INSTRUCTIONS

if TYPE_CHECKING:
    from synthorg.core.agent import AgentIdentity
    from synthorg.core.role import Role
    from synthorg.security.autonomy.models import EffectiveAutonomy


def build_core_context(
    agent: AgentIdentity,
    role: Role | None,
    effective_autonomy: EffectiveAutonomy | None = None,
) -> dict[str, Any]:
    """Build the core (always-present) template variables from agent identity.

    Args:
        agent: Agent identity.
        role: Optional role with description.
        effective_autonomy: Resolved autonomy for the current run.

    Returns:
        Dict of core template variables.
    """
    personality = agent.personality
    authority = agent.authority

    ctx: dict[str, Any] = {
        "agent_name": agent.name,
        "agent_role": agent.role,
        "agent_department": agent.department,
        "agent_level": agent.level.value,
        "role_description": role.description if role else "",
        "personality_description": personality.description,
        "communication_style": personality.communication_style,
        "risk_tolerance": personality.risk_tolerance.value,
        "creativity": personality.creativity.value,
        "verbosity": personality.verbosity.value,
        "decision_making": personality.decision_making.value,
        "collaboration": personality.collaboration.value,
        "conflict_approach": personality.conflict_approach.value,
        "personality_traits": personality.traits,
        "primary_skills": agent.skills.primary,
        "secondary_skills": agent.skills.secondary,
        "can_approve": authority.can_approve,
        "reports_to": authority.reports_to or "",
        "can_delegate_to": authority.can_delegate_to,
        "budget_limit": authority.budget_limit,
        "autonomy_instructions": AUTONOMY_INSTRUCTIONS[agent.level],
    }

    if effective_autonomy is not None:
        ctx["effective_autonomy"] = {
            "level": effective_autonomy.level.value,
            "auto_approve_actions": sorted(effective_autonomy.auto_approve_actions),
            "human_approval_actions": sorted(effective_autonomy.human_approval_actions),
            "security_agent": effective_autonomy.security_agent,
        }
    else:
        ctx["effective_autonomy"] = None

    return ctx


def build_metadata(agent: AgentIdentity) -> dict[str, str]:
    """Build metadata dict from agent identity.

    Args:
        agent: The agent identity.

    Returns:
        Dict with agent_id, name, role, department, and level.
    """
    return {
        "agent_id": str(agent.id),
        "name": agent.name,
        "role": agent.role,
        "department": agent.department,
        "level": agent.level.value,
    }
