"""Factory for building the training service from config."""

from typing import TYPE_CHECKING

from synthorg.hr.training.models import ContentType
from synthorg.observability import get_logger

if TYPE_CHECKING:
    from synthorg.api.approval_store import ApprovalStore
    from synthorg.hr.performance.tracker import PerformanceTracker
    from synthorg.hr.registry import AgentRegistryService
    from synthorg.hr.training.config import TrainingConfig
    from synthorg.hr.training.protocol import (
        ContentExtractor,
        CurationStrategy,
        SourceSelector,
        TrainingGuard,
    )
    from synthorg.hr.training.service import TrainingService
    from synthorg.memory.protocol import MemoryBackend
    from synthorg.providers.protocol import CompletionProvider
    from synthorg.tools.invocation_tracker import ToolInvocationTracker

logger = get_logger(__name__)


def _coerce_positive_int(
    value: object,
    *,
    field_name: str,
    default: int,
) -> int:
    """Coerce a config value to a positive int, falling back on invalid input.

    Args:
        value: The raw value from ``TrainingConfig.*_config``.
        field_name: Name of the field (for error messages).
        default: Default value when ``value`` is missing or invalid.

    Returns:
        The coerced positive integer, or ``default`` on invalid input.
    """
    if value is None:
        return default
    if isinstance(value, bool):
        msg = f"{field_name} must be a positive integer, got bool"
        logger.warning(msg, field_name=field_name, value=value)
        raise TypeError(msg)
    if isinstance(value, int):
        coerced = value
    elif isinstance(value, str):
        try:
            coerced = int(value)
        except ValueError as exc:
            msg = f"{field_name} must be a positive integer, got {value!r}"
            logger.warning(msg, field_name=field_name, value=value)
            raise ValueError(msg) from exc
    else:
        msg = f"{field_name} must be a positive integer, got {type(value).__name__}"
        logger.warning(msg, field_name=field_name, value_type=type(value).__name__)
        raise TypeError(msg)
    if coerced <= 0:
        msg = f"{field_name} must be > 0, got {coerced}"
        logger.warning(msg, field_name=field_name, value=coerced)
        raise ValueError(msg)
    return coerced


def build_training_service(  # noqa: PLR0913
    config: TrainingConfig,
    *,
    memory_backend: MemoryBackend,
    tracker: PerformanceTracker,
    registry: AgentRegistryService,
    approval_store: ApprovalStore,
    tool_tracker: ToolInvocationTracker,
    provider: CompletionProvider | None = None,
) -> TrainingService:
    """Build a fully wired ``TrainingService`` from configuration.

    Args:
        config: Training configuration.
        memory_backend: Memory backend.
        tracker: Performance tracker.
        registry: Agent registry.
        approval_store: Approval store for review gate.
        tool_tracker: Tool invocation tracker.
        provider: LLM completion provider (optional).

    Returns:
        Configured training service.
    """
    from synthorg.hr.training.service import (  # noqa: PLC0415
        TrainingService,
    )

    selector = _build_selector(config, tracker=tracker, registry=registry)
    extractors = _build_extractors(
        config,
        memory_backend=memory_backend,
        tool_tracker=tool_tracker,
    )
    curation = _build_curation(config, provider=provider)
    guards = _build_guards(config, approval_store=approval_store)

    return TrainingService(
        selector=selector,
        extractors=extractors,
        curation=curation,
        guards=guards,
        memory_backend=memory_backend,
        training_namespace=str(config.training_namespace),
        training_tags=tuple(str(t) for t in config.training_tags),
    )


def _build_selector(
    config: TrainingConfig,
    *,
    tracker: PerformanceTracker,
    registry: AgentRegistryService,
) -> SourceSelector:
    """Build source selector from config.

    Note:
        The ``user_curated`` selector type is intentionally not
        available in config: user-curated sources are passed via
        ``TrainingPlan.override_sources`` which the service uses
        directly without routing through a selector.
    """
    selector_type = str(config.source_selector_type)
    _allowed_selectors = {"role_top_performers", "department_diversity"}

    if selector_type not in _allowed_selectors:
        msg = (
            f"Unknown source_selector_type {selector_type!r}; "
            f"supported: {sorted(_allowed_selectors)}"
        )
        logger.warning(msg, selector_type=selector_type)
        raise ValueError(msg)

    if selector_type == "department_diversity":
        from synthorg.hr.training.source_selectors.department_diversity import (  # noqa: PLC0415
            DepartmentDiversitySampling,
        )

        return DepartmentDiversitySampling(
            registry=registry,
            tracker=tracker,
        )

    from synthorg.hr.training.source_selectors.role_top_performers import (  # noqa: PLC0415
        RoleTopPerformers,
    )

    top_n = _coerce_positive_int(
        config.source_selector_config.get("top_n"),
        field_name="source_selector_config.top_n",
        default=3,
    )
    return RoleTopPerformers(
        registry=registry,
        tracker=tracker,
        top_n=top_n,
    )


def _build_extractors(
    config: TrainingConfig,  # noqa: ARG001
    *,
    memory_backend: MemoryBackend,
    tool_tracker: ToolInvocationTracker,
) -> dict[ContentType, ContentExtractor]:
    """Build extractors for all content types."""
    from synthorg.hr.training.extractors.procedural import (  # noqa: PLC0415
        ProceduralMemoryExtractor,
    )
    from synthorg.hr.training.extractors.semantic import (  # noqa: PLC0415
        SemanticMemoryExtractor,
    )
    from synthorg.hr.training.extractors.tool_patterns import (  # noqa: PLC0415
        ToolPatternExtractor,
    )

    return {
        ContentType.PROCEDURAL: ProceduralMemoryExtractor(
            backend=memory_backend,
        ),
        ContentType.SEMANTIC: SemanticMemoryExtractor(
            backend=memory_backend,
        ),
        ContentType.TOOL_PATTERNS: ToolPatternExtractor(
            tracker=tool_tracker,
        ),
    }


def _build_curation(
    config: TrainingConfig,
    *,
    provider: CompletionProvider | None,
) -> CurationStrategy:
    """Build curation strategy from config."""
    strategy_type = str(config.curation_strategy_type)
    _allowed_strategies = {"relevance", "llm_curated"}

    if strategy_type not in _allowed_strategies:
        msg = (
            f"Unknown curation_strategy_type {strategy_type!r}; "
            f"supported: {sorted(_allowed_strategies)}"
        )
        logger.warning(msg, strategy_type=strategy_type)
        raise ValueError(msg)

    top_k = _coerce_positive_int(
        config.curation_strategy_config.get("top_k"),
        field_name="curation_strategy_config.top_k",
        default=50,
    )

    if strategy_type == "llm_curated":
        from synthorg.hr.training.curation.llm_curated import (  # noqa: PLC0415
            LLMCurated,
        )

        return LLMCurated(provider=provider, top_k=top_k)

    from synthorg.hr.training.curation.relevance import (  # noqa: PLC0415
        RelevanceScoreCuration,
    )

    return RelevanceScoreCuration(top_k=top_k)


def _build_guards(
    config: TrainingConfig,
    *,
    approval_store: ApprovalStore,
) -> tuple[TrainingGuard, ...]:
    """Build guard chain from config.

    Always includes SanitizationGuard first (mandatory).
    """
    from synthorg.hr.training.guards.review_gate import (  # noqa: PLC0415
        ReviewGateGuard,
    )
    from synthorg.hr.training.guards.sanitization import (  # noqa: PLC0415
        SanitizationGuard,
    )
    from synthorg.hr.training.guards.volume_cap import (  # noqa: PLC0415
        VolumeCapGuard,
    )

    guards: list[TrainingGuard] = [
        SanitizationGuard(
            max_length=config.sanitization_max_length,
        ),
        VolumeCapGuard(),
        ReviewGateGuard(approval_store=approval_store),
    ]
    return tuple(guards)
