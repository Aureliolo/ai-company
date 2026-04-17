"""Per-group metric aggregation for rollout strategies.

A/B and canary rollouts need quality / success / spend samples
bucketed by which group an agent belongs to. The ``GroupSignalAggregator``
protocol captures that shape independently of the underlying data
source. The default implementation wraps ``PerformanceTracker`` and
extracts one sample per agent from its latest snapshot.
"""

from datetime import datetime  # noqa: TC003 -- Pydantic needs at runtime
from typing import TYPE_CHECKING, Protocol, Self, runtime_checkable

from pydantic import BaseModel, ConfigDict, model_validator

from synthorg.core.types import NotBlankStr  # noqa: TC001

if TYPE_CHECKING:
    from synthorg.hr.performance.models import AgentPerformanceSnapshot
    from synthorg.hr.performance.tracker import PerformanceTracker


class GroupSamples(BaseModel):
    """Per-observation samples for a group of agents.

    Sample tuples are aligned: ``agent_ids[i]`` is the source of
    ``quality_samples[i]``, ``success_samples[i]``, and
    ``spend_samples[i]``. Agents with incomplete data are excluded
    entirely so the tuples stay aligned.

    Attributes:
        agent_ids: Agents contributing samples.
        quality_samples: Quality scores (0-10).
        success_samples: Task success rates (0-1).
        spend_samples: Total spend per agent (display currency).
    """

    model_config = ConfigDict(frozen=True, allow_inf_nan=False)

    agent_ids: tuple[NotBlankStr, ...] = ()
    quality_samples: tuple[float, ...] = ()
    success_samples: tuple[float, ...] = ()
    spend_samples: tuple[float, ...] = ()

    @model_validator(mode="after")
    def _validate_aligned_tuples(self) -> Self:
        n = len(self.agent_ids)
        if not (
            len(self.quality_samples) == n
            and len(self.success_samples) == n
            and len(self.spend_samples) == n
        ):
            msg = (
                f"sample tuples must align with agent_ids (n={n}); got "
                f"quality={len(self.quality_samples)}, "
                f"success={len(self.success_samples)}, "
                f"spend={len(self.spend_samples)}"
            )
            raise ValueError(msg)
        return self


@runtime_checkable
class GroupSignalAggregator(Protocol):
    """Collects per-agent metric samples for a single rollout group."""

    async def aggregate_for_agents(
        self,
        *,
        agent_ids: tuple[NotBlankStr, ...],
        since: datetime,
        until: datetime,
    ) -> GroupSamples:
        """Collect samples for the given agents over the time window.

        Args:
            agent_ids: Agents in the group.
            since: Start of the observation window (UTC).
            until: End of the observation window (UTC).

        Returns:
            Aligned sample tuples for quality / success / spend.
        """
        ...


class TrackerGroupAggregator:
    """Default ``GroupSignalAggregator`` backed by ``PerformanceTracker``.

    For each agent, reads the latest snapshot and extracts:

    * ``overall_quality_score`` → ``quality_samples``
    * ``windows[0].success_rate`` → ``success_samples``
    * ``windows[0].avg_cost_per_task * windows[0].tasks_completed`` →
      ``spend_samples``

    An agent contributes a triple only if every component is present.
    Missing components cause the whole triple to be skipped so the
    returned tuples stay aligned.
    """

    def __init__(self, *, tracker: PerformanceTracker) -> None:
        self._tracker = tracker

    async def aggregate_for_agents(
        self,
        *,
        agent_ids: tuple[NotBlankStr, ...],
        since: datetime,
        until: datetime,
    ) -> GroupSamples:
        """Pull samples for each agent from the tracker."""
        _ = since  # tracker snapshots are taken at ``until``
        kept_ids: list[NotBlankStr] = []
        qualities: list[float] = []
        successes: list[float] = []
        spends: list[float] = []
        for agent_id in agent_ids:
            snapshot = await self._tracker.get_snapshot(
                str(agent_id),
                now=until,
            )
            triple = _extract_triple(snapshot)
            if triple is None:
                continue
            q, s, spend = triple
            kept_ids.append(agent_id)
            qualities.append(q)
            successes.append(s)
            spends.append(spend)
        return GroupSamples(
            agent_ids=tuple(kept_ids),
            quality_samples=tuple(qualities),
            success_samples=tuple(successes),
            spend_samples=tuple(spends),
        )


def _extract_triple(
    snapshot: AgentPerformanceSnapshot,
) -> tuple[float, float, float] | None:
    """Return ``(quality, success, spend)`` or ``None`` if incomplete."""
    quality = snapshot.overall_quality_score
    if quality is None:
        return None
    if not snapshot.windows:
        return None
    window = snapshot.windows[0]
    success = window.success_rate
    cost_per_task = window.avg_cost_per_task
    if success is None or cost_per_task is None:
        return None
    spend = cost_per_task * float(window.tasks_completed)
    return quality, success, spend
