"""Tests for client-simulation factory dispatch."""

import pytest

from synthorg.client.adapters import (
    DirectAdapter,
    IntakeAdapter,
    ProjectAdapter,
)
from synthorg.client.config import (
    ClientPoolConfig,
    FeedbackConfig,
    ReportConfig,
    RequirementGeneratorConfig,
)
from synthorg.client.factory import (
    UnknownStrategyError,
    build_client_pool_strategy,
    build_entry_point_strategy,
    build_feedback_strategy,
    build_report_strategy,
    build_requirement_generator,
)
from synthorg.client.feedback.adversarial import AdversarialFeedback
from synthorg.client.feedback.binary import BinaryFeedback
from synthorg.client.feedback.criteria_check import CriteriaCheckFeedback
from synthorg.client.feedback.scored import ScoredFeedback
from synthorg.client.generators.procedural import ProceduralGenerator
from synthorg.client.pool import (
    DomainMatchedStrategy,
    RoundRobinStrategy,
    WeightedRandomStrategy,
)
from synthorg.client.report.detailed import DetailedReport
from synthorg.client.report.json_export import JsonExportReport
from synthorg.client.report.metrics_only import MetricsOnlyReport
from synthorg.client.report.summary import SummaryReport
from synthorg.core.types import NotBlankStr

pytestmark = pytest.mark.unit


class TestFeedbackFactory:
    def test_binary(self) -> None:
        impl = build_feedback_strategy(
            FeedbackConfig(strategy="binary"),
            client_id=NotBlankStr("c1"),
        )
        assert isinstance(impl, BinaryFeedback)

    def test_scored(self) -> None:
        impl = build_feedback_strategy(
            FeedbackConfig(strategy="scored", passing_score=0.75),
            client_id=NotBlankStr("c1"),
        )
        assert isinstance(impl, ScoredFeedback)

    def test_criteria_check(self) -> None:
        impl = build_feedback_strategy(
            FeedbackConfig(strategy="criteria_check"),
            client_id=NotBlankStr("c1"),
        )
        assert isinstance(impl, CriteriaCheckFeedback)

    def test_adversarial(self) -> None:
        impl = build_feedback_strategy(
            FeedbackConfig(strategy="adversarial"),
            client_id=NotBlankStr("c1"),
        )
        assert isinstance(impl, AdversarialFeedback)

    def test_unknown_raises(self) -> None:
        with pytest.raises(UnknownStrategyError, match="unknown feedback"):
            build_feedback_strategy(
                FeedbackConfig(strategy="bogus"),
                client_id=NotBlankStr("c1"),
            )


class TestReportFactory:
    def test_summary(self) -> None:
        assert isinstance(
            build_report_strategy(ReportConfig(strategy="summary")),
            SummaryReport,
        )

    def test_detailed(self) -> None:
        assert isinstance(
            build_report_strategy(ReportConfig(strategy="detailed")),
            DetailedReport,
        )

    def test_json_export(self) -> None:
        assert isinstance(
            build_report_strategy(ReportConfig(strategy="json_export")),
            JsonExportReport,
        )

    def test_metrics_only(self) -> None:
        assert isinstance(
            build_report_strategy(ReportConfig(strategy="metrics_only")),
            MetricsOnlyReport,
        )

    def test_unknown_raises(self) -> None:
        with pytest.raises(UnknownStrategyError, match="unknown report"):
            build_report_strategy(ReportConfig(strategy="xml"))


class TestPoolStrategyFactory:
    def test_round_robin(self) -> None:
        impl = build_client_pool_strategy(
            ClientPoolConfig(selection_strategy="round_robin"),
        )
        assert isinstance(impl, RoundRobinStrategy)

    def test_weighted_random(self) -> None:
        impl = build_client_pool_strategy(
            ClientPoolConfig(selection_strategy="weighted_random"),
        )
        assert isinstance(impl, WeightedRandomStrategy)

    def test_domain_matched(self) -> None:
        impl = build_client_pool_strategy(
            ClientPoolConfig(selection_strategy="domain_matched"),
        )
        assert isinstance(impl, DomainMatchedStrategy)

    def test_default_is_round_robin(self) -> None:
        impl = build_client_pool_strategy(ClientPoolConfig())
        assert isinstance(impl, RoundRobinStrategy)

    def test_unknown_raises(self) -> None:
        with pytest.raises(UnknownStrategyError, match="pool selection"):
            build_client_pool_strategy(
                ClientPoolConfig(selection_strategy="unknown"),
            )


class TestEntryPointFactory:
    def test_direct(self) -> None:
        assert isinstance(build_entry_point_strategy("direct"), DirectAdapter)

    def test_project_requires_id(self) -> None:
        with pytest.raises(UnknownStrategyError, match="project_id"):
            build_entry_point_strategy("project")

    def test_project_with_id(self) -> None:
        impl = build_entry_point_strategy(
            "project",
            project_id=NotBlankStr("proj-123"),
        )
        assert isinstance(impl, ProjectAdapter)

    def test_intake(self) -> None:
        assert isinstance(build_entry_point_strategy("intake"), IntakeAdapter)

    def test_unknown_raises(self) -> None:
        with pytest.raises(UnknownStrategyError, match="entry-point"):
            build_entry_point_strategy("unknown")


class TestRequirementGeneratorFactory:
    def test_procedural(self) -> None:
        impl = build_requirement_generator(
            RequirementGeneratorConfig(strategy="procedural"),
        )
        assert isinstance(impl, ProceduralGenerator)

    def test_template_requires_path(self) -> None:
        with pytest.raises(UnknownStrategyError, match="template_path"):
            build_requirement_generator(
                RequirementGeneratorConfig(strategy="template"),
            )

    def test_dataset_requires_path(self) -> None:
        with pytest.raises(UnknownStrategyError, match="dataset_path"):
            build_requirement_generator(
                RequirementGeneratorConfig(strategy="dataset"),
            )

    def test_llm_requires_provider(self) -> None:
        with pytest.raises(UnknownStrategyError, match="provider"):
            build_requirement_generator(
                RequirementGeneratorConfig(strategy="llm"),
            )

    def test_hybrid_rejects_single_arg(self) -> None:
        with pytest.raises(UnknownStrategyError, match="hybrid"):
            build_requirement_generator(
                RequirementGeneratorConfig(strategy="hybrid"),
            )

    def test_unknown_raises(self) -> None:
        with pytest.raises(
            UnknownStrategyError,
            match="unknown requirement generator",
        ):
            build_requirement_generator(
                RequirementGeneratorConfig(strategy="mystery"),
            )
