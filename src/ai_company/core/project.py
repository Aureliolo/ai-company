"""Project domain model for task collection management."""

from typing import Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

from ai_company.core.enums import ProjectStatus


class Project(BaseModel):
    """A collection of related tasks with a shared goal, team, and deadline.

    Projects organize tasks into a coherent unit of work with budget
    tracking and team assignment.  Per DESIGN_SPEC Section 2.1 glossary
    and Section 2.2 entity relationship tree.

    Attributes:
        id: Unique project identifier (e.g. ``"proj-456"``).
        name: Project display name.
        description: Detailed project description.
        team: Agent IDs assigned to this project.
        lead: Agent ID of the project lead.
        task_ids: IDs of tasks belonging to this project.
        deadline: Optional deadline (ISO 8601 string or ``None``).
        budget: Total budget for the project in USD.
        status: Current project status.
    """

    model_config = ConfigDict(frozen=True)

    id: str = Field(min_length=1, description="Unique project identifier")
    name: str = Field(min_length=1, description="Project display name")
    description: str = Field(
        default="",
        description="Detailed project description",
    )
    team: tuple[str, ...] = Field(
        default=(),
        description="Agent IDs assigned to this project",
    )
    lead: str | None = Field(
        default=None,
        min_length=1,
        description="Agent ID of the project lead",
    )
    task_ids: tuple[str, ...] = Field(
        default=(),
        description="IDs of tasks belonging to this project",
    )
    deadline: str | None = Field(
        default=None,
        description="Optional deadline (ISO 8601 string)",
    )
    budget: float = Field(
        default=0.0,
        ge=0.0,
        description="Total budget for the project in USD",
    )
    status: ProjectStatus = Field(
        default=ProjectStatus.PLANNING,
        description="Current project status",
    )

    @model_validator(mode="after")
    def _validate_non_blank_strings(self) -> Self:
        """Ensure string identifier fields are not whitespace-only."""
        for field_name in ("id", "name"):
            if not getattr(self, field_name).strip():
                msg = f"{field_name} must not be whitespace-only"
                raise ValueError(msg)
        if self.lead is not None and not self.lead.strip():
            msg = "lead must not be whitespace-only"
            raise ValueError(msg)
        if self.deadline is not None and not self.deadline.strip():
            msg = "deadline must not be whitespace-only"
            raise ValueError(msg)
        return self

    @model_validator(mode="after")
    def _validate_no_empty_collection_entries(self) -> Self:
        """Ensure no empty or whitespace-only entries in string tuples."""
        for field_name in ("team", "task_ids"):
            for value in getattr(self, field_name):
                if not value.strip():
                    msg = f"Empty or whitespace-only entry in {field_name}"
                    raise ValueError(msg)
        return self

    @model_validator(mode="after")
    def _validate_no_duplicate_team_members(self) -> Self:
        """Ensure no duplicate agent IDs in team."""
        if len(self.team) != len(set(self.team)):
            msg = "Duplicate entries in team"
            raise ValueError(msg)
        return self

    @model_validator(mode="after")
    def _validate_no_duplicate_task_ids(self) -> Self:
        """Ensure no duplicate task IDs."""
        if len(self.task_ids) != len(set(self.task_ids)):
            msg = "Duplicate entries in task_ids"
            raise ValueError(msg)
        return self
