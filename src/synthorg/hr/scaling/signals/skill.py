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
        agent_ids: tuple[NotBlankStr, ...],  # noqa: ARG002
        *,
        agent_skills: dict[str, tuple[str, ...]] | None = None,
        required_skills: tuple[str, ...] = (),
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

        if not required_skills or not agent_skills:
            return (
                ScalingSignal(
                    name=NotBlankStr("coverage_ratio"),
                    value=1.0 if not required_skills else 0.0,
                    source=_SOURCE_NAME,
                    timestamp=now,
                ),
                ScalingSignal(
                    name=NotBlankStr("missing_skill_count"),
                    value=0.0 if not required_skills else float(len(required_skills)),
                    source=_SOURCE_NAME,
                    timestamp=now,
                ),
            )

        # Union of all agent skills.
        all_skills: set[str] = set()
        for skills in agent_skills.values():
            all_skills.update(skills)

        required_set = set(required_skills)
        covered = required_set & all_skills
        missing_count = len(required_set) - len(covered)
        coverage = len(covered) / len(required_set) if required_set else 1.0

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
