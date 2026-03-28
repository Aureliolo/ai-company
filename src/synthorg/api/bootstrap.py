"""Agent bootstrap from persisted configuration.

Loads agent configs from the settings-backed :class:`ConfigResolver`
and registers them as live :class:`AgentIdentity` instances in the
:class:`AgentRegistryService`.  Designed to be called on app startup
and again after setup completion.
"""

from datetime import UTC, datetime
from typing import TYPE_CHECKING

from pydantic import ValidationError

from synthorg.core.agent import (
    AgentIdentity,
    MemoryConfig,
    ModelConfig,
    PersonalityConfig,
    ToolPermissions,
)
from synthorg.core.role import Authority
from synthorg.hr.errors import AgentAlreadyRegisteredError
from synthorg.observability import get_logger
from synthorg.observability.events.setup import (
    SETUP_AGENT_BOOTSTRAP_SKIPPED,
    SETUP_AGENTS_BOOTSTRAPPED,
)

if TYPE_CHECKING:
    from synthorg.config.schema import AgentConfig
    from synthorg.hr.registry import AgentRegistryService
    from synthorg.settings.resolver import ConfigResolver

logger = get_logger(__name__)


def _identity_from_config(config: AgentConfig) -> AgentIdentity:
    """Convert a persisted AgentConfig to a runtime AgentIdentity.

    Args:
        config: Agent configuration loaded from settings/YAML.

    Returns:
        A fully constructed AgentIdentity.
    """
    return AgentIdentity(
        name=config.name,
        role=config.role,
        department=config.department,
        level=config.level,
        model=ModelConfig(**config.model)
        if config.model
        else ModelConfig(
            provider="unknown",
            model_id="unknown",
        ),
        personality=(
            PersonalityConfig(**config.personality)
            if config.personality
            else PersonalityConfig()
        ),
        memory=(MemoryConfig(**config.memory) if config.memory else MemoryConfig()),
        tools=(ToolPermissions(**config.tools) if config.tools else ToolPermissions()),
        authority=(Authority(**config.authority) if config.authority else Authority()),
        autonomy_level=config.autonomy_level,
        hiring_date=datetime.now(UTC).date(),
    )


async def bootstrap_agents(
    config_resolver: ConfigResolver,
    agent_registry: AgentRegistryService,
) -> int:
    """Bootstrap agents from persisted config into the runtime registry.

    Loads agent configurations via *config_resolver* and registers each
    as an :class:`AgentIdentity` in *agent_registry*.  Skips agents
    that are already registered (idempotent) or have invalid configs
    (resilient).

    Args:
        config_resolver: Resolver for persisted settings.
        agent_registry: Runtime agent registry.

    Returns:
        Count of newly registered agents.
    """
    agent_configs = await config_resolver.get_agents()

    if not agent_configs:
        logger.info(SETUP_AGENTS_BOOTSTRAPPED, count=0)
        return 0

    registered = 0

    for config in agent_configs:
        try:
            identity = _identity_from_config(config)
        except ValidationError:
            logger.warning(
                SETUP_AGENT_BOOTSTRAP_SKIPPED,
                agent_name=config.name,
                reason="invalid_config",
                exc_info=True,
            )
            continue

        try:
            await agent_registry.register(identity)
            registered += 1
        except AgentAlreadyRegisteredError:
            logger.debug(
                SETUP_AGENT_BOOTSTRAP_SKIPPED,
                agent_name=config.name,
                agent_id=str(identity.id),
                reason="already_registered",
            )

    logger.info(
        SETUP_AGENTS_BOOTSTRAPPED,
        count=registered,
        total_configs=len(agent_configs),
    )
    return registered
