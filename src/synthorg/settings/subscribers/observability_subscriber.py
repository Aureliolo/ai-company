"""Observability settings subscriber -- reconfigure log pipeline at runtime."""

from typing import TYPE_CHECKING

from synthorg.observability import get_logger
from synthorg.observability.enums import LogLevel
from synthorg.observability.events.settings import (
    SETTINGS_OBSERVABILITY_PIPELINE_REBUILT,
    SETTINGS_OBSERVABILITY_REBUILD_FAILED,
    SETTINGS_OBSERVABILITY_VALIDATION_FAILED,
    SETTINGS_SUBSCRIBER_NOTIFIED,
)
from synthorg.observability.setup import configure_logging
from synthorg.observability.sink_config_builder import build_log_config_from_settings

if TYPE_CHECKING:
    from synthorg.settings.service import SettingsService

logger = get_logger(__name__)

_WATCHED: frozenset[tuple[str, str]] = frozenset(
    {
        ("observability", "root_log_level"),
        ("observability", "enable_correlation"),
        ("observability", "sink_overrides"),
        ("observability", "custom_sinks"),
    }
)


class ObservabilitySettingsSubscriber:
    """React to observability-namespace settings changes.

    Any watched key change triggers a full logging pipeline rebuild
    via :func:`configure_logging`.  The subscriber reads all current
    settings, merges defaults with overrides, and reconfigures.

    On failure (settings read error, validation error, or critical
    sink failure), the existing logging configuration is preserved
    where possible.  Note that ``configure_logging`` is not atomic --
    if it fails mid-rebuild, the pipeline may be in a degraded state.

    Args:
        settings_service: Settings service for reading current values.
        log_dir: Log file directory (fixed at construction time).
    """

    def __init__(
        self,
        settings_service: SettingsService,
        log_dir: str = "logs",
    ) -> None:
        self._settings_service = settings_service
        self._log_dir = log_dir

    @property
    def watched_keys(self) -> frozenset[tuple[str, str]]:
        """Return observability-namespace keys this subscriber watches."""
        return _WATCHED

    @property
    def subscriber_name(self) -> str:
        """Human-readable subscriber name."""
        return "observability-settings"

    async def on_settings_changed(
        self,
        namespace: str,
        key: str,
    ) -> None:
        """Handle an observability setting change.

        Reads all current observability settings, builds a merged
        :class:`LogConfig`, and calls :func:`configure_logging` to
        rebuild the pipeline.  Errors are caught and logged -- the
        existing configuration is preserved on failure.

        Args:
            namespace: Changed setting namespace.
            key: Changed setting key.
        """
        if namespace != "observability":
            logger.warning(
                SETTINGS_SUBSCRIBER_NOTIFIED,
                subscriber=self.subscriber_name,
                namespace=namespace,
                key=key,
                note="ignored unexpected namespace",
            )
            return

        # Read all current settings (any key change triggers full rebuild).
        try:
            root_level_result = await self._settings_service.get(
                "observability",
                "root_log_level",
            )
            correlation_result = await self._settings_service.get(
                "observability",
                "enable_correlation",
            )
            overrides_result = await self._settings_service.get(
                "observability",
                "sink_overrides",
            )
            custom_result = await self._settings_service.get(
                "observability",
                "custom_sinks",
            )
        except MemoryError, RecursionError:
            raise
        except Exception:
            logger.error(
                SETTINGS_OBSERVABILITY_REBUILD_FAILED,
                subscriber=self.subscriber_name,
                key=key,
                note="failed to read settings",
                exc_info=True,
            )
            return

        # Parse root level separately for accurate error reporting.
        try:
            root_level = LogLevel(root_level_result.value.upper())
        except ValueError, AttributeError:
            logger.error(
                SETTINGS_OBSERVABILITY_VALIDATION_FAILED,
                subscriber=self.subscriber_name,
                key=key,
                note=f"invalid root_log_level: {root_level_result.value!r}",
                exc_info=True,
            )
            return

        enable_correlation = str(correlation_result.value).lower() == "true"

        # Build LogConfig from settings + defaults.
        try:
            build_result = build_log_config_from_settings(
                root_level=root_level,
                enable_correlation=enable_correlation,
                sink_overrides_json=overrides_result.value,
                custom_sinks_json=custom_result.value,
                log_dir=self._log_dir,
            )
        except MemoryError, RecursionError:
            raise
        except Exception:
            logger.error(
                SETTINGS_OBSERVABILITY_VALIDATION_FAILED,
                subscriber=self.subscriber_name,
                key=key,
                note="invalid sink configuration -- keeping existing config",
                exc_info=True,
            )
            return

        # Rebuild the logging pipeline.  configure_logging is not atomic:
        # it clears old handlers before attaching new ones, so a failure
        # here may leave the pipeline degraded.
        try:
            configure_logging(
                build_result.config,
                routing_overrides=dict(build_result.routing_overrides) or None,
            )
        except MemoryError, RecursionError:
            raise
        except Exception:
            logger.error(
                SETTINGS_OBSERVABILITY_REBUILD_FAILED,
                subscriber=self.subscriber_name,
                key=key,
                note=(
                    "configure_logging failed -- old pipeline was already "
                    "torn down; logging may be degraded"
                ),
                exc_info=True,
            )
            return

        logger.info(
            SETTINGS_OBSERVABILITY_PIPELINE_REBUILT,
            subscriber=self.subscriber_name,
            key=key,
            sink_count=len(build_result.config.sinks),
            custom_routing_count=len(build_result.routing_overrides),
        )
