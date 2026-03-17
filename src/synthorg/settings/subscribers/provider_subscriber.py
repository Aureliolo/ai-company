"""Provider settings subscriber — rebuilds ModelRouter on strategy change."""

from typing import TYPE_CHECKING

from synthorg.observability import get_logger
from synthorg.observability.events.settings import (
    SETTINGS_SERVICE_SWAP_FAILED,
    SETTINGS_SUBSCRIBER_NOTIFIED,
)
from synthorg.providers.routing.router import ModelRouter

if TYPE_CHECKING:
    from synthorg.api.state import AppState
    from synthorg.config.schema import RootConfig
    from synthorg.settings.service import SettingsService

logger = get_logger(__name__)

_WATCHED: frozenset[tuple[str, str]] = frozenset(
    {
        ("providers", "default_provider"),
        ("providers", "routing_strategy"),
        ("providers", "retry_max_attempts"),
    }
)


class ProviderSettingsSubscriber:
    """React to provider-namespace settings changes.

    On ``routing_strategy`` change, rebuilds :class:`ModelRouter`
    with the new strategy and swaps it into ``AppState``.

    ``default_provider`` and ``retry_max_attempts`` are advisory-only:
    they are read through :class:`ConfigResolver` at use time and do
    not require a service rebuild.

    Args:
        config: Root company configuration (providers + routing).
        app_state: Application state for atomic service swap.
        settings_service: Settings service for reading new values.
    """

    def __init__(
        self,
        config: RootConfig,
        app_state: AppState,
        settings_service: SettingsService,
    ) -> None:
        self._config = config
        self._app_state = app_state
        self._settings_service = settings_service

    @property
    def watched_keys(self) -> frozenset[tuple[str, str]]:
        """Return provider-namespace keys this subscriber watches."""
        return _WATCHED

    @property
    def subscriber_name(self) -> str:
        """Human-readable subscriber name."""
        return "provider-settings"

    async def on_settings_changed(
        self,
        namespace: str,
        key: str,
    ) -> None:
        """Handle a provider setting change.

        Only ``routing_strategy`` triggers a :class:`ModelRouter`
        rebuild.  Other keys are advisory and logged at INFO level.

        Args:
            namespace: Changed setting namespace.
            key: Changed setting key.
        """
        if key == "routing_strategy":
            await self._rebuild_router()
        else:
            logger.info(
                SETTINGS_SUBSCRIBER_NOTIFIED,
                subscriber=self.subscriber_name,
                namespace=namespace,
                key=key,
                note="advisory — read through ConfigResolver at use time",
            )

    async def _rebuild_router(self) -> None:
        """Build a new ModelRouter from current settings and swap it in."""
        try:
            new_strategy = await self._settings_service.get(
                "providers",
                "routing_strategy",
            )
            new_routing = self._config.routing.model_copy(
                update={"strategy": new_strategy},
            )
            new_router = ModelRouter(
                new_routing,
                dict(self._config.providers),
            )
        except MemoryError, RecursionError:
            raise
        except Exception:
            logger.error(
                SETTINGS_SERVICE_SWAP_FAILED,
                service="model_router",
                exc_info=True,
            )
            return

        self._app_state.swap_model_router(new_router)
