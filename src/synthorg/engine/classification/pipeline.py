"""Error classification pipeline.

Orchestrates the detection of coordination errors from an execution
result using the configured error taxonomy.  Detectors are discovered
dynamically from the ``ErrorTaxonomyConfig.detectors`` dict and
dispatched via the ``Detector`` protocol.  The pipeline never raises
exceptions -- all errors are caught and logged.
"""

from typing import TYPE_CHECKING

from synthorg.budget.coordination_config import (
    DetectionScope,
    DetectorCategoryConfig,
    DetectorVariant,
    ErrorCategory,
    ErrorTaxonomyConfig,
)
from synthorg.engine.classification.budget_tracker import (
    ClassificationBudgetTracker,
)
from synthorg.engine.classification.composite import CompositeDetector
from synthorg.engine.classification.heuristic_detectors import (
    HeuristicContextOmissionDetector,
    HeuristicContradictionDetector,
    HeuristicCoordinationFailureDetector,
    HeuristicNumericalDriftDetector,
)
from synthorg.engine.classification.loaders import (
    SameTaskLoader,
    TaskTreeLoader,
)
from synthorg.engine.classification.models import (
    ClassificationResult,
    ErrorFinding,
)
from synthorg.engine.classification.protocol_detectors import (
    AuthorityBreachDetector,
    DelegationProtocolDetector,
    ReviewPipelineProtocolDetector,
)
from synthorg.engine.classification.semantic_detectors import (
    SemanticContradictionDetector,
    SemanticCoordinationDetector,
    SemanticMissingReferenceDetector,
    SemanticNumericalVerificationDetector,
)
from synthorg.observability import get_logger
from synthorg.observability.events.classification import (
    CLASSIFICATION_COMPLETE,
    CLASSIFICATION_ERROR,
    CLASSIFICATION_FINDING,
    CLASSIFICATION_SINK_ERROR,
    CLASSIFICATION_SKIPPED,
    CLASSIFICATION_START,
    DETECTOR_ERROR,
)

if TYPE_CHECKING:
    from collections.abc import Callable

    from synthorg.core.types import NotBlankStr
    from synthorg.engine.classification.protocol import (
        ClassificationSink,
        DetectionContext,
        Detector,
        ScopedContextLoader,
    )
    from synthorg.engine.loop_protocol import ExecutionResult
    from synthorg.persistence.repositories import TaskRepository
    from synthorg.providers.base import BaseCompletionProvider
    from synthorg.providers.resilience.rate_limiter import RateLimiter

logger = get_logger(__name__)


# ── Heuristic detector factory map ────────────────────────────

_HEURISTIC_FACTORIES: dict[
    ErrorCategory,
    Callable[[], Detector],
] = {
    ErrorCategory.LOGICAL_CONTRADICTION: HeuristicContradictionDetector,
    ErrorCategory.NUMERICAL_DRIFT: HeuristicNumericalDriftDetector,
    ErrorCategory.CONTEXT_OMISSION: HeuristicContextOmissionDetector,
    ErrorCategory.COORDINATION_FAILURE: HeuristicCoordinationFailureDetector,
}

_PROTOCOL_FACTORIES: dict[
    ErrorCategory,
    Callable[[], Detector],
] = {
    ErrorCategory.DELEGATION_PROTOCOL_VIOLATION: DelegationProtocolDetector,
    ErrorCategory.REVIEW_PIPELINE_VIOLATION: ReviewPipelineProtocolDetector,
}

_BEHAVIOR_FACTORIES: dict[
    ErrorCategory,
    Callable[[], Detector],
] = {
    ErrorCategory.AUTHORITY_BREACH_ATTEMPT: AuthorityBreachDetector,
}


_SEMANTIC_FACTORIES: dict[ErrorCategory, type] = {
    ErrorCategory.LOGICAL_CONTRADICTION: SemanticContradictionDetector,
    ErrorCategory.NUMERICAL_DRIFT: SemanticNumericalVerificationDetector,
    ErrorCategory.CONTEXT_OMISSION: SemanticMissingReferenceDetector,
    ErrorCategory.COORDINATION_FAILURE: SemanticCoordinationDetector,
}

_SIMPLE_FACTORIES: dict[
    DetectorVariant,
    dict[ErrorCategory, Callable[[], Detector]],
] = {
    DetectorVariant.HEURISTIC: _HEURISTIC_FACTORIES,
    DetectorVariant.PROTOCOL_CHECK: _PROTOCOL_FACTORIES,
    DetectorVariant.BEHAVIOR_CHECK: _BEHAVIOR_FACTORIES,
}


def _build_detectors(
    config: ErrorTaxonomyConfig,
    *,
    provider: BaseCompletionProvider | None = None,
    rate_limiter: RateLimiter | None = None,
    budget_tracker: ClassificationBudgetTracker | None = None,
) -> tuple[Detector, ...]:
    """Instantiate detectors from config.

    For each category, instantiates one detector per configured
    variant.  When multiple variants target the same category,
    wraps them in a ``CompositeDetector``.  Skips LLM variants
    when no provider is available.
    """
    detectors: list[Detector] = []

    for category, cat_config in config.detectors.items():
        variants = _build_variants(
            category,
            cat_config,
            config=config,
            provider=provider,
            rate_limiter=rate_limiter,
            budget_tracker=budget_tracker,
        )
        if len(variants) == 1:
            detectors.append(variants[0])
        elif len(variants) > 1:
            detectors.append(
                CompositeDetector(detectors=tuple(variants)),
            )

    return tuple(detectors)


def _build_variants(  # noqa: PLR0913
    category: ErrorCategory,
    cat_config: DetectorCategoryConfig,
    *,
    config: ErrorTaxonomyConfig,
    provider: BaseCompletionProvider | None,
    rate_limiter: RateLimiter | None,
    budget_tracker: ClassificationBudgetTracker | None,
) -> list[Detector]:
    """Build detector instances for a single category."""
    variants: list[Detector] = []
    for variant in cat_config.variants:
        if variant == DetectorVariant.LLM_SEMANTIC:
            _maybe_add_semantic(
                variants,
                category,
                provider=provider,
                model_id=config.llm_provider_tier,
                rate_limiter=rate_limiter,
                budget_tracker=budget_tracker,
            )
        else:
            factory_map = _SIMPLE_FACTORIES.get(variant, {})
            factory = factory_map.get(category)
            if factory is not None:
                variants.append(factory())
    return variants


def _maybe_add_semantic(  # noqa: PLR0913
    variants: list[Detector],
    category: ErrorCategory,
    *,
    provider: BaseCompletionProvider | None,
    model_id: str,
    rate_limiter: RateLimiter | None,
    budget_tracker: ClassificationBudgetTracker | None,
) -> None:
    """Add a semantic detector variant if provider is available."""
    if provider is None:
        logger.warning(
            DETECTOR_ERROR,
            detector=f"semantic({category.value})",
            agent_id="",
            task_id="",
            execution_id="",
            message_count=0,
        )
        return
    sem_cls = _SEMANTIC_FACTORIES.get(category)
    if sem_cls is not None:
        variants.append(
            sem_cls(
                provider=provider,
                model_id=model_id,
                rate_limiter=rate_limiter,
                budget_tracker=budget_tracker,
            ),
        )


def _select_loader(
    scope: DetectionScope,
    task_repo: TaskRepository | None,
) -> ScopedContextLoader:
    """Select context loader for the given scope."""
    if scope == DetectionScope.TASK_TREE and task_repo is not None:
        return TaskTreeLoader(task_repo=task_repo)
    return SameTaskLoader()


async def classify_execution_errors(  # noqa: PLR0913
    execution_result: ExecutionResult,
    agent_id: NotBlankStr,
    task_id: NotBlankStr,
    *,
    config: ErrorTaxonomyConfig,
    task_repo: TaskRepository | None = None,
    provider: BaseCompletionProvider | None = None,
    rate_limiter: RateLimiter | None = None,
    sinks: tuple[ClassificationSink, ...] = (),
) -> ClassificationResult | None:
    """Classify coordination errors from an execution result.

    Discovers detectors from ``config.detectors``, loads
    scope-appropriate context, runs detectors concurrently,
    and dispatches results to registered sinks.

    Returns ``None`` when the taxonomy is disabled.  Never raises --
    all exceptions are caught and logged as ``CLASSIFICATION_ERROR``.

    Args:
        execution_result: The completed execution result to analyse.
        agent_id: Agent that executed the task.
        task_id: Task that was executed.
        config: Error taxonomy configuration.
        task_repo: Optional task repository for TASK_TREE scope.
        provider: Optional LLM provider for semantic detectors.
        rate_limiter: Optional rate limiter for semantic detectors.
        sinks: Downstream consumers to notify after classification.

    Returns:
        Classification result with findings, or ``None`` if disabled.
    """
    if not config.enabled:
        logger.debug(
            CLASSIFICATION_SKIPPED,
            agent_id=agent_id,
            task_id=task_id,
            reason="error taxonomy disabled",
        )
        return None

    execution_id = execution_result.context.execution_id
    logger.info(
        CLASSIFICATION_START,
        agent_id=agent_id,
        task_id=task_id,
        execution_id=execution_id,
        categories=tuple(c.value for c in config.categories),
    )

    try:
        result = await _run_pipeline(
            execution_result,
            agent_id,
            task_id,
            execution_id=execution_id,
            config=config,
            task_repo=task_repo,
            provider=provider,
            rate_limiter=rate_limiter,
        )
    except MemoryError, RecursionError:
        logger.error(
            CLASSIFICATION_ERROR,
            agent_id=agent_id,
            task_id=task_id,
            error="non-recoverable error in classification",
            exc_info=True,
        )
        raise
    except Exception as exc:
        logger.exception(
            CLASSIFICATION_ERROR,
            agent_id=agent_id,
            task_id=task_id,
            error=f"{type(exc).__name__}: {exc}",
        )
        return None

    # Dispatch to sinks (best-effort)
    for sink in sinks:
        try:
            await sink.on_classification(result)
        except MemoryError, RecursionError:
            raise
        except Exception:
            logger.exception(
                CLASSIFICATION_SINK_ERROR,
                agent_id=agent_id,
                task_id=task_id,
            )

    return result


async def _run_pipeline(  # noqa: PLR0913
    execution_result: ExecutionResult,
    agent_id: str,
    task_id: str,
    *,
    execution_id: str,
    config: ErrorTaxonomyConfig,
    task_repo: TaskRepository | None,
    provider: BaseCompletionProvider | None,
    rate_limiter: RateLimiter | None,
) -> ClassificationResult:
    """Build detectors, load contexts, run, and collect findings."""
    budget_tracker = ClassificationBudgetTracker(
        budget_usd=config.classification_budget_per_task_usd,
    )

    all_detectors = _build_detectors(
        config,
        provider=provider,
        rate_limiter=rate_limiter,
        budget_tracker=budget_tracker,
    )

    # Group detectors by their required scope
    scope_detectors: dict[
        DetectionScope,
        list[Detector],
    ] = {}
    for detector in all_detectors:
        # Use the scope from the category config
        cat_cfg: DetectorCategoryConfig = config.detectors[detector.category]
        scope_detectors.setdefault(cat_cfg.scope, []).append(detector)

    # Load contexts per scope and run detectors sequentially.
    # Concurrent execution happens inside CompositeDetector for
    # multi-variant categories.
    all_findings: list[ErrorFinding] = []

    for scope, detectors in scope_detectors.items():
        loader = _select_loader(scope, task_repo)
        context = await loader.load(
            execution_result,
            agent_id,
            task_id,
        )
        for detector in detectors:
            findings = await _safe_detect(
                detector,
                context,
                agent_id,
                task_id,
                execution_id,
            )
            all_findings.extend(findings)

    for finding in all_findings:
        logger.info(
            CLASSIFICATION_FINDING,
            agent_id=agent_id,
            task_id=task_id,
            execution_id=execution_id,
            category=finding.category.value,
            severity=finding.severity.value,
            description=finding.description,
        )

    classification = ClassificationResult(
        execution_id=execution_id,
        agent_id=agent_id,
        task_id=task_id,
        categories_checked=config.categories,
        findings=tuple(all_findings),
    )

    logger.info(
        CLASSIFICATION_COMPLETE,
        agent_id=agent_id,
        task_id=task_id,
        execution_id=execution_id,
        finding_count=classification.finding_count,
    )

    return classification


async def _safe_detect(
    detector: Detector,
    context: DetectionContext,
    agent_id: str,
    task_id: str,
    execution_id: str,
) -> tuple[ErrorFinding, ...]:
    """Run a single detector with isolation.

    Re-raises ``MemoryError`` and ``RecursionError``; catches and
    logs all other exceptions without stopping the pipeline.
    """
    try:
        return await detector.detect(context)
    except MemoryError, RecursionError:
        raise
    except Exception:
        logger.exception(
            DETECTOR_ERROR,
            agent_id=agent_id,
            task_id=task_id,
            execution_id=execution_id,
            detector=type(detector).__name__,
            message_count=0,
        )
        return ()
