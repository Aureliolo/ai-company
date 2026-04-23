"""Models for the evolution outcome store.

The store records :class:`EvolutionOutcomeRecord` instances; the
aggregator derives a window summary from them.  Records are frozen so
they can be safely returned from the store to callers without copy-on-
read ceremony.
"""

from datetime import UTC, datetime

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field

from synthorg.core.types import NotBlankStr  # noqa: TC001


class EvolutionOutcomeRecord(BaseModel):
    """Terminal record of a proposal that reached a decision.

    Attributes:
        agent_id: Which agent was the target of the proposal.
        axis: Which altitude / axis the proposal targeted (matches
            :class:`~synthorg.meta.models.ProposalAltitude` values).
        applied: ``True`` when the proposal was applied and did not
            roll back; ``False`` for rejected / rolled-back / failed.
        proposed_at: When the proposal was originally generated.
        recorded_at: When the terminal outcome was recorded.
    """

    model_config = ConfigDict(frozen=True, allow_inf_nan=False)

    agent_id: NotBlankStr
    axis: NotBlankStr
    applied: bool
    proposed_at: AwareDatetime
    recorded_at: AwareDatetime = Field(
        default_factory=lambda: datetime.now(UTC),
    )
