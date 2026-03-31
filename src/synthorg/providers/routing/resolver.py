"""Model resolver -- maps aliases and model IDs to ``ResolvedModel``.

Indexes every model ID and alias to one or more ``ResolvedModel``
instances (multi-provider support).  When multiple providers serve
the same model, a ``ModelCandidateSelector`` picks the best
candidate at resolution time.

Typically built via the ``from_config`` classmethod from
``dict[str, ProviderConfig]``.  Uses ``MappingProxyType`` to guarantee
immutability after construction.
"""

from types import MappingProxyType
from typing import TYPE_CHECKING

from synthorg.observability import get_logger
from synthorg.observability.events.routing import (
    ROUTING_MODEL_RESOLUTION_FAILED,
    ROUTING_MODEL_RESOLVED,
    ROUTING_MULTI_PROVIDER_REGISTERED,
    ROUTING_RESOLVER_BUILT,
)

from .errors import ModelResolutionError
from .models import ResolvedModel
from .selector import ModelCandidateSelector, QuotaAwareSelector

if TYPE_CHECKING:
    from synthorg.config.schema import ProviderConfig

logger = get_logger(__name__)


class ModelResolver:
    """Resolves model aliases and IDs to ``ResolvedModel`` instances.

    Built from the providers section of the company config.  Each model
    ID and alias is indexed for O(1) lookup.  When multiple providers
    register the same ref, the injected ``selector`` picks the best
    candidate.

    Examples:
        Build from config::

            resolver = ModelResolver.from_config(root_config.providers)
            model = resolver.resolve("medium")
    """

    def __init__(
        self,
        index: dict[str, tuple[ResolvedModel, ...]],
        *,
        selector: ModelCandidateSelector | None = None,
    ) -> None:
        """Initialize with a pre-built ref -> candidates index.

        Args:
            index: Mapping of model ref to tuple of resolved models.
                A frozen copy is made internally; the caller's dict
                is not modified.
            selector: Strategy for picking among multiple candidates.
                Defaults to ``QuotaAwareSelector()`` (cheapest with
                quota preference).
        """
        self._index: MappingProxyType[str, tuple[ResolvedModel, ...]] = (
            MappingProxyType(
                {k: tuple(v) for k, v in index.items()},
            )
        )
        self._selector: ModelCandidateSelector = (
            selector if selector is not None else QuotaAwareSelector()
        )

    @property
    def selector(self) -> ModelCandidateSelector:
        """The active candidate selector."""
        return self._selector

    @staticmethod
    def _index_ref(
        index: dict[str, list[ResolvedModel]],
        ref: str,
        resolved: ResolvedModel,
        provider_name: str,
    ) -> None:
        """Register a model ref, appending on multi-provider collision."""
        existing_list = index.get(ref)
        if existing_list is not None:
            for existing in existing_list:
                if existing == resolved:
                    return  # Exact duplicate, skip
            logger.info(
                ROUTING_MULTI_PROVIDER_REGISTERED,
                ref=ref,
                existing_providers=[e.provider_name for e in existing_list],
                new_provider=provider_name,
                new_model_id=resolved.model_id,
            )
            existing_list.append(resolved)
        else:
            index[ref] = [resolved]

    @classmethod
    def from_config(
        cls,
        providers: dict[str, ProviderConfig],
        *,
        selector: ModelCandidateSelector | None = None,
    ) -> ModelResolver:
        """Build a resolver from a provider config dict.

        Args:
            providers: Provider config dict (key = provider name).
            selector: Optional candidate selector override.

        Returns:
            A new ``ModelResolver`` with all models indexed.
        """
        index: dict[str, list[ResolvedModel]] = {}

        for provider_name, provider_config in providers.items():
            for model_config in provider_config.models:
                resolved = ResolvedModel(
                    provider_name=provider_name,
                    model_id=model_config.id,
                    alias=model_config.alias,
                    cost_per_1k_input=model_config.cost_per_1k_input,
                    cost_per_1k_output=model_config.cost_per_1k_output,
                    max_context=model_config.max_context,
                    estimated_latency_ms=model_config.estimated_latency_ms,
                )
                for ref in (model_config.id, model_config.alias):
                    if ref is None:
                        continue
                    cls._index_ref(index, ref, resolved, provider_name)

        tuple_index = {k: tuple(v) for k, v in index.items()}
        multi_refs = [k for k, v in tuple_index.items() if len(v) > 1]

        logger.info(
            ROUTING_RESOLVER_BUILT,
            model_count=len(
                {
                    (m.provider_name, m.model_id)
                    for candidates in tuple_index.values()
                    for m in candidates
                },
            ),
            ref_count=len(tuple_index),
            providers=sorted(providers),
            multi_provider_refs=multi_refs,
        )
        return cls(tuple_index, selector=selector)

    def resolve(self, ref: str) -> ResolvedModel:
        """Resolve a model alias or ID to a ``ResolvedModel``.

        When multiple providers serve the same model, the selector
        picks the best candidate.

        Args:
            ref: Model alias or ID string.

        Returns:
            The resolved model.

        Raises:
            ModelResolutionError: If the ref is not found.
        """
        candidates = self._index.get(ref)
        if candidates is None:
            logger.warning(
                ROUTING_MODEL_RESOLUTION_FAILED,
                ref=ref,
                available=sorted(self._index),
            )
            msg = f"Model reference {ref!r} not found. Available: {sorted(self._index)}"
            raise ModelResolutionError(msg, context={"ref": ref})
        model = self._selector.select(candidates)
        logger.debug(
            ROUTING_MODEL_RESOLVED,
            ref=ref,
            provider=model.provider_name,
            model_id=model.model_id,
            candidate_count=len(candidates),
        )
        return model

    def resolve_safe(self, ref: str) -> ResolvedModel | None:
        """Resolve a model ref without raising.

        Returns ``None`` instead of raising ``ModelResolutionError``
        when *ref* is not found.

        Args:
            ref: Model alias or ID string.

        Returns:
            The resolved model, or ``None`` if not found.
        """
        candidates = self._index.get(ref)
        if candidates is None:
            logger.debug(
                ROUTING_MODEL_RESOLUTION_FAILED,
                ref=ref,
            )
            return None
        return self._selector.select(candidates)

    def resolve_all(self, ref: str) -> tuple[ResolvedModel, ...]:
        """Return all provider variants for a model ref.

        Args:
            ref: Model alias or ID string.

        Returns:
            Tuple of all candidates, or empty tuple if not found.
        """
        return self._index.get(ref, ())

    def all_models(self) -> tuple[ResolvedModel, ...]:
        """Return all resolved models including multi-provider variants.

        Deduplication is by ``(provider_name, model_id)`` pair, so the
        same model from different providers appears as separate entries.
        """
        seen: set[tuple[str, str]] = set()
        result: list[ResolvedModel] = []
        for candidates in self._index.values():
            for m in candidates:
                key = (m.provider_name, m.model_id)
                if key not in seen:
                    seen.add(key)
                    result.append(m)
        return tuple(result)

    def all_models_sorted_by_cost(self) -> tuple[ResolvedModel, ...]:
        """Return models sorted by total cost (ascending).

        Total cost is ``cost_per_1k_input + cost_per_1k_output``.
        """
        return tuple(
            sorted(
                self.all_models(),
                key=lambda m: m.total_cost_per_1k,
            ),
        )

    def all_models_sorted_by_latency(self) -> tuple[ResolvedModel, ...]:
        """Return models sorted by estimated latency (ascending).

        Models with ``None`` latency sort last.
        """
        return tuple(
            sorted(
                self.all_models(),
                key=lambda m: (
                    m.estimated_latency_ms
                    if m.estimated_latency_ms is not None
                    else float("inf")
                ),
            ),
        )
