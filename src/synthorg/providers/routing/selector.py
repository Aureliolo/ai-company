"""Model candidate selectors for multi-provider resolution.

When multiple providers serve the same model, a selector picks the
best candidate from the list.  Selectors are synchronous and
constructed with their context (e.g. quota snapshot) already bound.
"""

from types import MappingProxyType
from typing import TYPE_CHECKING, Protocol, runtime_checkable

from synthorg.observability import get_logger
from synthorg.observability.events.routing import ROUTING_CANDIDATE_SELECTED

if TYPE_CHECKING:
    from collections.abc import Mapping

    from .models import ResolvedModel

logger = get_logger(__name__)


@runtime_checkable
class ModelCandidateSelector(Protocol):
    """Protocol for selecting among multiple provider candidates."""

    def select(
        self,
        candidates: tuple[ResolvedModel, ...],
    ) -> ResolvedModel:
        """Pick the best candidate from one or more models.

        Args:
            candidates: Non-empty tuple of resolved models for the
                same model reference.

        Returns:
            The selected model.
        """
        ...


class QuotaAwareSelector:
    """Prefer providers with available quota, then cheapest.

    When quota information is available, candidates from providers
    with remaining quota are preferred.  Among those (or among all
    candidates when none have quota), the cheapest is returned.

    With an empty quota map (the default), all providers are assumed
    available and the selector degrades to cheapest-first.

    Args:
        provider_quota_available: Mapping of provider name to quota
            availability.  Providers absent from the mapping are
            assumed available.
    """

    def __init__(
        self,
        *,
        provider_quota_available: Mapping[str, bool] | None = None,
    ) -> None:
        self._quota: MappingProxyType[str, bool] = MappingProxyType(
            dict(provider_quota_available) if provider_quota_available else {},
        )

    def select(
        self,
        candidates: tuple[ResolvedModel, ...],
    ) -> ResolvedModel:
        """Select the best candidate considering quota and cost."""
        with_quota = [c for c in candidates if self._has_quota(c.provider_name)]
        pool = with_quota or list(candidates)
        chosen = min(pool, key=lambda m: m.total_cost_per_1k)
        if len(candidates) > 1:
            logger.debug(
                ROUTING_CANDIDATE_SELECTED,
                provider=chosen.provider_name,
                model_id=chosen.model_id,
                candidate_count=len(candidates),
                available_count=len(with_quota),
                selector="quota_aware",
            )
        return chosen

    def _has_quota(self, provider_name: str) -> bool:
        return self._quota.get(provider_name, True)


class CheapestSelector:
    """Always pick the cheapest candidate regardless of quota."""

    def select(
        self,
        candidates: tuple[ResolvedModel, ...],
    ) -> ResolvedModel:
        """Select the cheapest candidate by total cost per 1k tokens."""
        chosen = min(candidates, key=lambda m: m.total_cost_per_1k)
        if len(candidates) > 1:
            logger.debug(
                ROUTING_CANDIDATE_SELECTED,
                provider=chosen.provider_name,
                model_id=chosen.model_id,
                candidate_count=len(candidates),
                selector="cheapest",
            )
        return chosen
