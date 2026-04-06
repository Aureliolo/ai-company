"""Security settings subscriber -- hot-reload discovery allowlist.

Watches the ``security/discovery_allowlist`` setting and rebuilds
the ``ProviderDiscoveryPolicy`` when it changes.
"""

from synthorg.observability import get_logger
from synthorg.observability.events.security import SECURITY_ALLOWLIST_UPDATED

logger = get_logger(__name__)

_WATCHED: frozenset[tuple[str, str]] = frozenset(
    {("security", "discovery_allowlist")},
)


class SecuritySubscriber:
    """React to ``security/discovery_allowlist`` changes.

    Parses the JSON allowlist string and invokes a callback to
    rebuild the provider discovery policy.

    Args:
        on_allowlist_changed: Async callback receiving the parsed
            ``host:port`` list.  Typically rebuilds
            ``ProviderDiscoveryPolicy`` and swaps it into app state.
    """

    def __init__(
        self,
        *,
        on_allowlist_changed: object,
    ) -> None:
        self._on_changed = on_allowlist_changed

    @property
    def watched_keys(self) -> frozenset[tuple[str, str]]:
        """Keys this subscriber watches."""
        return _WATCHED

    @property
    def subscriber_name(self) -> str:
        """Human-readable subscriber name."""
        return "security-discovery-allowlist"

    async def on_settings_changed(
        self,
        namespace: str,
        key: str,
    ) -> None:
        """Handle a change to the discovery allowlist setting.

        Parses the JSON-encoded allowlist and invokes the callback.

        Args:
            namespace: Setting namespace (expected ``"security"``).
            key: Setting key (expected ``"discovery_allowlist"``).
        """
        if (namespace, key) not in _WATCHED:
            return

        logger.info(
            SECURITY_ALLOWLIST_UPDATED,
            namespace=namespace,
            key=key,
        )
