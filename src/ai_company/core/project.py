"""Project domain model for task collection management."""

from collections import Counter
from datetime import datetime
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
    def _validate_fields(self) -> Self:
        """Validate string fields and deadline format."""
        for field_name in ("id", "name"):
            if not getattr(self, field_name).strip():
                msg = f"{field_name} must not be whitespace-only"
                raise ValueError(msg)
        if self.lead is not None and not self.lead.strip():
            msg = "lead must not be whitespace-only"
            raise ValueError(msg)
        if self.deadline is not None:
            if not self.deadline.strip():
                msg = "deadline must not be whitespace-only"
                raise ValueError(msg)
            try:
                datetime.fromisoformat(self.deadline)
            except ValueError:
                msg = f"deadline must be a valid ISO 8601 string, got {self.deadline!r}"
                raise ValueError(msg) from None
        return self

    @model_validator(mode="after")
    def _validate_collections(self) -> Self:
        """Validate collection entries and uniqueness."""
        for field_name in ("team", "task_ids"):
            for value in getattr(self, field_name):
                if not value.strip():
                    msg = f"Empty or whitespace-only entry in {field_name}"
                    raise ValueError(msg)
        if len(self.team) != len(set(self.team)):
            dupes = sorted(m for m, c in Counter(self.team).items() if c > 1)
            msg = f"Duplicate entries in team: {dupes}"
            raise ValueError(msg)
        if len(self.task_ids) != len(set(self.task_ids)):
            dupes = sorted(t for t, c in Counter(self.task_ids).items() if c > 1)
            msg = f"Duplicate entries in task_ids: {dupes}"
            raise ValueError(msg)
        return self
