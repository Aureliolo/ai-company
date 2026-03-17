"""Memory settings subscriber — operator notification for restart-required changes."""

from synthorg.observability import get_logger
from synthorg.observability.events.settings import SETTINGS_SUBSCRIBER_NOTIFIED

logger = get_logger(__name__)

_WATCHED: frozenset[tuple[str, str]] = frozenset(
    {
        ("memory", "backend"),
        ("memory", "default_level"),
        ("memory", "consolidation_interval"),
    }
)


class MemorySettingsSubscriber:
    """React to memory-namespace settings changes.

    The dispatcher filters ``restart_required=True`` changes (e.g.
    ``memory/backend``) and logs a WARNING *before* calling
    ``on_settings_changed``.  This subscriber only sees
    non-restart-required keys (``default_level``,
    ``consolidation_interval``), for which it logs an INFO-level
    notification that the value will take effect on next use.
    """

    @property
    def watched_keys(self) -> frozenset[tuple[str, str]]:
        """Return memory-namespace keys this subscriber watches."""
        return _WATCHED

    @property
    def subscriber_name(self) -> str:
        """Human-readable subscriber name."""
        return "memory-settings"

    async def on_settings_changed(
        self,
        namespace: str,
        key: str,
    ) -> None:
        """Log that a memory setting changed and will take effect on next use.

        Args:
            namespace: Changed setting namespace.
            key: Changed setting key.
        """
        logger.info(
            SETTINGS_SUBSCRIBER_NOTIFIED,
            subscriber=self.subscriber_name,
            namespace=namespace,
            key=key,
            note="will take effect on next use",
        )
