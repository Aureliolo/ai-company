"""Agent-related helpers for the first-run setup controller.

Handles template agent expansion, model matching, and persistence
operations that were previously inline in ``setup.py``.
"""

import json
from typing import TYPE_CHECKING, Any

from synthorg.api.errors import ApiValidationError, NotFoundError
from synthorg.observability import get_logger
from synthorg.observability.events.setup import (
    SETUP_AGENTS_CORRUPTED,
    SETUP_AGENTS_READ_FALLBACK,
    SETUP_MODEL_NOT_FOUND,
    SETUP_PROVIDER_NOT_FOUND,
)
from synthorg.settings.enums import SettingSource
from synthorg.settings.errors import SettingNotFoundError

if TYPE_CHECKING:
    from synthorg.api.controllers.setup_models import SetupAgentRequest
    from synthorg.settings.service import SettingsService
    from synthorg.templates.schema import CompanyTemplate

logger = get_logger(__name__)


def expand_template_agents(template: CompanyTemplate) -> list[dict[str, Any]]:
    """Expand template agent configs into persistable agent dicts.

    Uses the same building blocks as the renderer (personality presets,
    auto-name generation) but does not require a full ``RootConfig``
    validation pass.

    Args:
        template: Parsed ``CompanyTemplate`` from the loader.

    Returns:
        List of agent config dicts with ``tier`` metadata.
    """
    from synthorg.templates.presets import (  # noqa: PLC0415
        generate_auto_name,
        get_personality_preset,
    )

    agents: list[dict[str, Any]] = []
    used_names: set[str] = set()

    for idx, agent_cfg in enumerate(template.agents):
        name = agent_cfg.name.strip() if agent_cfg.name else ""
        if not name or name.startswith("{{"):
            name = generate_auto_name(agent_cfg.role, seed=idx)

        # Deduplicate names.
        base_name = name
        counter = 2
        while name in used_names:
            name = f"{base_name} {counter}"
            counter += 1
        used_names.add(name)

        # Resolve personality.
        preset_name = agent_cfg.personality_preset or "pragmatic_builder"
        personality = get_personality_preset(preset_name)

        agent_dict: dict[str, Any] = {
            "name": name,
            "role": agent_cfg.role,
            "department": agent_cfg.department or "engineering",
            "level": agent_cfg.level.value,
            "personality": personality,
            "personality_preset": preset_name,
            "tier": agent_cfg.model,
            "model": {"provider": "", "model_id": ""},
        }
        agents.append(agent_dict)

    return agents


def match_and_assign_models(
    agents: list[dict[str, Any]],
    providers: dict[str, Any],
) -> list[dict[str, Any]]:
    """Auto-assign models to template agents using the matching engine.

    Mutates the agent dicts in-place, setting ``model.provider`` and
    ``model.model_id`` to the best available match.

    Args:
        agents: Expanded agent config dicts from ``expand_template_agents``.
        providers: Provider name -> config mapping.

    Returns:
        The same agent list (mutated in-place for convenience).
    """
    from synthorg.templates.model_matcher import match_all_agents  # noqa: PLC0415

    matches = match_all_agents(agents, providers)
    for m in matches:
        if m.agent_index < len(agents):
            agents[m.agent_index]["model"] = {
                "provider": m.provider_name,
                "model_id": m.model_id,
            }

    return agents


def validate_provider_and_model(
    providers: dict[str, Any],
    data: SetupAgentRequest,
) -> None:
    """Validate that the provider and model exist.

    Args:
        providers: Provider name -> config mapping from management service.
        data: Agent creation payload.

    Raises:
        NotFoundError: If the provider does not exist.
        ApiValidationError: If the model is not in the provider.
    """
    if data.model_provider not in providers:
        msg = f"Provider {data.model_provider!r} not found"
        logger.warning(SETUP_PROVIDER_NOT_FOUND, provider=data.model_provider)
        raise NotFoundError(msg)

    provider_config = providers[data.model_provider]
    model_ids = {m.id for m in provider_config.models}
    if data.model_id not in model_ids:
        msg = f"Model {data.model_id!r} not found in provider {data.model_provider!r}"
        logger.warning(
            SETUP_MODEL_NOT_FOUND,
            provider=data.model_provider,
            model=data.model_id,
        )
        raise ApiValidationError(msg)


def build_agent_config(data: SetupAgentRequest) -> dict[str, Any]:
    """Build an agent config dict for settings persistence.

    Args:
        data: Validated agent creation payload.

    Returns:
        Agent configuration dict suitable for JSON serialization.
    """
    from synthorg.templates.presets import get_personality_preset  # noqa: PLC0415

    personality_dict = get_personality_preset(data.personality_preset)
    agent_config: dict[str, Any] = {
        "name": data.name,
        "role": data.role,
        "department": data.department,
        "level": data.level.value,
        "personality": personality_dict,
        "model": {
            "provider": data.model_provider,
            "model_id": data.model_id,
        },
    }
    if data.budget_limit_monthly is not None:
        agent_config["budget_limit_monthly"] = data.budget_limit_monthly
    return agent_config


async def get_existing_agents(
    settings_svc: SettingsService,
) -> list[dict[str, Any]]:
    """Read the current agents list from settings.

    Only the "entry not found" case yields an empty list. JSON parse
    errors and non-list values are surfaced so callers do not silently
    overwrite corrupted data.

    Args:
        settings_svc: Settings service instance.

    Returns:
        List of agent config dicts (empty if entry is absent or None).

    Raises:
        ApiValidationError: If the stored value is not valid JSON or
            not a JSON array.
    """
    try:
        entry = await settings_svc.get_entry("company", "agents")
    except MemoryError, RecursionError:
        raise
    except SettingNotFoundError:
        logger.debug(SETUP_AGENTS_READ_FALLBACK, reason="entry_not_found")
        return []

    if entry.source != SettingSource.DATABASE:
        logger.debug(
            SETUP_AGENTS_READ_FALLBACK,
            reason="non_database_source",
            source=entry.source,
        )
        return []

    try:
        parsed = json.loads(entry.value)
    except json.JSONDecodeError as exc:
        logger.warning(
            SETUP_AGENTS_CORRUPTED,
            reason="invalid_json",
            exc_info=True,
        )
        msg = "Stored agents list is not valid JSON"
        raise ApiValidationError(msg) from exc

    if not isinstance(parsed, list):
        logger.warning(
            SETUP_AGENTS_CORRUPTED,
            reason="non_list_json",
            raw_type=type(parsed).__name__,
        )
        msg = f"Stored agents list is {type(parsed).__name__}, expected list"
        raise ApiValidationError(msg)

    return parsed


def validate_agents_value(raw: str, *, strict: bool) -> bool:
    """Parse *raw* as JSON and return True if it is a non-empty list.

    When *strict* is True, raises ``ApiValidationError`` on corrupted
    data instead of returning False.

    Args:
        raw: Raw JSON string from settings.
        strict: When True, raise on corrupted data.

    Returns:
        True if the value is a non-empty JSON list.
    """
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError:
        logger.warning(
            SETUP_AGENTS_CORRUPTED,
            reason="invalid_json",
            exc_info=True,
        )
        if strict:
            msg = "Stored agents list is not valid JSON"
            raise ApiValidationError(msg) from None
        return False

    if not isinstance(parsed, list):
        logger.warning(
            SETUP_AGENTS_CORRUPTED,
            reason="non_list_json",
            raw_type=type(parsed).__name__,
        )
        if strict:
            msg = f"Stored agents list is {type(parsed).__name__}, expected list"
            raise ApiValidationError(msg)
        return False

    return bool(parsed)
