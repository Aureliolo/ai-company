"""Extracted helper functions for system prompt construction.

Pure data-building helpers used by :mod:`synthorg.engine.prompt` to assemble
template context, metadata dicts, and section tracking.  Separated to keep
``prompt.py`` under the 800-line limit.
"""

from types import MappingProxyType
from typing import TYPE_CHECKING, Any, Final, get_args

from synthorg.core.enums import SeniorityLevel  # noqa: TC001 -- used in type annotation
from synthorg.core.types import AutonomyDetailLevel, PersonalityMode
from synthorg.engine.prompt_template import (
    AUTONOMY_INSTRUCTIONS,
    AUTONOMY_MINIMAL,
    AUTONOMY_SUMMARY,
)

if TYPE_CHECKING:
    from synthorg.core.agent import AgentIdentity
    from synthorg.core.company import Company
    from synthorg.core.role import Role
    from synthorg.core.task import Task
    from synthorg.engine.prompt_profiles import PromptProfile
    from synthorg.providers.models import ToolDefinition
    from synthorg.security.autonomy.models import EffectiveAutonomy

_AUTONOMY_LOOKUP: MappingProxyType[
    AutonomyDetailLevel,
    MappingProxyType[SeniorityLevel, str],
] = MappingProxyType(
    {
        "full": AUTONOMY_INSTRUCTIONS,
        "summary": AUTONOMY_SUMMARY,
        "minimal": AUTONOMY_MINIMAL,
    },
)

_expected_detail_levels = set(get_args(AutonomyDetailLevel))
_missing_detail = _expected_detail_levels - set(_AUTONOMY_LOOKUP)
if _missing_detail:
    _msg_d = f"Missing autonomy lookup for detail levels: {sorted(_missing_detail)}"
    raise ValueError(_msg_d)

# ── Section names ────────────────────────────────────────────────

SECTION_IDENTITY: Final[str] = "identity"
SECTION_PERSONALITY: Final[str] = "personality"
SECTION_SKILLS: Final[str] = "skills"
SECTION_AUTHORITY: Final[str] = "authority"
SECTION_ORG_POLICIES: Final[str] = "org_policies"
SECTION_AUTONOMY: Final[str] = "autonomy"
SECTION_TASK: Final[str] = "task"
SECTION_COMPANY: Final[str] = "company"
SECTION_TOOLS: Final[str] = "tools"
SECTION_CONTEXT_BUDGET: Final[str] = "context_budget"

# Sections trimmed when over token budget, least critical first.
# Tools section was removed from the default template per D22
# (non-inferable principle), but custom templates may still render tools.
TRIMMABLE_SECTIONS: Final[tuple[str, ...]] = (
    SECTION_COMPANY,
    SECTION_TASK,
    SECTION_ORG_POLICIES,
)


def _resolve_profile_flags(
    profile: PromptProfile | None,
) -> tuple[PersonalityMode, AutonomyDetailLevel, bool, bool]:
    """Extract rendering flags from profile, falling back to full defaults.

    Returns:
        ``(personality_mode, autonomy_detail, include_org_policies,
        simplify_criteria)``.
    """
    # Deferred import to avoid circular dependency at module level.
    from synthorg.engine.prompt_profiles import (  # noqa: PLC0415
        get_prompt_profile,
    )

    effective = profile if profile is not None else get_prompt_profile(None)
    return (
        effective.personality_mode,
        effective.autonomy_detail_level,
        effective.include_org_policies,
        effective.simplify_acceptance_criteria,
    )


def build_core_context(
    agent: AgentIdentity,
    role: Role | None,
    effective_autonomy: EffectiveAutonomy | None = None,
    profile: PromptProfile | None = None,
) -> dict[str, Any]:
    """Build core template variables from agent identity and profile.

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
    personality_mode, autonomy_detail, include_org_policies, simplify_criteria = (
        _resolve_profile_flags(profile)
    )
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
    task: Task | None,
    available_tools: tuple[ToolDefinition, ...] = (),
    company: Company | None,
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
    _, _, include_policies, _ = _resolve_profile_flags(profile)

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
    if context_budget:
        sections.append(SECTION_CONTEXT_BUDGET)
    return tuple(sections)
