"""Model resolver — maps aliases and model IDs to ``ResolvedModel``.

Built from ``dict[str, ProviderConfig]`` at construction time.  Indexes
every model ID and alias to a ``ResolvedModel``.  Uses
``MappingProxyType`` for immutability (matches ``ProviderRegistry``
pattern).
"""

from types import MappingProxyType
from typing import TYPE_CHECKING

from ai_company.observability import get_logger
from ai_company.observability.events import (
    ROUTING_MODEL_RESOLUTION_FAILED,
    ROUTING_MODEL_RESOLVED,
    ROUTING_RESOLVER_BUILT,
)

from .errors import ModelResolutionError
from .models import ResolvedModel

logger = get_logger(__name__)

if TYPE_CHECKING:
    from ai_company.config.schema import ProviderConfig


class ModelResolver:
    """Resolves model aliases and IDs to ``ResolvedModel`` instances.

    Built from the providers section of the company config.  Each model
    ID and alias is indexed for O(1) lookup.

    Examples:
        Build from config::

            resolver = ModelResolver.from_config(root_config.providers)
            model = resolver.resolve("sonnet")
    """

    def __init__(
        self,
        index: dict[str, ResolvedModel],
    ) -> None:
        """Initialize with a pre-built ref -> model index.

        Args:
            index: Mutable dict of model ref to resolved model.
                The resolver takes ownership and freezes a copy.
        """
        self._index: MappingProxyType[str, ResolvedModel] = MappingProxyType(
            dict(index),
        )

    @classmethod
    def from_config(
        cls,
        providers: dict[str, ProviderConfig],
    ) -> ModelResolver:
        """Build a resolver from a provider config dict.

        Args:
            providers: Provider config dict (key = provider name).

        Returns:
            A new ``ModelResolver`` with all models indexed.
        """
        index: dict[str, ResolvedModel] = {}

        for provider_name, provider_config in providers.items():
            for model_config in provider_config.models:
                resolved = ResolvedModel(
                    provider_name=provider_name,
                    model_id=model_config.id,
                    alias=model_config.alias,
                    cost_per_1k_input=model_config.cost_per_1k_input,
                    cost_per_1k_output=model_config.cost_per_1k_output,
                    max_context=model_config.max_context,
                )
                index[model_config.id] = resolved
                if model_config.alias is not None:
                    index[model_config.alias] = resolved

        logger.info(
            ROUTING_RESOLVER_BUILT,
            model_count=len(index),
            providers=sorted(providers),
        )
        return cls(index)

    def resolve(self, ref: str) -> ResolvedModel:
        """Resolve a model alias or ID to a ``ResolvedModel``.

        Args:
            ref: Model alias or ID string.

        Returns:
            The resolved model.

        Raises:
            ModelResolutionError: If the ref is not found.
        """
        model = self._index.get(ref)
        if model is None:
            logger.warning(
                ROUTING_MODEL_RESOLUTION_FAILED,
                ref=ref,
                available=sorted(self._index),
            )
            msg = f"Model reference {ref!r} not found. Available: {sorted(self._index)}"
            raise ModelResolutionError(msg, context={"ref": ref})
        logger.debug(
            ROUTING_MODEL_RESOLVED,
            ref=ref,
            provider=model.provider_name,
            model_id=model.model_id,
        )
        return model

    def resolve_safe(self, ref: str) -> ResolvedModel | None:
        """Resolve a model ref without raising.

        Args:
            ref: Model alias or ID string.

        Returns:
            The resolved model, or ``None`` if not found.
        """
        return self._index.get(ref)

    def all_models(self) -> tuple[ResolvedModel, ...]:
        """Return deduplicated tuple of all resolved models."""
        seen_ids: set[str] = set()
        unique: list[ResolvedModel] = []
        for model in self._index.values():
            if model.model_id not in seen_ids:
                seen_ids.add(model.model_id)
                unique.append(model)
        return tuple(unique)

    def all_models_sorted_by_cost(self) -> tuple[ResolvedModel, ...]:
        """Return models sorted by total cost (ascending).

        Total cost is ``cost_per_1k_input + cost_per_1k_output``.
        """
        return tuple(
            sorted(
                self.all_models(),
                key=lambda m: m.cost_per_1k_input + m.cost_per_1k_output,
            ),
        )
