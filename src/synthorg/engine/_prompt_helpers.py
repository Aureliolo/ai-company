"""Extracted helper functions for system prompt construction.

Pure data-building helpers used by :mod:`synthorg.engine.prompt` to assemble
template context, metadata dicts, and section tracking.  Separated to keep
``prompt.py`` under the 800-line limit.
"""

from types import MappingProxyType
from typing import TYPE_CHECKING, Any

from synthorg.core.enums import SeniorityLevel  # noqa: TC001 -- used in type annotation
from synthorg.engine.prompt_template import (
    AUTONOMY_INSTRUCTIONS,
    AUTONOMY_MINIMAL,
    AUTONOMY_SUMMARY,
)

if TYPE_CHECKING:
    from synthorg.core.agent import AgentIdentity
    from synthorg.core.role import Role
    from synthorg.engine.prompt_profiles import PromptProfile
    from synthorg.providers.models import ToolDefinition
    from synthorg.security.autonomy.models import EffectiveAutonomy

_AUTONOMY_LOOKUP: MappingProxyType[str, dict[SeniorityLevel, str]] = MappingProxyType(
    {
        "full": AUTONOMY_INSTRUCTIONS,
        "summary": AUTONOMY_SUMMARY,
        "minimal": AUTONOMY_MINIMAL,
    },
)

# ── Section names ────────────────────────────────────────────────

SECTION_IDENTITY = "identity"
SECTION_PERSONALITY = "personality"
SECTION_SKILLS = "skills"
SECTION_AUTHORITY = "authority"
SECTION_ORG_POLICIES = "org_policies"
SECTION_AUTONOMY = "autonomy"
SECTION_TASK = "task"
SECTION_COMPANY = "company"
SECTION_TOOLS = "tools"
SECTION_CONTEXT_BUDGET = "context_budget"

# Sections trimmed when over token budget, least critical first.
# Tools section was removed from the default template per D22
# (non-inferable principle), but custom templates may still render tools.
TRIMMABLE_SECTIONS = (
    SECTION_COMPANY,
    SECTION_TASK,
    SECTION_ORG_POLICIES,
)


def build_core_context(
    agent: AgentIdentity,
    role: Role | None,
    effective_autonomy: EffectiveAutonomy | None = None,
    profile: PromptProfile | None = None,
) -> dict[str, Any]:
    """Build the core (always-present) template variables from agent identity.

    Args:
        agent: Agent identity.
        role: Optional role with description.
        effective_autonomy: Resolved autonomy for the current run.
        profile: Prompt profile controlling verbosity.  ``None``
            defaults to full rendering.

    Returns:
        Dict of core template variables.
    """
    personality = agent.personality
    authority = agent.authority

    # Profile-derived rendering flags (defaults = full profile).
    personality_mode = profile.personality_mode if profile else "full"
    autonomy_detail = profile.autonomy_detail_level if profile else "full"
    include_org_policies = profile.include_org_policies if profile else True
    simplify_criteria = profile.simplify_acceptance_criteria if profile else False

    autonomy_map = _AUTONOMY_LOOKUP[autonomy_detail]

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
        "autonomy_instructions": autonomy_map[agent.level],
        # Profile-driven template flags.
        "personality_mode": personality_mode,
        "include_org_policies": include_org_policies,
        "simplify_acceptance_criteria": simplify_criteria,
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


def compute_sections(  # noqa: PLR0913
    *,
    task: object | None,
    available_tools: tuple[ToolDefinition, ...] = (),
    company: object | None,
    org_policies: tuple[str, ...] = (),
    custom_template: bool = False,
    context_budget: str | None = None,
    profile: PromptProfile | None = None,
) -> tuple[str, ...]:
    """Determine which sections are present in the rendered prompt.

    The default template omits the tools section per D22 (non-inferable
    principle).  Custom templates may still render tools, so the tools
    section is tracked when ``available_tools`` is non-empty and a custom
    template is in use.

    Args:
        task: Optional task context.
        available_tools: Tool definitions (tracked for custom templates).
        company: Optional company context.
        org_policies: Company-wide policy texts.
        custom_template: Whether a custom template is being used.
        context_budget: Formatted context budget indicator string.
        profile: Prompt profile controlling section inclusion.

    Returns:
        Tuple of section names that are included.
    """
    include_policies = profile.include_org_policies if profile else True

    sections: list[str] = [
        SECTION_IDENTITY,
        SECTION_PERSONALITY,
        SECTION_SKILLS,
        SECTION_AUTHORITY,
    ]
    if org_policies and include_policies:
        sections.append(SECTION_ORG_POLICIES)
    # Autonomy follows org_policies in the template.
    sections.append(SECTION_AUTONOMY)
    if task is not None:
        sections.append(SECTION_TASK)
    if available_tools and custom_template:
        sections.append(SECTION_TOOLS)
    if company is not None:
        sections.append(SECTION_COMPANY)
    if context_budget is not None:
        sections.append(SECTION_CONTEXT_BUDGET)
    return tuple(sections)
