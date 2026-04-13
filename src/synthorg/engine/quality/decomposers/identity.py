"""Identity criteria decomposer -- one probe per criterion."""

from typing import TYPE_CHECKING

from synthorg.engine.quality.verification import AtomicProbe

if TYPE_CHECKING:
    from synthorg.core.task import AcceptanceCriterion
    from synthorg.core.types import NotBlankStr


class IdentityCriteriaDecomposer:
    """Deterministic decomposer that emits one probe per criterion.

    Used in tests and as a no-LLM fallback.
    """

    @property
    def name(self) -> str:
        """Strategy name."""
        return "identity"

    async def decompose(
        self,
        criteria: tuple[AcceptanceCriterion, ...],
        *,
        task_id: NotBlankStr,
        agent_id: NotBlankStr,  # noqa: ARG002
    ) -> tuple[AtomicProbe, ...]:
        """Map each criterion to a single binary probe."""
        return tuple(
            AtomicProbe(
                id=f"{task_id}-probe-{i}",
                probe_text=f"Is the criterion satisfied: {c.description}",
                source_criterion=c.description,
            )
            for i, c in enumerate(criteria)
        )
