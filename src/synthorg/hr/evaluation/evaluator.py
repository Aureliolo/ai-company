"""Evaluation service -- five-pillar orchestrator.

Central service for computing five-pillar evaluation reports.
Delegates to pluggable pillar strategies, computes efficiency
inline, and handles pillar toggling with weight redistribution.
"""

import asyncio
import math
from datetime import UTC, datetime
from typing import TYPE_CHECKING

from synthorg.core.types import NotBlankStr
from synthorg.hr.evaluation.config import EvaluationConfig
from synthorg.hr.evaluation.enums import EvaluationPillar
from synthorg.hr.evaluation.models import (
    EvaluationContext,
    EvaluationReport,
    InteractionFeedback,
    PillarScore,
    ResilienceMetrics,
    redistribute_weights,
)
from synthorg.hr.performance.models import (  # noqa: TC001
    LlmCalibrationRecord,
    TaskMetricRecord,
)
from synthorg.observability import get_logger
from synthorg.observability.events.evaluation import (
    EVAL_FEEDBACK_RECORDED,
    EVAL_PILLAR_SCORED,
    EVAL_PILLAR_SKIPPED,
    EVAL_REPORT_COMPUTED,
)

if TYPE_CHECKING:
    from pydantic import AwareDatetime

    from synthorg.hr.evaluation.pillar_protocol import PillarScoringStrategy
    from synthorg.hr.performance.tracker import PerformanceTracker

logger = get_logger(__name__)

_MAX_SCORE: float = 10.0
_NEUTRAL_SCORE: float = 5.0
_MIN_QUALITY_SCORES_FOR_STDDEV: int = 2


class EvaluationService:
    """Central service for computing five-pillar evaluation reports.

    Delegates to pluggable strategies for Intelligence, Resilience,
    Governance, and Experience pillars. Efficiency is computed inline
    from ``WindowMetrics``. Disabled pillars are skipped and their
    weight redistributed.

    Args:
        tracker: Performance tracker for snapshot and metric data.
        intelligence_strategy: Strategy for Pillar 1 (optional).
        resilience_strategy: Strategy for Pillar 3 (optional).
        governance_strategy: Strategy for Pillar 4 (optional).
        ux_strategy: Strategy for Pillar 5 (optional).
        config: Evaluation configuration (optional, defaults to all
            pillars enabled).
    """

    def __init__(  # noqa: PLR0913
        self,
        *,
        tracker: PerformanceTracker,
        intelligence_strategy: PillarScoringStrategy | None = None,
        resilience_strategy: PillarScoringStrategy | None = None,
        governance_strategy: PillarScoringStrategy | None = None,
        ux_strategy: PillarScoringStrategy | None = None,
        config: EvaluationConfig | None = None,
    ) -> None:
        self._tracker = tracker
        self._config = config or EvaluationConfig()
        self._intelligence = intelligence_strategy or self._default_intelligence()
        self._resilience = resilience_strategy or self._default_resilience()
        self._governance = governance_strategy or self._default_governance()
        self._ux = ux_strategy or self._default_ux()
        self._feedback: dict[str, list[InteractionFeedback]] = {}

    @staticmethod
    def _default_intelligence() -> PillarScoringStrategy:
        from synthorg.hr.evaluation.intelligence_strategy import (  # noqa: PLC0415
            QualityBlendIntelligenceStrategy,
        )

        return QualityBlendIntelligenceStrategy()

    @staticmethod
    def _default_resilience() -> PillarScoringStrategy:
        from synthorg.hr.evaluation.resilience_strategy import (  # noqa: PLC0415
            TaskBasedResilienceStrategy,
        )

        return TaskBasedResilienceStrategy()

    @staticmethod
    def _default_governance() -> PillarScoringStrategy:
        from synthorg.hr.evaluation.governance_strategy import (  # noqa: PLC0415
            AuditBasedGovernanceStrategy,
        )

        return AuditBasedGovernanceStrategy()

    @staticmethod
    def _default_ux() -> PillarScoringStrategy:
        from synthorg.hr.evaluation.experience_strategy import (  # noqa: PLC0415
            FeedbackBasedUxStrategy,
        )

        return FeedbackBasedUxStrategy()

    async def evaluate(
        self,
        agent_id: NotBlankStr,
        *,
        now: AwareDatetime | None = None,
    ) -> EvaluationReport:
        """Compute a five-pillar evaluation report for an agent.

        Skips disabled pillars and redistributes their weight to
        enabled pillars. Scores enabled pillars concurrently.

        Args:
            agent_id: Agent to evaluate.
            now: Reference time (defaults to current UTC time).

        Returns:
            Complete evaluation report with pillar scores.
        """
        if now is None:
            now = datetime.now(UTC)

        cfg = self._config
        snapshot = await self._tracker.get_snapshot(agent_id, now=now)
        task_records = self._tracker.get_task_metrics(agent_id=agent_id)

        # Build calibration records if sampler is available.
        calibration_records: tuple[LlmCalibrationRecord, ...] = ()
        if self._tracker.sampler is not None:
            calibration_records = self._tracker.sampler.get_calibration_records(
                agent_id=agent_id,
            )

        # Build feedback records.
        feedback = tuple(self._feedback.get(str(agent_id), []))

        # Build resilience metrics from task records.
        resilience_metrics = self._compute_resilience_metrics(task_records)

        # Build evaluation context.
        context = EvaluationContext(
            agent_id=agent_id,
            now=now,
            config=cfg,
            snapshot=snapshot,
            task_records=task_records,
            calibration_records=calibration_records,
            feedback=feedback,
            resilience_metrics=resilience_metrics,
        )

        # Determine enabled pillars and their strategies.
        pillar_entries: list[
            tuple[EvaluationPillar, float, PillarScoringStrategy | None]
        ] = [
            (
                EvaluationPillar.INTELLIGENCE,
                cfg.intelligence.weight,
                self._intelligence,
            ),
            (EvaluationPillar.EFFICIENCY, cfg.efficiency.weight, None),  # inline
            (EvaluationPillar.RESILIENCE, cfg.resilience.weight, self._resilience),
            (EvaluationPillar.GOVERNANCE, cfg.governance.weight, self._governance),
            (EvaluationPillar.EXPERIENCE, cfg.experience.weight, self._ux),
        ]

        enabled_flags = {
            EvaluationPillar.INTELLIGENCE: cfg.intelligence.enabled,
            EvaluationPillar.EFFICIENCY: cfg.efficiency.enabled,
            EvaluationPillar.RESILIENCE: cfg.resilience.enabled,
            EvaluationPillar.GOVERNANCE: cfg.governance.enabled,
            EvaluationPillar.EXPERIENCE: cfg.experience.enabled,
        }

        enabled_entries = [(p, w, s) for p, w, s in pillar_entries if enabled_flags[p]]

        for p, _w, _s in pillar_entries:
            if not enabled_flags[p]:
                logger.debug(
                    EVAL_PILLAR_SKIPPED,
                    agent_id=agent_id,
                    pillar=p.value,
                )

        # Redistribute weights among enabled pillars.
        weights = redistribute_weights(
            [(p.value, w, True) for p, w, _ in enabled_entries],
        )

        # Score all enabled pillars concurrently.
        pillar_scores: list[PillarScore] = []
        async with asyncio.TaskGroup() as tg:
            tasks: dict[EvaluationPillar, asyncio.Task[PillarScore]] = {}
            for pillar, _weight, strategy in enabled_entries:
                if strategy is not None:
                    tasks[pillar] = tg.create_task(
                        strategy.score(context=context),
                    )
                else:
                    # Efficiency is inline.
                    tasks[pillar] = tg.create_task(
                        self._score_efficiency(context),
                    )

        for pillar, _weight, _strategy in enabled_entries:
            pillar_scores.append(tasks[pillar].result())

        # Compute weighted overall score and confidence.
        overall_score = 0.0
        overall_confidence = 0.0
        for ps in pillar_scores:
            w = weights.get(ps.pillar.value, 0.0)
            overall_score += ps.score * w
            overall_confidence += ps.confidence * w

        overall_score = max(0.0, min(_MAX_SCORE, overall_score))
        overall_confidence = max(0.0, min(1.0, overall_confidence))

        pillar_weights = tuple(
            (NotBlankStr(k), round(v, 6)) for k, v in sorted(weights.items())
        )

        report = EvaluationReport(
            agent_id=agent_id,
            computed_at=now,
            snapshot=snapshot,
            pillar_scores=tuple(pillar_scores),
            overall_score=round(overall_score, 4),
            overall_confidence=round(overall_confidence, 4),
            pillar_weights=pillar_weights,
        )

        logger.info(
            EVAL_REPORT_COMPUTED,
            agent_id=agent_id,
            pillar_count=len(pillar_scores),
            overall_score=report.overall_score,
            overall_confidence=report.overall_confidence,
        )
        return report

    async def record_feedback(
        self,
        feedback: InteractionFeedback,
    ) -> InteractionFeedback:
        """Store interaction feedback for UX pillar scoring.

        Args:
            feedback: Interaction feedback to store.

        Returns:
            The stored feedback record.
        """
        agent_key = str(feedback.agent_id)
        if agent_key not in self._feedback:
            self._feedback[agent_key] = []
        self._feedback[agent_key].append(feedback)

        logger.info(
            EVAL_FEEDBACK_RECORDED,
            agent_id=feedback.agent_id,
            source=feedback.source,
        )
        return feedback

    def get_feedback(
        self,
        *,
        agent_id: NotBlankStr | None = None,
        since: AwareDatetime | None = None,
    ) -> tuple[InteractionFeedback, ...]:
        """Query stored feedback records.

        Args:
            agent_id: Filter by agent (None = all agents).
            since: Include records after this time.

        Returns:
            Matching feedback records.
        """
        if agent_id is not None:
            records = list(self._feedback.get(str(agent_id), []))
        else:
            records = [r for recs in self._feedback.values() for r in recs]

        if since is not None:
            records = [r for r in records if r.recorded_at >= since]
        return tuple(records)

    async def _score_efficiency(
        self,
        context: EvaluationContext,
    ) -> PillarScore:
        """Compute efficiency pillar score inline from WindowMetrics.

        Uses the 30d window (falling back to 7d) for cost, time,
        and token efficiency sub-metrics.
        """
        cfg = context.config.efficiency
        snapshot = context.snapshot

        # Find best window (prefer 30d, fall back to 7d).
        window_map = {w.window_size: w for w in snapshot.windows}
        window = window_map.get("30d") or window_map.get("7d")

        if window is None or window.data_point_count == 0:
            return PillarScore(
                pillar=EvaluationPillar.EFFICIENCY,
                score=_NEUTRAL_SCORE,
                confidence=0.0,
                strategy_name=NotBlankStr("inline_efficiency"),
                data_point_count=0,
                evaluated_at=context.now,
            )

        metrics: list[tuple[str, float, bool]] = []
        scores: dict[str, float] = {}

        if cfg.cost_enabled and window.avg_cost_per_task is not None:
            cost_score = max(
                0.0,
                _MAX_SCORE * (1.0 - window.avg_cost_per_task / cfg.reference_cost_usd),
            )
            scores["cost"] = min(_MAX_SCORE, cost_score)
            metrics.append(("cost", cfg.cost_weight, True))

        if cfg.time_enabled and window.avg_completion_time_seconds is not None:
            time_score = max(
                0.0,
                _MAX_SCORE
                * (
                    1.0
                    - window.avg_completion_time_seconds / cfg.reference_time_seconds
                ),
            )
            scores["time"] = min(_MAX_SCORE, time_score)
            metrics.append(("time", cfg.time_weight, True))

        if cfg.tokens_enabled and window.avg_tokens_per_task is not None:
            token_score = max(
                0.0,
                _MAX_SCORE * (1.0 - window.avg_tokens_per_task / cfg.reference_tokens),
            )
            scores["tokens"] = min(_MAX_SCORE, token_score)
            metrics.append(("tokens", cfg.tokens_weight, True))

        if not metrics:
            return PillarScore(
                pillar=EvaluationPillar.EFFICIENCY,
                score=_NEUTRAL_SCORE,
                confidence=0.0,
                strategy_name=NotBlankStr("inline_efficiency"),
                data_point_count=window.data_point_count,
                evaluated_at=context.now,
            )

        weights = redistribute_weights(metrics)
        weighted_sum = sum(scores[k] * weights[k] for k in weights)
        final_score = max(0.0, min(_MAX_SCORE, weighted_sum))

        breakdown = tuple(
            (NotBlankStr(k), round(v, 4)) for k, v in sorted(scores.items())
        )
        confidence = min(1.0, window.data_point_count / 10.0)

        result = PillarScore(
            pillar=EvaluationPillar.EFFICIENCY,
            score=round(final_score, 4),
            confidence=round(confidence, 4),
            strategy_name=NotBlankStr("inline_efficiency"),
            breakdown=breakdown,
            data_point_count=window.data_point_count,
            evaluated_at=context.now,
        )

        logger.debug(
            EVAL_PILLAR_SCORED,
            agent_id=context.agent_id,
            pillar=EvaluationPillar.EFFICIENCY.value,
            score=result.score,
        )
        return result

    @staticmethod
    def _compute_resilience_metrics(
        records: tuple[TaskMetricRecord, ...],
    ) -> ResilienceMetrics:
        """Derive resilience metrics from raw task records.

        Computes recovery count, streaks, and quality score stddev.
        """
        total = len(records)
        if total == 0:
            return ResilienceMetrics(
                total_tasks=0,
                failed_tasks=0,
                recovered_tasks=0,
                current_success_streak=0,
                longest_success_streak=0,
            )

        # Sort by completion time.
        sorted_records = sorted(records, key=lambda r: r.completed_at)

        failed = sum(1 for r in sorted_records if not r.is_success)
        recovered = 0
        current_streak = 0
        longest_streak = 0
        prev_failed = False

        for record in sorted_records:
            if record.is_success:
                current_streak += 1
                longest_streak = max(longest_streak, current_streak)
                if prev_failed:
                    recovered += 1
                prev_failed = False
            else:
                current_streak = 0
                prev_failed = True

        # Quality score stddev.
        quality_scores = [
            r.quality_score for r in sorted_records if r.quality_score is not None
        ]
        stddev: float | None = None
        if len(quality_scores) >= _MIN_QUALITY_SCORES_FOR_STDDEV:
            mean = sum(quality_scores) / len(quality_scores)
            variance = sum((s - mean) ** 2 for s in quality_scores) / len(
                quality_scores,
            )
            stddev = round(math.sqrt(variance), 4)

        return ResilienceMetrics(
            total_tasks=total,
            failed_tasks=failed,
            recovered_tasks=min(recovered, failed),
            current_success_streak=current_streak,
            longest_success_streak=longest_streak,
            quality_score_stddev=stddev,
        )
