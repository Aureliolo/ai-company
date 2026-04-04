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
from synthorg.engine.token_estimation import DefaultTokenEstimator
from synthorg.observability import get_logger
from synthorg.observability.events.prompt import PROMPT_PERSONALITY_TRIMMED

if TYPE_CHECKING:
    from synthorg.core.agent import AgentIdentity
    from synthorg.core.company import Company
    from synthorg.core.role import Role
    from synthorg.core.task import Task
    from synthorg.engine.prompt import PersonalityTrimInfo
    from synthorg.engine.prompt_profiles import PromptProfile
    from synthorg.providers.models import ToolDefinition
    from synthorg.security.autonomy.models import EffectiveAutonomy

logger = get_logger(__name__)

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


def _estimate_personality_tokens(
    ctx: dict[str, Any],
    personality_mode: PersonalityMode,
    estimator: DefaultTokenEstimator,
) -> int:
    """Estimate token count of the personality section as the template renders it.

    Assembles the text that the Jinja2 template would produce for the
    given *personality_mode*, including markdown overhead, and runs it
    through the estimator.

    Args:
        ctx: Template context dict with personality fields populated.
        personality_mode: Which rendering mode to estimate for.
        estimator: Token estimator (char/4 heuristic).

    Returns:
        Estimated token count.
    """
    parts: list[str] = []
    desc = ctx.get("personality_description", "")

    if personality_mode == "full":
        if desc:
            parts.append(desc)
        parts.append(f"- **Communication style**: {ctx['communication_style']}")
        parts.append(f"- **Verbosity**: {ctx['verbosity']}")
        parts.append(f"- **Risk tolerance**: {ctx['risk_tolerance']}")
        parts.append(f"- **Creativity**: {ctx['creativity']}")
        parts.append(f"- **Decision-making**: {ctx['decision_making']}")
        parts.append(f"- **Collaboration preference**: {ctx['collaboration']}")
        parts.append(f"- **Conflict approach**: {ctx['conflict_approach']}")
        traits = ctx.get("personality_traits", ())
        if traits:
            parts.append(f"- **Traits**: {', '.join(traits)}")
    elif personality_mode == "condensed":
        if desc:
            parts.append(desc)
        parts.append(f"- **Style**: {ctx['communication_style']}")
        traits = ctx.get("personality_traits", ())
        if traits:
            parts.append(f"- **Traits**: {', '.join(traits)}")
    else:
        # minimal
        parts.append(f"- **Style**: {ctx['communication_style']}")

    text = "\n".join(parts)
    return estimator.estimate_tokens(text)


def _truncate_description(description: str, max_chars: int) -> str:
    """Truncate a description to fit within a character limit.

    Truncates at the last word boundary before *max_chars*, appending
    ``"..."`` as a suffix.  Returns an empty string when *max_chars*
    is too small to hold any meaningful content.

    Args:
        description: Original description text.
        max_chars: Maximum character count for the result.

    Returns:
        Truncated description or empty string.
    """
    ellipsis = "..."
    # Need at least room for one word + ellipsis.
    if max_chars < len(ellipsis) + 1:
        return ""

    budget = max_chars - len(ellipsis)
    truncated = description[:budget]
    # Find last space to avoid splitting mid-word.
    last_space = truncated.rfind(" ")
    if last_space > 0:
        truncated = truncated[:last_space]
    return truncated.rstrip() + ellipsis


def _trim_personality(
    ctx: dict[str, Any],
    profile: PromptProfile,
) -> PersonalityTrimInfo | None:
    """Progressively trim personality fields to fit the token budget.

    Applies three tiers of trimming until the personality section fits
    within ``profile.max_personality_tokens``:

    1. Drop behavioral enum fields (override mode to ``"condensed"``).
    2. Truncate ``personality_description`` to fit remaining budget.
    3. Fall back to ``"minimal"`` (communication_style only).

    Args:
        ctx: Mutable template context dict.  Modified in place.
        profile: Prompt profile with ``max_personality_tokens`` limit.

    Returns:
        :class:`PersonalityTrimInfo` when trimming was applied, or
        ``None`` when the section was already within budget.
    """
    # Deferred import to avoid circular dependency at module level.
    from synthorg.engine.prompt import PersonalityTrimInfo  # noqa: PLC0415

    estimator = DefaultTokenEstimator()
    max_tokens = profile.max_personality_tokens
    current_mode: PersonalityMode = ctx["personality_mode"]
    before_tokens = _estimate_personality_tokens(ctx, current_mode, estimator)

    if before_tokens <= max_tokens:
        return None

    trim_tier = 0

    # Tier 1: Drop enums (switch to condensed).
    if current_mode == "full":
        trim_tier = 1
        ctx["personality_mode"] = "condensed"
        current_mode = "condensed"
        tokens = _estimate_personality_tokens(ctx, current_mode, estimator)
        if tokens <= max_tokens:
            _log_trim(before_tokens, tokens, max_tokens, trim_tier)
            return PersonalityTrimInfo(
                before_tokens=before_tokens,
                after_tokens=tokens,
                max_tokens=max_tokens,
                trim_tier=trim_tier,
            )

    # Tier 2: Truncate description.
    desc = ctx.get("personality_description", "")
    if desc and current_mode in {"full", "condensed"}:
        trim_tier = max(trim_tier, 2)
        # Estimate tokens WITHOUT description to find remaining budget.
        saved_desc = ctx["personality_description"]
        ctx["personality_description"] = ""
        tokens_without_desc = _estimate_personality_tokens(
            ctx,
            current_mode,
            estimator,
        )
        remaining_tokens = max_tokens - tokens_without_desc
        if remaining_tokens > 0:
            max_chars = remaining_tokens * 4  # Inverse of char/4 heuristic.
            ctx["personality_description"] = _truncate_description(
                saved_desc,
                max_chars,
            )
        else:
            ctx["personality_description"] = ""

        tokens = _estimate_personality_tokens(ctx, current_mode, estimator)
        if tokens <= max_tokens:
            _log_trim(before_tokens, tokens, max_tokens, trim_tier)
            return PersonalityTrimInfo(
                before_tokens=before_tokens,
                after_tokens=tokens,
                max_tokens=max_tokens,
                trim_tier=trim_tier,
            )

    # Tier 3: Fall back to minimal (communication_style only).
    trim_tier = 3
    ctx["personality_mode"] = "minimal"
    ctx["personality_description"] = ""
    tokens = _estimate_personality_tokens(ctx, "minimal", estimator)
    _log_trim(before_tokens, tokens, max_tokens, trim_tier)
    return PersonalityTrimInfo(
        before_tokens=before_tokens,
        after_tokens=tokens,
        max_tokens=max_tokens,
        trim_tier=trim_tier,
    )


def _log_trim(
    before_tokens: int,
    after_tokens: int,
    max_tokens: int,
    trim_tier: int,
) -> None:
    """Log a personality trimming event."""
    logger.info(
        PROMPT_PERSONALITY_TRIMMED,
        before_tokens=before_tokens,
        after_tokens=after_tokens,
        max_tokens=max_tokens,
        trim_tier=trim_tier,
    )


def build_core_context(
    agent: AgentIdentity,
    role: Role | None,
    effective_autonomy: EffectiveAutonomy | None = None,
    profile: PromptProfile | None = None,
    *,
    trimming_enabled: bool = True,
) -> tuple[dict[str, Any], PersonalityTrimInfo | None]:
    """Build core template variables from agent identity and profile.

    Args:
        agent: Agent identity.
        role: Optional role with description.
        effective_autonomy: Resolved autonomy for the current run.
        profile: Prompt profile controlling verbosity.  ``None``
            defaults to full rendering.
        trimming_enabled: When ``True``, enforce
            ``profile.max_personality_tokens`` via progressive trimming.

    Returns:
        Tuple of (template context dict, personality trim info or None).
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

    # Apply personality trimming after the context is fully built.
    trim_info: PersonalityTrimInfo | None = None
    if trimming_enabled and profile is not None:
        trim_info = _trim_personality(ctx, profile)

    return ctx, trim_info


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
