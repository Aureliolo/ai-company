"""Factory functions for client-simulation strategies.

Each strategy family has a configuration discriminator
(``config.strategy`` / ``config.selection_strategy``) that selects a
concrete implementation. The factories below turn those strings into
instances, failing loudly on unknown values so misconfiguration never
silently falls through to a no-op default.
"""

from pathlib import Path
from typing import TYPE_CHECKING

from synthorg.client.adapters import (
    DirectAdapter,
    IntakeAdapter,
    ProjectAdapter,
)
from synthorg.client.feedback.adversarial import AdversarialFeedback
from synthorg.client.feedback.binary import BinaryFeedback
from synthorg.client.feedback.criteria_check import CriteriaCheckFeedback
from synthorg.client.feedback.scored import ScoredFeedback
from synthorg.client.generators.dataset import DatasetGenerator
from synthorg.client.generators.llm import LLMGenerator
from synthorg.client.generators.procedural import ProceduralGenerator
from synthorg.client.generators.template import TemplateGenerator
from synthorg.client.pool import (
    DomainMatchedStrategy,
    RoundRobinStrategy,
    WeightedRandomStrategy,
)
from synthorg.client.report.detailed import DetailedReport
from synthorg.client.report.json_export import JsonExportReport
from synthorg.client.report.metrics_only import MetricsOnlyReport
from synthorg.client.report.summary import SummaryReport

if TYPE_CHECKING:
    from synthorg.client.config import (
        ClientPoolConfig,
        FeedbackConfig,
        ReportConfig,
        RequirementGeneratorConfig,
    )
    from synthorg.client.protocols import (
        ClientPoolStrategy,
        EntryPointStrategy,
        FeedbackStrategy,
        ReportStrategy,
        RequirementGenerator,
    )
    from synthorg.core.types import NotBlankStr
    from synthorg.providers.protocol import CompletionProvider


_GENERATOR_STRATEGIES: frozenset[str] = frozenset(
    {"template", "llm", "dataset", "hybrid", "procedural"},
)
_FEEDBACK_STRATEGIES: frozenset[str] = frozenset(
    {"binary", "scored", "criteria_check", "adversarial"},
)
_REPORT_STRATEGIES: frozenset[str] = frozenset(
    {"summary", "detailed", "json_export", "metrics_only"},
)
_POOL_STRATEGIES: frozenset[str] = frozenset(
    {"round_robin", "weighted_random", "domain_matched"},
)
_ENTRY_POINT_STRATEGIES: frozenset[str] = frozenset(
    {"direct", "project", "intake"},
)


class UnknownStrategyError(ValueError):
    """Raised when a config discriminator does not map to any strategy."""


def build_requirement_generator(
    config: RequirementGeneratorConfig,
    *,
    provider: CompletionProvider | None = None,
    model: NotBlankStr | None = None,
) -> RequirementGenerator:
    """Construct a ``RequirementGenerator`` from configuration.

    Dispatches on ``config.strategy``:

    * ``template`` -> ``TemplateGenerator``
    * ``llm`` -> ``LLMGenerator`` (requires ``provider`` + ``model``)
    * ``dataset`` -> ``DatasetGenerator`` (requires ``dataset_path``)
    * ``procedural`` -> ``ProceduralGenerator``
    * ``hybrid`` -> ``HybridGenerator`` -- callers compose manually.
    """
    strategy = str(config.strategy)
    if strategy == "template":
        if config.template_path is None:
            msg = "template strategy requires config.template_path"
            raise UnknownStrategyError(msg)
        return TemplateGenerator(template_path=Path(config.template_path))
    if strategy == "llm":
        if provider is None:
            msg = "llm strategy requires a provider"
            raise UnknownStrategyError(msg)
        effective_model = model or config.llm_model
        if effective_model is None:
            msg = "llm strategy requires model (argument or config.llm_model)"
            raise UnknownStrategyError(msg)
        return LLMGenerator(provider=provider, model=effective_model)
    if strategy == "dataset":
        if config.dataset_path is None:
            msg = "dataset strategy requires config.dataset_path"
            raise UnknownStrategyError(msg)
        return DatasetGenerator(dataset_path=Path(config.dataset_path))
    if strategy == "procedural":
        return ProceduralGenerator()
    if strategy == "hybrid":
        msg = (
            "hybrid strategy has no single-argument factory; compose "
            "HybridGenerator directly with a tuple of "
            "(generator, weight) pairs"
        )
        raise UnknownStrategyError(msg)
    msg = (
        f"unknown requirement generator strategy {strategy!r}; "
        f"expected one of {sorted(_GENERATOR_STRATEGIES)}"
    )
    raise UnknownStrategyError(msg)


def build_feedback_strategy(
    config: FeedbackConfig,
    *,
    client_id: NotBlankStr,
) -> FeedbackStrategy:
    """Construct a ``FeedbackStrategy`` from configuration.

    Dispatches on ``config.strategy``:

    * ``binary`` -> ``BinaryFeedback``
    * ``scored`` -> ``ScoredFeedback``
    * ``criteria_check`` -> ``CriteriaCheckFeedback``
    * ``adversarial`` -> ``AdversarialFeedback``
    """
    strategy = str(config.strategy)
    if strategy == "binary":
        return BinaryFeedback(
            client_id=client_id,
            strictness_multiplier=config.strictness_multiplier,
        )
    if strategy == "scored":
        return ScoredFeedback(
            client_id=client_id,
            passing_score=config.passing_score,
            strictness_multiplier=config.strictness_multiplier,
        )
    if strategy == "criteria_check":
        return CriteriaCheckFeedback(client_id=client_id)
    if strategy == "adversarial":
        return AdversarialFeedback(client_id=client_id)
    msg = (
        f"unknown feedback strategy {strategy!r}; "
        f"expected one of {sorted(_FEEDBACK_STRATEGIES)}"
    )
    raise UnknownStrategyError(msg)


def build_report_strategy(config: ReportConfig) -> ReportStrategy:
    """Construct a ``ReportStrategy`` from configuration.

    Dispatches on ``config.strategy`` in ``{summary, detailed,
    json_export, metrics_only}``.
    """
    strategy = str(config.strategy)
    if strategy == "summary":
        return SummaryReport()
    if strategy == "detailed":
        return DetailedReport()
    if strategy == "json_export":
        return JsonExportReport()
    if strategy == "metrics_only":
        return MetricsOnlyReport()
    msg = (
        f"unknown report strategy {strategy!r}; "
        f"expected one of {sorted(_REPORT_STRATEGIES)}"
    )
    raise UnknownStrategyError(msg)


def build_client_pool_strategy(
    config: ClientPoolConfig,
) -> ClientPoolStrategy:
    """Construct a ``ClientPoolStrategy`` from configuration.

    Dispatches on ``config.selection_strategy`` in ``{round_robin,
    weighted_random, domain_matched}``. Defaults to ``round_robin``.
    """
    strategy = str(config.selection_strategy)
    if strategy == "round_robin":
        return RoundRobinStrategy()
    if strategy == "weighted_random":
        return WeightedRandomStrategy()
    if strategy == "domain_matched":
        return DomainMatchedStrategy()
    msg = (
        f"unknown pool selection strategy {strategy!r}; "
        f"expected one of {sorted(_POOL_STRATEGIES)}"
    )
    raise UnknownStrategyError(msg)


def build_entry_point_strategy(
    adapter: str,
    *,
    project_id: NotBlankStr | None = None,
) -> EntryPointStrategy:
    """Construct an ``EntryPointStrategy`` from the adapter identifier.

    Dispatches on ``adapter`` in ``{direct, project, intake}``.

    Args:
        adapter: Discriminator identifier.
        project_id: Required when ``adapter == 'project'``.
    """
    if adapter == "direct":
        return DirectAdapter()
    if adapter == "project":
        if project_id is None:
            msg = "project adapter requires project_id"
            raise UnknownStrategyError(msg)
        return ProjectAdapter(project_id=project_id)
    if adapter == "intake":
        return IntakeAdapter()
    msg = (
        f"unknown entry-point adapter {adapter!r}; "
        f"expected one of {sorted(_ENTRY_POINT_STRATEGIES)}"
    )
    raise UnknownStrategyError(msg)
