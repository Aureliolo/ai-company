"""Background health prober for LLM providers.

Periodically pings provider endpoints with lightweight HTTP requests
(no model loading) to detect reachability.  Real API call outcomes
recorded in :class:`ProviderHealthTracker` automatically reset the
probe interval for that provider.
"""

import asyncio
import contextlib
import time
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Final

import httpx

from synthorg.observability import get_logger
from synthorg.observability.events.provider import (
    PROVIDER_HEALTH_PROBE_FAILED,
    PROVIDER_HEALTH_PROBE_SKIPPED,
    PROVIDER_HEALTH_PROBE_STARTED,
    PROVIDER_HEALTH_PROBE_SUCCESS,
    PROVIDER_HEALTH_PROBER_CYCLE_FAILED,
    PROVIDER_HEALTH_PROBER_STARTED,
    PROVIDER_HEALTH_PROBER_STOPPED,
)
from synthorg.providers.health import ProviderHealthRecord, ProviderHealthTracker

if TYPE_CHECKING:
    from synthorg.config.schema import ProviderConfig
    from synthorg.settings.resolver import ConfigResolver

logger = get_logger(__name__)

_DEFAULT_INTERVAL_SECONDS: Final[int] = 1800  # 30 minutes
_PROBE_TIMEOUT_SECONDS: Final[float] = 10.0


def _build_ping_url(base_url: str, litellm_provider: str | None) -> str:
    """Build a lightweight ping URL for a provider.

    Uses the cheapest possible endpoint -- no model loading.

    Args:
        base_url: Provider base URL.
        litellm_provider: LiteLLM provider identifier for path selection.

    Returns:
        URL to ping.
    """
    stripped = base_url.rstrip("/")
    if litellm_provider == "ollama" or ":11434" in stripped:
        return stripped  # Ollama root returns "Ollama is running"
    return f"{stripped}/models"


def _build_auth_headers(
    auth_type: str,
    api_key: str | None,
) -> dict[str, str]:
    """Build auth headers for the probe request.

    Args:
        auth_type: Provider auth type.
        api_key: API key (may be None for local providers).

    Returns:
        Headers dict (may be empty).
    """
    if api_key and auth_type in ("api_key", "subscription"):
        return {"Authorization": f"Bearer {api_key}"}
    return {}


class ProviderHealthProber:
    """Background service that pings providers to check reachability.

    Only probes providers that have a ``base_url`` configured (local
    and self-hosted providers).  Cloud providers without base_url rely
    on real API call outcomes for health status.

    The prober skips providers that have recent health records in the
    tracker (i.e. recent real API traffic), avoiding redundant probes.

    Args:
        health_tracker: Health tracker to record probe results.
        config_resolver: Config resolver to read provider configs.
        interval_seconds: Seconds between probe cycles.
    """

    __slots__ = (
        "_config_resolver",
        "_health_tracker",
        "_interval",
        "_stop_event",
        "_task",
    )

    def __init__(
        self,
        health_tracker: ProviderHealthTracker,
        config_resolver: ConfigResolver,
        *,
        interval_seconds: int = _DEFAULT_INTERVAL_SECONDS,
    ) -> None:
        self._health_tracker = health_tracker
        self._config_resolver = config_resolver
        self._interval = interval_seconds
        self._stop_event = asyncio.Event()
        self._task: asyncio.Task[None] | None = None

    async def start(self) -> None:
        """Start the background probe loop."""
        if self._task is not None:
            return
        self._stop_event.clear()
        self._task = asyncio.create_task(self._run_loop())
        logger.info(
            PROVIDER_HEALTH_PROBER_STARTED,
            interval_seconds=self._interval,
        )

    async def stop(self) -> None:
        """Stop the background probe loop gracefully."""
        self._stop_event.set()
        if self._task is not None:
            self._task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._task
            self._task = None
        logger.info(PROVIDER_HEALTH_PROBER_STOPPED)

    async def _run_loop(self) -> None:
        """Main loop: probe all, then sleep until next cycle or stop."""
        while not self._stop_event.is_set():
            try:
                await self._probe_all()
            except asyncio.CancelledError:
                raise
            except Exception:
                logger.exception(PROVIDER_HEALTH_PROBER_CYCLE_FAILED)
            try:
                await asyncio.wait_for(
                    self._stop_event.wait(),
                    timeout=self._interval,
                )
                break  # stop_event was set
            except TimeoutError:
                continue  # timeout = time to probe again

    async def _probe_all(self) -> None:
        """Probe all eligible providers in parallel."""
        providers = await self._config_resolver.get_provider_configs()
        eligible: list[tuple[str, ProviderConfig]] = []
        for name, config in providers.items():
            if config.base_url is None:
                continue  # cloud providers -- no lightweight ping available
            summary = await self._health_tracker.get_summary(name)
            if summary.last_check_timestamp is not None:
                elapsed = (
                    datetime.now(UTC) - summary.last_check_timestamp
                ).total_seconds()
                if elapsed < self._interval:
                    logger.debug(
                        PROVIDER_HEALTH_PROBE_SKIPPED,
                        provider=name,
                        seconds_since_last=round(elapsed),
                    )
                    continue
            eligible.append((name, config))
        if eligible:
            async with asyncio.TaskGroup() as tg:
                for name, config in eligible:
                    tg.create_task(self._probe_one(name, config))

    async def _probe_one(
        self,
        name: str,
        config: ProviderConfig,
    ) -> None:
        """Ping a single provider and record the result.

        Args:
            name: Provider name.
            config: Provider configuration.
        """
        base_url = config.base_url or ""
        litellm_provider = config.litellm_provider
        raw_auth = config.auth_type
        auth_type = raw_auth.value if hasattr(raw_auth, "value") else str(raw_auth)
        api_key = config.api_key

        url = _build_ping_url(base_url, litellm_provider)
        headers = _build_auth_headers(auth_type, api_key)

        logger.debug(PROVIDER_HEALTH_PROBE_STARTED, provider=name)
        start = time.monotonic()
        success = False
        error_msg: str | None = None

        try:
            async with httpx.AsyncClient(
                timeout=_PROBE_TIMEOUT_SECONDS,
                follow_redirects=False,
            ) as client:
                resp = await client.get(url, headers=headers)
                _server_error_threshold = 500
                success = resp.status_code < _server_error_threshold
                if not success:
                    error_msg = f"HTTP {resp.status_code}"
        except httpx.ConnectError:
            error_msg = "connection refused"
        except httpx.TimeoutException:
            error_msg = "timeout"
        except asyncio.CancelledError:
            raise
        except MemoryError, RecursionError:
            raise
        except Exception as exc:
            error_msg = f"{type(exc).__name__}: {exc}"

        elapsed_ms = (time.monotonic() - start) * 1000

        record = ProviderHealthRecord(
            provider_name=name,
            timestamp=datetime.now(UTC),
            success=success,
            response_time_ms=round(elapsed_ms, 1),
            error_message=error_msg,
        )
        await self._health_tracker.record(record)

        if success:
            logger.info(
                PROVIDER_HEALTH_PROBE_SUCCESS,
                provider=name,
                latency_ms=round(elapsed_ms, 1),
            )
        else:
            logger.warning(
                PROVIDER_HEALTH_PROBE_FAILED,
                provider=name,
                error=error_msg,
                latency_ms=round(elapsed_ms, 1),
            )
