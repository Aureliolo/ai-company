"""System prompt construction from agent identity and context.

Translates agent configuration (personality, skills, authority, role) into
contextually rich system prompts that shape agent behavior during LLM calls.

**Non-inferable principle:** System prompts should contain only information
that agents cannot discover by reading the codebase or environment.  Tool
definitions, for example, are already delivered via the LLM provider's API
``tools`` parameter, so repeating them in the system prompt would increase
cost without benefit (per D22, arXiv:2602.11988).  The default template
therefore omits the ``Available Tools`` section.  Custom templates may still
reference ``{{ tools }}`` when explicitly needed.

Example::

    from synthorg.engine.prompt import build_system_prompt

    prompt = build_system_prompt(agent=agent_identity, task=task)
    prompt.content  # rendered system prompt string
"""

from typing import TYPE_CHECKING, Any

from jinja2 import TemplateError as Jinja2TemplateError
from jinja2 import TemplateSyntaxError
from jinja2.sandbox import SandboxedEnvironment
from pydantic import BaseModel, ConfigDict, Field

from synthorg.budget.currency import DEFAULT_CURRENCY, format_cost, get_currency_symbol
from synthorg.engine._prompt_helpers import (
    SECTION_COMPANY as _SECTION_COMPANY,
)
from synthorg.engine._prompt_helpers import (
    SECTION_ORG_POLICIES as _SECTION_ORG_POLICIES,
)
from synthorg.engine._prompt_helpers import (
    SECTION_TASK as _SECTION_TASK,
)
from synthorg.engine._prompt_helpers import (
    TRIMMABLE_SECTIONS as _TRIMMABLE_SECTIONS,
)
from synthorg.engine._prompt_helpers import (
    build_core_context as _build_core_context,
)
from synthorg.engine._prompt_helpers import (
    build_metadata as _build_metadata,
)
from synthorg.engine._prompt_helpers import (
    compute_sections as _compute_sections,
)
from synthorg.engine.errors import PromptBuildError
from synthorg.engine.policy_validation import validate_policy_quality
from synthorg.engine.prompt_profiles import PromptProfile, get_prompt_profile
from synthorg.engine.prompt_template import (
    DEFAULT_TEMPLATE,
    PROMPT_TEMPLATE_VERSION,
)
from synthorg.engine.sanitization import sanitize_message
from synthorg.engine.token_estimation import (
    DefaultTokenEstimator,
    PromptTokenEstimator,
)
from synthorg.observability import get_logger
from synthorg.observability.events.prompt import (
    PROMPT_BUILD_BUDGET_EXCEEDED,
    PROMPT_BUILD_ERROR,
    PROMPT_BUILD_START,
    PROMPT_BUILD_SUCCESS,
    PROMPT_BUILD_TOKEN_TRIMMED,
    PROMPT_CUSTOM_TEMPLATE_FAILED,
    PROMPT_CUSTOM_TEMPLATE_LOADED,
    PROMPT_POLICY_VALIDATION_FAILED,
    PROMPT_PROFILE_SELECTED,
)

if TYPE_CHECKING:
    from synthorg.core.agent import AgentIdentity
    from synthorg.core.company import Company
    from synthorg.core.role import Role
    from synthorg.core.task import Task
    from synthorg.core.types import ModelTier
    from synthorg.providers.models import ToolDefinition
    from synthorg.security.autonomy.models import EffectiveAutonomy

logger = get_logger(__name__)

# Sandboxed to prevent arbitrary code execution in user-provided custom templates.
# Thread-safe for concurrent parse/render calls. Do NOT add filters, globals,
# or extensions after module initialization.
_SANDBOX_ENV = SandboxedEnvironment()


# ── Result model ─────────────────────────────────────────────────


class SystemPrompt(BaseModel):
    """Immutable result of system prompt construction.

    Attributes:
        content: Full rendered prompt text.
        template_version: Version of the template that produced this prompt.
        estimated_tokens: Token estimate of the prompt content.
        sections: Names of sections included in the prompt.
        metadata: Agent identity metadata (agent_id, name, role,
            department, level, and optionally profile_tier).
    """

    model_config = ConfigDict(frozen=True, allow_inf_nan=False)

    content: str = Field(description="Full rendered prompt text")
    template_version: str = Field(
        description="Template version that produced this prompt",
    )
    estimated_tokens: int = Field(
        ge=0,
        description="Estimated token count of prompt content",
    )
    sections: tuple[str, ...] = Field(
        description="Names of sections included in the prompt",
    )
    metadata: dict[str, str] = Field(
        description="Agent identity metadata (string-only values; shallow-frozen)",
    )


# ── Public API ───────────────────────────────────────────────────


def build_system_prompt(  # noqa: PLR0913
    *,
    agent: AgentIdentity,
    role: Role | None = None,
    task: Task | None = None,
    available_tools: tuple[ToolDefinition, ...] = (),
    company: Company | None = None,
    org_policies: tuple[str, ...] = (),
    max_tokens: int | None = None,
    custom_template: str | None = None,
    token_estimator: PromptTokenEstimator | None = None,
    effective_autonomy: EffectiveAutonomy | None = None,
    context_budget_indicator: str | None = None,
    currency: str = DEFAULT_CURRENCY,
    model_tier: ModelTier | None = None,
) -> SystemPrompt:
    """Build a system prompt from agent identity and optional context.

    When ``max_tokens`` is provided and the prompt exceeds it, optional
    sections are progressively trimmed (company, task, org_policies).

    Args:
        agent: Agent identity containing personality, skills, authority.
        role: Optional role with description and responsibilities.
        task: Optional task context injected into the prompt.
        available_tools: Tool definitions populated into template context
            for custom templates only; the default template omits tools
            per D22 (non-inferable principle).
        company: Opt-in. Non-inferable principle recommends omitting
            unless agents need org-level context they cannot discover.
        org_policies: Company-wide policy texts to inject into prompt.
        max_tokens: Token budget; sections are trimmed if exceeded.
        custom_template: Optional Jinja2 template string override.
        token_estimator: Custom token estimator (defaults to char/4).
        effective_autonomy: Resolved autonomy for the current run.
        context_budget_indicator: Formatted context budget indicator
            string to inject into the prompt.
        currency: ISO 4217 currency code for budget displays
            (e.g. ``"USD"``, ``"EUR"``).
        model_tier: Model capability tier for prompt profile selection.
            ``None`` defaults to the full (large) profile.

    Returns:
        Immutable :class:`SystemPrompt` with rendered content and metadata.

    Raises:
        PromptBuildError: If prompt construction fails.
    """
    _validate_max_tokens(agent, max_tokens)
    _validate_org_policies(agent, org_policies)

    profile = get_prompt_profile(model_tier)
    logger.info(
        PROMPT_PROFILE_SELECTED,
        requested_tier=model_tier,
        selected_tier=profile.tier,
        defaulted=model_tier is None,
        personality_mode=profile.personality_mode,
        autonomy_detail_level=profile.autonomy_detail_level,
    )

    # Advisory only -- issues are logged but never block prompt construction.
    if org_policies:
        try:
            validate_policy_quality(org_policies)
        except MemoryError, RecursionError:
            raise
        except Exception:
            logger.warning(
                PROMPT_POLICY_VALIDATION_FAILED,
                agent_id=str(agent.id),
                exc_info=True,
            )

    logger.info(
        PROMPT_BUILD_START,
        agent_id=str(agent.id),
        agent_name=agent.name,
        has_task=task is not None,
        tool_count=len(available_tools),
        has_company=company is not None,
        has_custom_template=custom_template is not None,
        model_tier=model_tier,
    )

    try:
        estimator = token_estimator or DefaultTokenEstimator()
        template_str = _resolve_template(custom_template)

        result = _render_with_trimming(
            template_str=template_str,
            agent=agent,
            role=role,
            task=task,
            available_tools=available_tools,
            company=company,
            org_policies=org_policies,
            max_tokens=max_tokens,
            estimator=estimator,
            effective_autonomy=effective_autonomy,
            context_budget_indicator=context_budget_indicator,
            currency=currency,
            profile=profile,
        )
    except PromptBuildError:
        raise  # Already logged by inner functions.
    except MemoryError, RecursionError:
        logger.error(
            PROMPT_BUILD_ERROR,
            agent_id=str(agent.id),
            agent_name=agent.name,
            error="non-recoverable error building prompt",
            exc_info=True,
        )
        raise
    except Exception as exc:
        logger.exception(
            PROMPT_BUILD_ERROR,
            agent_id=str(agent.id),
            agent_name=agent.name,
            error=str(exc),
        )
        detail = sanitize_message(str(exc))
        msg = f"Unexpected error building prompt for agent '{agent.name}': {detail}"
        raise PromptBuildError(msg) from exc

    return _log_and_return(agent, result)


def _validate_max_tokens(
    agent: AgentIdentity,
    max_tokens: int | None,
) -> None:
    """Raise ``PromptBuildError`` if ``max_tokens`` is non-positive."""
    if max_tokens is not None and max_tokens <= 0:
        msg = f"max_tokens must be > 0, got {max_tokens}"
        logger.error(
            PROMPT_BUILD_ERROR,
            agent_id=str(agent.id),
            agent_name=agent.name,
            max_tokens=max_tokens,
        )
        raise PromptBuildError(msg)


def _validate_org_policies(
    agent: AgentIdentity,
    org_policies: tuple[str, ...],
) -> None:
    """Raise ``PromptBuildError`` on blank or non-string policy entries.

    Args:
        agent: Agent identity for error context.
        org_policies: Policy texts to validate.

    Raises:
        PromptBuildError: If any policy entry is empty or whitespace-only.
    """
    for index, policy in enumerate(org_policies):
        if not isinstance(policy, str) or not policy.strip():
            msg = f"org_policies[{index}] must be a non-empty string"
            logger.error(
                PROMPT_BUILD_ERROR,
                agent_id=str(agent.id),
                error=msg,
            )
            raise PromptBuildError(msg)


def _log_and_return(
    agent: AgentIdentity,
    result: SystemPrompt,
) -> SystemPrompt:
    """Log prompt build success and return the result."""
    logger.info(
        PROMPT_BUILD_SUCCESS,
        agent_id=str(agent.id),
        sections=result.sections,
        estimated_tokens=result.estimated_tokens,
        template_version=result.template_version,
    )
    return result


# ── Private helpers ──────────────────────────────────────────────


def _resolve_template(custom_template: str | None) -> str:
    """Resolve the template string to use for rendering.

    Args:
        custom_template: Optional user-provided template string.

    Returns:
        The template string to render.

    Raises:
        PromptBuildError: If custom template syntax is invalid.
    """
    if custom_template is None:
        return DEFAULT_TEMPLATE

    # Early-fail: validate syntax before building the template context.
    # from_string() in _render_template would also catch this, but failing
    # here produces a more specific "invalid syntax" error message.
    try:
        _SANDBOX_ENV.parse(custom_template)
    except TemplateSyntaxError as exc:
        logger.exception(
            PROMPT_CUSTOM_TEMPLATE_FAILED,
            error=str(exc),
        )
        msg = f"Custom template has invalid Jinja2 syntax: {exc}"
        raise PromptBuildError(msg) from exc

    logger.debug(PROMPT_CUSTOM_TEMPLATE_LOADED)
    return custom_template


def _build_template_context(  # noqa: PLR0913
    *,
    agent: AgentIdentity,
    role: Role | None,
    task: Task | None,
    available_tools: tuple[ToolDefinition, ...],
    company: Company | None,
    org_policies: tuple[str, ...] = (),
    effective_autonomy: EffectiveAutonomy | None = None,
    context_budget: str | None = None,
    currency: str = DEFAULT_CURRENCY,
    profile: PromptProfile | None = None,
) -> dict[str, Any]:
    """Assemble the full Jinja2 template context from agent and optional inputs.

    Args:
        agent: Agent identity.
        role: Optional role with description.
        task: Optional task context.
        available_tools: Tool definitions.
        company: Optional company context.
        org_policies: Company-wide policy texts.
        effective_autonomy: Resolved autonomy for the current run.
        context_budget: Formatted context budget indicator string.
        currency: ISO 4217 currency code for budget displays.
        profile: Prompt profile controlling rendering verbosity.

    Returns:
        Dict of template variables.
    """
    context = _build_core_context(agent, role, effective_autonomy, profile)

    context["currency_symbol"] = get_currency_symbol(currency)
    context["currency"] = currency
    budget_limit = agent.authority.budget_limit
    context["formatted_budget_limit"] = (
        format_cost(budget_limit, currency) if budget_limit > 0 else ""
    )
    context["org_policies"] = org_policies
    context["context_budget"] = context_budget

    if task is not None:
        context["task"] = {
            "title": task.title,
            "description": task.description,
            "acceptance_criteria": tuple(
                {"description": c.description} for c in task.acceptance_criteria
            ),
            "budget_limit": task.budget_limit,
            "deadline": task.deadline,
        }
        context["formatted_task_budget"] = (
            format_cost(task.budget_limit, currency) if task.budget_limit > 0 else ""
        )
    else:
        context["task"] = None
        context["formatted_task_budget"] = ""

    context["tools"] = (
        tuple({"name": t.name, "description": t.description} for t in available_tools)
        if available_tools
        else None
    )

    if company is not None:
        context["company"] = {"name": company.name}
        context["company_departments"] = tuple(d.name for d in company.departments)
    else:
        context["company"] = None
        context["company_departments"] = None

    return context


def _render_template(template_str: str, context: dict[str, Any]) -> str:
    """Render a Jinja2 template string with the given context.

    Args:
        template_str: Jinja2 template text.
        context: Template variables.

    Returns:
        Rendered prompt text.

    Raises:
        PromptBuildError: If rendering fails.
    """
    try:
        template = _SANDBOX_ENV.from_string(template_str)
        return template.render(**context)
    except Jinja2TemplateError as exc:
        logger.exception(PROMPT_BUILD_ERROR, error=str(exc))
        msg = f"System prompt rendering failed: {exc}"
        raise PromptBuildError(msg) from exc


def _trim_sections(  # noqa: PLR0913
    *,
    template_str: str,
    agent: AgentIdentity,
    role: Role | None,
    task: Task | None,
    available_tools: tuple[ToolDefinition, ...],
    company: Company | None,
    org_policies: tuple[str, ...],
    max_tokens: int,
    estimator: PromptTokenEstimator,
    effective_autonomy: EffectiveAutonomy | None = None,
    context_budget: str | None = None,
    currency: str = DEFAULT_CURRENCY,
    profile: PromptProfile | None = None,
) -> tuple[
    str,
    int,
    Task | None,
    Company | None,
    tuple[str, ...],
]:
    """Progressively remove optional sections until under token budget.

    Returns ``(content, estimated, task, company, org_policies)``
    so the caller can reuse the final render.
    """
    trimmed_sections: list[str] = []

    for section in _TRIMMABLE_SECTIONS:
        content, estimated = _render_and_estimate(
            template_str,
            agent,
            role,
            task,
            available_tools,
            company,
            org_policies,
            estimator,
            effective_autonomy=effective_autonomy,
            context_budget=context_budget,
            currency=currency,
            profile=profile,
        )
        if estimated <= max_tokens:
            break

        if section == _SECTION_COMPANY and company is not None:
            company = None
        elif (
            section == _SECTION_ORG_POLICIES
            and org_policies
            and (profile is None or profile.include_org_policies)
        ):
            org_policies = ()
        elif section == _SECTION_TASK and task is not None:
            task = None
        else:
            continue

        trimmed_sections.append(section)
    else:
        # All sections exhausted -- do a final render.
        content, estimated = _render_and_estimate(
            template_str,
            agent,
            role,
            task,
            available_tools,
            company,
            org_policies,
            estimator,
            effective_autonomy=effective_autonomy,
            context_budget=context_budget,
            currency=currency,
            profile=profile,
        )

    _log_trim_results(agent, max_tokens, estimated, trimmed_sections)

    return content, estimated, task, company, org_policies


def _log_trim_results(
    agent: AgentIdentity,
    max_tokens: int,
    estimated: int,
    trimmed_sections: list[str],
) -> None:
    """Log warnings for trimmed sections and/or budget-exceeded state."""
    if trimmed_sections:
        logger.warning(
            PROMPT_BUILD_TOKEN_TRIMMED,
            agent_id=str(agent.id),
            max_tokens=max_tokens,
            estimated_tokens=estimated,
            trimmed_sections=trimmed_sections,
        )
    if estimated > max_tokens:
        logger.warning(
            PROMPT_BUILD_BUDGET_EXCEEDED,
            agent_id=str(agent.id),
            max_tokens=max_tokens,
            estimated_tokens=estimated,
        )


def _render_with_trimming(  # noqa: PLR0913
    *,
    template_str: str,
    agent: AgentIdentity,
    role: Role | None,
    task: Task | None,
    available_tools: tuple[ToolDefinition, ...],
    company: Company | None,
    org_policies: tuple[str, ...] = (),
    max_tokens: int | None,
    estimator: PromptTokenEstimator,
    effective_autonomy: EffectiveAutonomy | None = None,
    context_budget_indicator: str | None = None,
    currency: str = DEFAULT_CURRENCY,
    profile: PromptProfile | None = None,
) -> SystemPrompt:
    """Render the prompt, trimming optional sections if over token budget."""
    content, estimated = _render_and_estimate(
        template_str,
        agent,
        role,
        task,
        available_tools,
        company,
        org_policies,
        estimator,
        effective_autonomy=effective_autonomy,
        context_budget=context_budget_indicator,
        currency=currency,
        profile=profile,
    )

    if max_tokens is not None and estimated > max_tokens:
        content, estimated, task, company, org_policies = _trim_sections(
            template_str=template_str,
            agent=agent,
            role=role,
            task=task,
            available_tools=available_tools,
            company=company,
            org_policies=org_policies,
            max_tokens=max_tokens,
            estimator=estimator,
            effective_autonomy=effective_autonomy,
            context_budget=context_budget_indicator,
            currency=currency,
            profile=profile,
        )

    return _build_prompt_result(
        content,
        estimated,
        task,
        available_tools,
        company,
        org_policies,
        agent,
        custom_template=template_str is not DEFAULT_TEMPLATE,
        context_budget=context_budget_indicator,
        profile=profile,
    )


def _build_prompt_result(  # noqa: PLR0913
    content: str,
    estimated: int,
    task: Task | None,
    available_tools: tuple[ToolDefinition, ...],
    company: Company | None,
    org_policies: tuple[str, ...],
    agent: AgentIdentity,
    *,
    custom_template: bool = False,
    context_budget: str | None = None,
    profile: PromptProfile | None = None,
) -> SystemPrompt:
    """Assemble the final ``SystemPrompt`` from rendered content."""
    sections = _compute_sections(
        task=task,
        available_tools=available_tools,
        company=company,
        org_policies=org_policies,
        custom_template=custom_template,
        context_budget=context_budget,
        profile=profile,
    )
    metadata = _build_metadata(agent)
    if profile is not None:
        metadata["profile_tier"] = profile.tier
    return SystemPrompt(
        content=content,
        template_version=PROMPT_TEMPLATE_VERSION,
        estimated_tokens=estimated,
        sections=sections,
        metadata=metadata,
    )


def _render_and_estimate(  # noqa: PLR0913
    template_str: str,
    agent: AgentIdentity,
    role: Role | None,
    task: Task | None,
    available_tools: tuple[ToolDefinition, ...],
    company: Company | None,
    org_policies: tuple[str, ...],
    estimator: PromptTokenEstimator,
    *,
    effective_autonomy: EffectiveAutonomy | None = None,
    context_budget: str | None = None,
    currency: str = DEFAULT_CURRENCY,
    profile: PromptProfile | None = None,
) -> tuple[str, int]:
    """Render the template and estimate its token count.

    Args:
        template_str: Jinja2 template text.
        agent: Agent identity.
        role: Optional role.
        task: Optional task context.
        available_tools: Tool definitions.
        company: Optional company context.
        org_policies: Company-wide policy texts.
        estimator: Token estimator.
        effective_autonomy: Resolved autonomy for the current run.
        context_budget: Formatted context budget indicator string.
        currency: ISO 4217 currency code for budget displays.
        profile: Prompt profile controlling rendering verbosity.

    Returns:
        Tuple of (rendered content, estimated token count).
    """
    context = _build_template_context(
        agent=agent,
        role=role,
        task=task,
        available_tools=available_tools,
        company=company,
        org_policies=org_policies,
        effective_autonomy=effective_autonomy,
        context_budget=context_budget,
        currency=currency,
        profile=profile,
    )
    content = _render_template(template_str, context)
    return content, estimator.estimate_tokens(content)


def build_error_prompt(
    identity: AgentIdentity,
    agent_id: str,
    system_prompt: SystemPrompt | None,
) -> SystemPrompt:
    """Return the existing system prompt or a minimal error placeholder.

    Used by the engine when the execution pipeline fails and a
    ``SystemPrompt`` was never built (or was partially built).

    Args:
        identity: Agent identity for metadata.
        agent_id: String agent identifier.
        system_prompt: Previously built prompt, or ``None``.

    Returns:
        The existing prompt if available, else a minimal placeholder.
    """
    if system_prompt is not None:
        return system_prompt
    metadata = {**_build_metadata(identity), "agent_id": agent_id}
    return SystemPrompt(
        content="",
        template_version="error",
        estimated_tokens=0,
        sections=(),
        metadata=metadata,
    )


def format_task_instruction(
    task: Task,
    *,
    currency: str = DEFAULT_CURRENCY,
) -> str:
    """Format a task into a user message for the initial conversation.

    Args:
        task: Task to format.
        currency: ISO 4217 currency code for budget display.

    Returns:
        Markdown-formatted task instruction string.
    """
    parts = [f"# Task: {task.title}", "", task.description]

    if task.acceptance_criteria:
        parts.append("")
        parts.append("## Acceptance Criteria")
        parts.extend(f"- {c.description}" for c in task.acceptance_criteria)

    if task.budget_limit > 0:
        parts.append("")
        parts.append(f"**Budget limit:** {format_cost(task.budget_limit, currency)}")

    if task.deadline:
        parts.append("")
        parts.append(f"**Deadline:** {task.deadline}")

    return "\n".join(parts)
