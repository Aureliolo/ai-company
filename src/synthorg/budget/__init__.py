"""Budget and cost tracking domain models.

This module provides the domain models for budget configuration, cost
tracking, budget hierarchy, and spending summaries as described in
the Operations design page.
"""

from synthorg.budget.automated_reports import AutomatedReportService
from synthorg.budget.baseline_store import BaselineRecord, BaselineStore
from synthorg.budget.billing import billing_period_start, daily_period_start
from synthorg.budget.call_analytics import CallAnalyticsService
from synthorg.budget.call_analytics_config import CallAnalyticsConfig, RetryAlertConfig
from synthorg.budget.call_analytics_models import AnalyticsAggregation
from synthorg.budget.call_category import LLMCallCategory, OrchestrationAlertLevel
from synthorg.budget.call_classifier import (
    CallClassificationStrategy,
    ClassificationContext,
    RulesBasedClassifier,
    classify_call,
)
from synthorg.budget.category_analytics import CategoryBreakdown, OrchestrationRatio
from synthorg.budget.config import (
    AutoDowngradeConfig,
    BudgetAlertConfig,
    BudgetConfig,
)
from synthorg.budget.coordination_collector import (
    CoordinationMetricsCollector,
    SimilarityComputer,
)
from synthorg.budget.coordination_config import (
    CoordinationMetricName,
    CoordinationMetricsConfig,
    ErrorCategory,
    ErrorTaxonomyConfig,
    OrchestrationAlertThresholds,
)
from synthorg.budget.coordination_metrics import (
    AmdahlCeiling,
    CoordinationEfficiency,
    CoordinationMetrics,
    CoordinationOverhead,
    ErrorAmplification,
    MessageDensity,
    MessageOverhead,
    RedundancyRate,
    StragglerGap,
    TokenSpeedupRatio,
)
from synthorg.budget.cost_record import CostRecord
from synthorg.budget.cost_tiers import (
    BUILTIN_TIERS,
    CostTierDefinition,
    CostTiersConfig,
    classify_model_tier,
    resolve_tiers,
)
from synthorg.budget.currency import (
    CURRENCY_SYMBOLS,
    DEFAULT_CURRENCY,
    MINOR_UNITS,
    format_cost,
    format_cost_detail,
    get_currency_symbol,
)
from synthorg.budget.degradation import DegradationResult, PreFlightResult
from synthorg.budget.enforcer import BudgetEnforcer
from synthorg.budget.enums import BudgetAlertLevel
from synthorg.budget.errors import (
    BudgetExhaustedError,
    DailyLimitExceededError,
    QuotaExhaustedError,
    RiskBudgetExhaustedError,
)
from synthorg.budget.hierarchy import (
    BudgetHierarchy,
    DepartmentBudget,
    TeamBudget,
)
from synthorg.budget.optimizer import CostOptimizer
from synthorg.budget.optimizer_models import (
    AgentEfficiency,
    AnomalyDetectionResult,
    AnomalySeverity,
    AnomalyType,
    ApprovalDecision,
    CostOptimizerConfig,
    DowngradeAnalysis,
    DowngradeRecommendation,
    EfficiencyAnalysis,
    EfficiencyRating,
    RoutingOptimizationAnalysis,
    RoutingSuggestion,
    SpendingAnomaly,
)
from synthorg.budget.quota import (
    DegradationAction,
    DegradationConfig,
    ProviderCostModel,
    QuotaCheckResult,
    QuotaLimit,
    QuotaSnapshot,
    QuotaWindow,
    SubscriptionConfig,
    effective_cost_per_1k,
)
from synthorg.budget.quota_poller import QuotaPoller
from synthorg.budget.quota_poller_config import QuotaAlertThresholds, QuotaPollerConfig
from synthorg.budget.quota_tracker import QuotaTracker
from synthorg.budget.rebalance import RebalanceMode, RebalanceResult, compute_rebalance
from synthorg.budget.report_config import (
    AutomatedReportingConfig,
    ReportPeriod,
    ReportScheduleConfig,
    ReportTemplateName,
)
from synthorg.budget.report_templates import (
    AgentPerformanceSummary,
    ComprehensiveReport,
    DailyRiskPoint,
    DepartmentTaskSummary,
    PerformanceMetricsReport,
    RiskTrendsReport,
    TaskCompletionReport,
)
from synthorg.budget.reports import (
    ModelDistribution,
    PeriodComparison,
    ProviderDistribution,
    ReportGenerator,
    SpendingReport,
    TaskSpending,
)
from synthorg.budget.risk_check import RiskCheckResult
from synthorg.budget.risk_config import RiskBudgetAlertConfig, RiskBudgetConfig
from synthorg.budget.risk_record import RiskRecord
from synthorg.budget.risk_tracker import RiskTracker
from synthorg.budget.spending_summary import (
    AgentSpending,
    DepartmentSpending,
    PeriodSpending,
    SpendingSummary,
)
from synthorg.budget.tracker import CostTracker

__all__ = [
    "BUILTIN_TIERS",
    "CURRENCY_SYMBOLS",
    "DEFAULT_CURRENCY",
    "MINOR_UNITS",
    "AgentEfficiency",
    "AgentPerformanceSummary",
    "AgentSpending",
    "AmdahlCeiling",
    "AnalyticsAggregation",
    "AnomalyDetectionResult",
    "AnomalySeverity",
    "AnomalyType",
    "ApprovalDecision",
    "AutoDowngradeConfig",
    "AutomatedReportService",
    "AutomatedReportingConfig",
    "BaselineRecord",
    "BaselineStore",
    "BudgetAlertConfig",
    "BudgetAlertLevel",
    "BudgetConfig",
    "BudgetEnforcer",
    "BudgetExhaustedError",
    "BudgetHierarchy",
    "CallAnalyticsConfig",
    "CallAnalyticsService",
    "CallClassificationStrategy",
    "CategoryBreakdown",
    "ClassificationContext",
    "ComprehensiveReport",
    "CoordinationEfficiency",
    "CoordinationMetricName",
    "CoordinationMetrics",
    "CoordinationMetricsCollector",
    "CoordinationMetricsConfig",
    "CoordinationOverhead",
    "CostOptimizer",
    "CostOptimizerConfig",
    "CostRecord",
    "CostTierDefinition",
    "CostTiersConfig",
    "CostTracker",
    "DailyLimitExceededError",
    "DailyRiskPoint",
    "DegradationAction",
    "DegradationConfig",
    "DegradationResult",
    "DepartmentBudget",
    "DepartmentSpending",
    "DepartmentTaskSummary",
    "DowngradeAnalysis",
    "DowngradeRecommendation",
    "EfficiencyAnalysis",
    "EfficiencyRating",
    "ErrorAmplification",
    "ErrorCategory",
    "ErrorTaxonomyConfig",
    "LLMCallCategory",
    "MessageDensity",
    "MessageOverhead",
    "ModelDistribution",
    "OrchestrationAlertLevel",
    "OrchestrationAlertThresholds",
    "OrchestrationRatio",
    "PerformanceMetricsReport",
    "PeriodComparison",
    "PeriodSpending",
    "PreFlightResult",
    "ProviderCostModel",
    "ProviderDistribution",
    "QuotaAlertThresholds",
    "QuotaCheckResult",
    "QuotaExhaustedError",
    "QuotaLimit",
    "QuotaPoller",
    "QuotaPollerConfig",
    "QuotaSnapshot",
    "QuotaTracker",
    "QuotaWindow",
    "RebalanceMode",
    "RebalanceResult",
    "RedundancyRate",
    "ReportGenerator",
    "ReportPeriod",
    "ReportScheduleConfig",
    "ReportTemplateName",
    "RetryAlertConfig",
    "RiskBudgetAlertConfig",
    "RiskBudgetConfig",
    "RiskBudgetExhaustedError",
    "RiskCheckResult",
    "RiskRecord",
    "RiskTracker",
    "RiskTrendsReport",
    "RoutingOptimizationAnalysis",
    "RoutingSuggestion",
    "RulesBasedClassifier",
    "SimilarityComputer",
    "SpendingAnomaly",
    "SpendingReport",
    "SpendingSummary",
    "StragglerGap",
    "SubscriptionConfig",
    "TaskCompletionReport",
    "TaskSpending",
    "TeamBudget",
    "TokenSpeedupRatio",
    "billing_period_start",
    "classify_call",
    "classify_model_tier",
    "compute_rebalance",
    "daily_period_start",
    "effective_cost_per_1k",
    "format_cost",
    "format_cost_detail",
    "get_currency_symbol",
    "resolve_tiers",
]
