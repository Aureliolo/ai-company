"""Durable per-project cost aggregate model and repository protocol.

Stores lifetime cost totals per project, surviving the in-memory
CostTracker's 168-hour retention window.  Updated atomically on
each cost recording; queried by BudgetEnforcer for project-level
budget enforcement.
"""

from typing import Protocol, runtime_checkable

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field

from synthorg.core.types import NotBlankStr  # noqa: TC001


class ProjectCostAggregate(BaseModel):
    """Immutable snapshot of a project's lifetime cost totals.

    One row per project in the ``project_cost_aggregates`` table.
    Totals are monotonically increasing (never pruned).

    Attributes:
        project_id: Unique project identifier (primary key).
        total_cost: Accumulated cost in base currency.
        total_input_tokens: Accumulated input token count.
        total_output_tokens: Accumulated output token count.
        record_count: Number of cost records aggregated.
        last_updated: Timestamp of the most recent increment.
    """

    model_config = ConfigDict(frozen=True, allow_inf_nan=False)

    project_id: NotBlankStr = Field(description="Project identifier")
    total_cost: float = Field(ge=0.0, description="Accumulated cost")
    total_input_tokens: int = Field(
        ge=0,
        description="Accumulated input tokens",
    )
    total_output_tokens: int = Field(
        ge=0,
        description="Accumulated output tokens",
    )
    record_count: int = Field(
        ge=0,
        description="Number of cost records aggregated",
    )
    last_updated: AwareDatetime = Field(
        description="Timestamp of last increment",
    )


@runtime_checkable
class ProjectCostAggregateRepository(Protocol):
    """Repository for durable per-project cost aggregates.

    Implementations must provide atomic increment semantics so
    concurrent cost recordings do not lose updates.
    """

    async def get(
        self,
        project_id: NotBlankStr,
    ) -> ProjectCostAggregate | None:
        """Retrieve the aggregate for a project.

        Args:
            project_id: Project identifier.

        Returns:
            The aggregate, or ``None`` if no costs have been recorded.
        """
        ...

    async def increment(
        self,
        project_id: NotBlankStr,
        cost: float,
        input_tokens: int,
        output_tokens: int,
    ) -> ProjectCostAggregate:
        """Atomically increment the project's cost aggregate.

        Creates a new aggregate row on the first call for a project.
        Subsequent calls increment the existing totals.

        Args:
            project_id: Project identifier.
            cost: Cost delta to add.
            input_tokens: Input token delta to add.
            output_tokens: Output token delta to add.

        Returns:
            The updated aggregate after the increment.
        """
        ...
