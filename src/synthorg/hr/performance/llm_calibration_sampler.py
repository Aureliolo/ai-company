"""LLM-based calibration sampling for collaboration scoring.

Periodically samples a configurable fraction (default 1%) of collaboration
interactions and has an LLM evaluate them independently.  Results are stored
as calibration records for drift analysis against the behavioral strategy.
"""

import json
import random
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING

from synthorg.hr.performance.models import LlmCalibrationRecord
from synthorg.observability import get_logger
from synthorg.observability.events.performance import (
    PERF_LLM_SAMPLE_COMPLETED,
    PERF_LLM_SAMPLE_FAILED,
    PERF_LLM_SAMPLE_STARTED,
)
from synthorg.providers.enums import MessageRole
from synthorg.providers.models import ChatMessage, CompletionConfig

if TYPE_CHECKING:
    from pydantic import AwareDatetime

    from synthorg.core.types import NotBlankStr
    from synthorg.hr.performance.models import CollaborationMetricRecord
    from synthorg.providers.protocol import CompletionProvider

logger = get_logger(__name__)

_SYSTEM_PROMPT = """\
You are evaluating the quality of collaboration in an AI agent interaction.

Given the interaction summary and behavioral metrics below, rate the \
overall collaboration quality on a scale of 0.0 to 10.0.

Respond with JSON only: {{"score": <float>, "rationale": "<brief explanation>"}}

Behavioral metrics (for reference, not the sole basis for your score):
- delegation_success: {delegation_success}
- delegation_response_seconds: {delegation_response_seconds}
- conflict_constructiveness: {conflict_constructiveness}
- meeting_contribution: {meeting_contribution}
- loop_triggered: {loop_triggered}
- handoff_completeness: {handoff_completeness}

Interaction summary:
{interaction_summary}\
"""

_COMPLETION_CONFIG = CompletionConfig(temperature=0.3, max_tokens=256)


class LlmCalibrationSampler:
    """Periodic LLM sampling of collaboration interactions for calibration.

    Samples a configurable fraction of collaboration events and has an
    LLM evaluate them independently.  Results are stored as calibration
    records for drift analysis against the behavioral strategy.

    Args:
        provider: Completion provider for LLM calls.
        model: Model identifier to use for sampling.
        sampling_rate: Fraction of events to sample (0.0-1.0).
        retention_days: Days to retain calibration records.
    """

    def __init__(
        self,
        *,
        provider: CompletionProvider,
        model: NotBlankStr,
        sampling_rate: float = 0.01,
        retention_days: int = 90,
    ) -> None:
        self._provider = provider
        self._model = str(model)
        self._sampling_rate = sampling_rate
        self._retention_days = retention_days
        self._records: dict[str, list[LlmCalibrationRecord]] = {}

    def should_sample(self) -> bool:
        """Determine whether to sample the current event.

        Returns:
            ``True`` if a random draw falls below the sampling rate.
        """
        return random.random() < self._sampling_rate  # noqa: S311

    async def sample(
        self,
        *,
        record: CollaborationMetricRecord,
        behavioral_score: float,
    ) -> LlmCalibrationRecord | None:
        """Sample and evaluate a collaboration interaction via LLM.

        Skips records without ``interaction_summary``.  Provider failures
        are caught and logged — this is best-effort calibration.

        Args:
            record: The collaboration metric record to evaluate.
            behavioral_score: The behavioral strategy's score for context.

        Returns:
            A calibration record, or ``None`` on skip/failure.
        """
        if record.interaction_summary is None:
            return None

        self._prune_expired()

        logger.debug(
            PERF_LLM_SAMPLE_STARTED,
            agent_id=record.agent_id,
            record_id=record.id,
        )

        try:
            llm_score, rationale, cost_usd = await self._call_llm(record)
        except Exception:
            logger.warning(
                PERF_LLM_SAMPLE_FAILED,
                agent_id=record.agent_id,
                record_id=record.id,
                exc_info=True,
            )
            return None

        drift = abs(llm_score - behavioral_score)
        from synthorg.core.types import NotBlankStr  # noqa: PLC0415

        calibration_record = LlmCalibrationRecord(
            agent_id=record.agent_id,
            sampled_at=datetime.now(UTC),
            interaction_record_id=record.id,
            llm_score=llm_score,
            behavioral_score=behavioral_score,
            drift=round(drift, 4),
            rationale=NotBlankStr(rationale),
            model_used=NotBlankStr(self._model),
            cost_usd=cost_usd,
        )

        agent_key = str(record.agent_id)
        if agent_key not in self._records:
            self._records[agent_key] = []
        self._records[agent_key].append(calibration_record)

        logger.info(
            PERF_LLM_SAMPLE_COMPLETED,
            agent_id=record.agent_id,
            llm_score=llm_score,
            behavioral_score=behavioral_score,
            drift=drift,
        )
        return calibration_record

    def get_calibration_records(
        self,
        *,
        agent_id: NotBlankStr | None = None,
        since: AwareDatetime | None = None,
    ) -> tuple[LlmCalibrationRecord, ...]:
        """Query stored calibration records.

        Args:
            agent_id: Filter by agent (``None`` = all agents).
            since: Include records after this time.

        Returns:
            Matching calibration records.
        """
        if agent_id is not None:
            records = list(self._records.get(str(agent_id), []))
        else:
            records = [r for recs in self._records.values() for r in recs]

        if since is not None:
            records = [r for r in records if r.sampled_at >= since]

        return tuple(records)

    def get_drift_summary(
        self,
        agent_id: NotBlankStr,
    ) -> float | None:
        """Compute average drift for an agent.

        Args:
            agent_id: Agent to compute drift for.

        Returns:
            Average drift, or ``None`` if no calibration records exist.
        """
        records = self._records.get(str(agent_id), [])
        if not records:
            return None
        return round(sum(r.drift for r in records) / len(records), 4)

    async def _call_llm(
        self,
        record: CollaborationMetricRecord,
    ) -> tuple[float, str, float]:
        """Call the LLM to evaluate a collaboration interaction.

        Returns:
            Tuple of (score, rationale, cost_usd).

        Raises:
            ValueError: If the LLM response cannot be parsed.
        """
        prompt = _SYSTEM_PROMPT.format(
            delegation_success=record.delegation_success,
            delegation_response_seconds=record.delegation_response_seconds,
            conflict_constructiveness=record.conflict_constructiveness,
            meeting_contribution=record.meeting_contribution,
            loop_triggered=record.loop_triggered,
            handoff_completeness=record.handoff_completeness,
            interaction_summary=record.interaction_summary,
        )

        response = await self._provider.complete(
            messages=[
                ChatMessage(
                    role=MessageRole.USER,
                    content=prompt,
                ),
            ],
            model=self._model,
            config=_COMPLETION_CONFIG,
        )

        if response.content is None:
            msg = "LLM returned no content"
            raise ValueError(msg)

        parsed = json.loads(response.content)
        score = float(parsed["score"])
        rationale = str(parsed["rationale"])

        max_score = 10.0
        if not (0.0 <= score <= max_score):
            msg = f"LLM score {score} outside valid range [0, 10]"
            raise ValueError(msg)

        return score, rationale, response.usage.cost_usd

    def _prune_expired(self) -> None:
        """Remove calibration records older than the retention period."""
        cutoff = datetime.now(UTC) - timedelta(days=self._retention_days)
        for agent_key in list(self._records):
            self._records[agent_key] = [
                r for r in self._records[agent_key] if r.sampled_at >= cutoff
            ]
            if not self._records[agent_key]:
                del self._records[agent_key]
