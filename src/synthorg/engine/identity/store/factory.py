"""Factory for building identity version stores from config."""

from typing import TYPE_CHECKING

from synthorg.engine.identity.store.append_only import AppendOnlyIdentityStore
from synthorg.engine.identity.store.copy_on_write import CopyOnWriteIdentityStore
from synthorg.observability import get_logger
from synthorg.observability.events.evolution import EVOLUTION_INVALID_STORE_TYPE

if TYPE_CHECKING:
    from synthorg.core.agent import AgentIdentity
    from synthorg.engine.identity.store.config import IdentityStoreConfig
    from synthorg.engine.identity.store.protocol import IdentityVersionStore
    from synthorg.hr.registry import AgentRegistryService
    from synthorg.versioning.service import VersioningService

logger = get_logger(__name__)


def build_identity_store(
    config: IdentityStoreConfig,
    *,
    registry: AgentRegistryService,
    versioning: VersioningService[AgentIdentity],
) -> IdentityVersionStore:
    """Build an identity version store from configuration.

    Args:
        config: Identity store configuration.
        registry: Agent registry service.
        versioning: Versioning service for AgentIdentity.

    Returns:
        Configured identity version store.

    Raises:
        ValueError: If config.type is not recognized.
    """
    if config.type == "append_only":
        return AppendOnlyIdentityStore(
            registry=registry,
            versioning=versioning,
        )
    if config.type == "copy_on_write":
        return CopyOnWriteIdentityStore(
            registry=registry,
            versioning=versioning,
        )
    msg = f"Unknown identity store type: {config.type!r}"  # type: ignore[unreachable]
    logger.warning(EVOLUTION_INVALID_STORE_TYPE, store_type=config.type)
    raise ValueError(msg)
