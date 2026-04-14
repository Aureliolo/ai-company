"""Well-known Agent Card endpoints.

Serves Agent Cards at ``/.well-known/agent-card.json`` (company
level) and ``/.well-known/agents/{agent_id}/agent-card.json``
(per-agent).  These endpoints are unauthenticated per the A2A
spec -- Agent Cards are public discovery documents.

Registered at the Litestar root level (outside ``/api/v1``) and
only mounted when ``a2a.enabled = True``.
"""

import asyncio
import time
from typing import Any

from litestar import Controller, Request, get
from litestar.datastructures import State  # noqa: TC002
from litestar.response import Response

from synthorg.a2a.agent_card import AgentCardBuilder  # noqa: TC001
from synthorg.observability import get_logger
from synthorg.observability.events.a2a import (
    A2A_AGENT_CARD_CACHE_HIT,
    A2A_AGENT_CARD_CACHE_MISS,
    A2A_AGENT_CARD_SERVED,
)

logger = get_logger(__name__)

# Module-level cache with lock for async safety.
_card_cache: dict[str, tuple[dict[str, Any], float]] = {}
_cache_lock = asyncio.Lock()


async def _get_cached_card(
    cache_key: str,
    ttl: int,
) -> dict[str, Any] | None:
    """Return cached card data if still valid.

    Args:
        cache_key: Cache key (agent id or "__company__").
        ttl: Cache TTL in seconds (0 disables caching).

    Returns:
        Cached card dict or None if expired/missing.
    """
    if ttl <= 0:
        return None
    async with _cache_lock:
        entry = _card_cache.get(cache_key)
        if entry is None:
            return None
        card_data, expires_at = entry
        if time.monotonic() > expires_at:
            del _card_cache[cache_key]
            return None
        return card_data


async def _put_cached_card(
    cache_key: str,
    card_data: dict[str, Any],
    ttl: int,
) -> None:
    """Store card data in cache with TTL.

    Args:
        cache_key: Cache key.
        card_data: Serialized card dict.
        ttl: TTL in seconds (0 skips caching).
    """
    if ttl <= 0:
        return
    async with _cache_lock:
        _card_cache[cache_key] = (
            card_data,
            time.monotonic() + ttl,
        )


class WellKnownAgentCardController(Controller):
    """Serves A2A Agent Cards at well-known URIs."""

    path = "/.well-known"
    tags = ["A2A"]  # noqa: RUF012

    @get(
        "/agent-card.json",
        summary="Company-level Agent Card",
        description=(
            "Returns an aggregated Agent Card representing "
            "all agents in this organization."
        ),
    )
    async def company_agent_card(
        self,
        state: State,
        request: Request[Any, Any, Any],
    ) -> Response[dict[str, Any]]:
        """Serve the company-level Agent Card."""
        app_state = state["app_state"]
        a2a_config = app_state.config.a2a
        ttl = a2a_config.agent_card_cache_ttl_seconds

        host_base = str(request.base_url).rstrip("/")
        company_cache_key = f"__company__:{host_base}"
        cached = await _get_cached_card(company_cache_key, ttl)
        if cached is not None:
            logger.debug(
                A2A_AGENT_CARD_CACHE_HIT,
                cache_key=company_cache_key,
            )
            return Response(
                content=cached,
                media_type="application/json",
                headers={
                    "Cache-Control": f"public, max-age={ttl}",
                },
            )

        logger.debug(
            A2A_AGENT_CARD_CACHE_MISS,
            cache_key=company_cache_key,
        )

        builder: AgentCardBuilder = app_state.a2a_card_builder
        registry = app_state.agent_registry

        try:
            identities = await registry.list_active()
            base_url = str(request.base_url).rstrip("/")
            card = builder.build_company_card(
                identities=identities,
                base_url=f"{base_url}/api/v1/a2a",
                company_name=str(app_state.config.company_name),
            )
            card_data = card.model_dump()
            cache_key = f"__company__:{base_url}"
            await _put_cached_card(cache_key, card_data, ttl)
        except MemoryError, RecursionError:
            raise
        except Exception:
            logger.exception(
                A2A_AGENT_CARD_SERVED,
                card_type="company",
                error="Failed to build company agent card",
            )
            return Response(
                content={"error": "Service temporarily unavailable"},
                media_type="application/json",
                status_code=503,
            )

        logger.info(
            A2A_AGENT_CARD_SERVED,
            card_type="company",
            agent_count=len(identities),
        )
        return Response(
            content=card_data,
            media_type="application/json",
            headers={
                "Cache-Control": f"public, max-age={ttl}",
            },
        )

    @get(
        "/agents/{agent_id:str}/agent-card.json",
        summary="Per-agent Agent Card",
        description=(
            "Returns the Agent Card for a specific agent identified by agent_id."
        ),
    )
    async def agent_card(
        self,
        state: State,
        request: Request[Any, Any, Any],
        agent_id: str,
    ) -> Response[dict[str, Any]]:
        """Serve a per-agent Agent Card."""
        from synthorg.api.errors import NotFoundError  # noqa: PLC0415

        app_state = state["app_state"]
        a2a_config = app_state.config.a2a
        ttl = a2a_config.agent_card_cache_ttl_seconds

        host_base = str(request.base_url).rstrip("/")
        agent_cache_key = f"{agent_id}:{host_base}"
        cached = await _get_cached_card(agent_cache_key, ttl)
        if cached is not None:
            logger.debug(
                A2A_AGENT_CARD_CACHE_HIT,
                cache_key=agent_cache_key,
            )
            return Response(
                content=cached,
                media_type="application/json",
                headers={
                    "Cache-Control": f"public, max-age={ttl}",
                },
            )

        logger.debug(
            A2A_AGENT_CARD_CACHE_MISS,
            cache_key=agent_cache_key,
        )

        registry = app_state.agent_registry

        try:
            identity = await registry.get(agent_id)
            if identity is None:
                identity = await registry.get_by_name(agent_id)
        except MemoryError, RecursionError:
            raise
        except Exception:
            logger.exception(
                A2A_AGENT_CARD_SERVED,
                card_type="agent",
                agent_id=agent_id,
                error="Failed to build agent card",
            )
            return Response(
                content={"error": "Service temporarily unavailable"},
                media_type="application/json",
                status_code=503,
            )

        if identity is None:
            msg = f"Agent '{agent_id}' not found"
            raise NotFoundError(msg)

        try:
            builder: AgentCardBuilder = app_state.a2a_card_builder
            card = builder.build(
                identity=identity,
                base_url=f"{host_base}/api/v1/a2a",
            )
            card_data = card.model_dump()
            await _put_cached_card(agent_cache_key, card_data, ttl)
        except MemoryError, RecursionError:
            raise
        except Exception:
            logger.exception(
                A2A_AGENT_CARD_SERVED,
                card_type="agent",
                agent_id=agent_id,
                error="Failed to build agent card",
            )
            return Response(
                content={"error": "Service temporarily unavailable"},
                media_type="application/json",
                status_code=503,
            )

        logger.info(
            A2A_AGENT_CARD_SERVED,
            card_type="agent",
            agent_id=agent_id,
        )
        return Response(
            content=card_data,
            media_type="application/json",
            headers={
                "Cache-Control": f"public, max-age={ttl}",
            },
        )
