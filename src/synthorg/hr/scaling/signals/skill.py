"""Skill signal source -- reads agent skills and task requirements."""

from datetime import UTC, datetime

from synthorg.core.types import NotBlankStr
from synthorg.hr.scaling.models import ScalingSignal
from synthorg.observability import get_logger

logger = get_logger(__name__)

_SOURCE_NAME = NotBlankStr("skill")


class SkillSignalSource:
    """Read-only adapter over agent skill inventories.

    Compares the set of skills required by pending/recent tasks
    against the union of agent skills to identify coverage gaps.
    """

    @property
    def name(self) -> NotBlankStr:
        """Source identifier."""
        return _SOURCE_NAME

    async def collect(
        self,
        agent_ids: tuple[NotBlankStr, ...],
        *,
        agent_skills: dict[NotBlankStr, tuple[NotBlankStr, ...]] | None = None,
        required_skills: tuple[NotBlankStr, ...] = (),
    ) -> tuple[ScalingSignal, ...]:
        """Collect skill coverage signals.

        Args:
            agent_ids: Active agent IDs.
            agent_skills: Mapping of agent_id to their skill names.
            required_skills: Skills required by pending/recent tasks.

        Returns:
            Skill signals: coverage_ratio, missing_skill_count.
        """
        now = datetime.now(UTC)
        unique_required = set(required_skills)

        if not unique_required or not agent_skills:
            return (
                ScalingSignal(
                    name=NotBlankStr("coverage_ratio"),
                    value=1.0 if not unique_required else 0.0,
                    source=_SOURCE_NAME,
                    timestamp=now,
                ),
                ScalingSignal(
                    name=NotBlankStr("missing_skill_count"),
                    value=0.0 if not unique_required else float(len(unique_required)),
                    source=_SOURCE_NAME,
                    timestamp=now,
                ),
            )

        all_skills: set[NotBlankStr] = set()
        for aid in agent_ids:
            all_skills.update(agent_skills.get(aid, ()))

        covered = unique_required & all_skills
        missing_count = len(unique_required) - len(covered)
        coverage = len(covered) / len(unique_required) if unique_required else 1.0

        return (
            ScalingSignal(
                name=NotBlankStr("coverage_ratio"),
                value=round(coverage, 4),
                source=_SOURCE_NAME,
                timestamp=now,
            ),
            ScalingSignal(
                name=NotBlankStr("missing_skill_count"),
                value=float(missing_count),
                source=_SOURCE_NAME,
                timestamp=now,
            ),
        )
