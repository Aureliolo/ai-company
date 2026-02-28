"""Task domain model and acceptance criteria."""

from typing import Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

from ai_company.core.artifact import ExpectedArtifact  # noqa: TC001
from ai_company.core.enums import Complexity, Priority, TaskStatus, TaskType


class AcceptanceCriterion(BaseModel):
    """A single acceptance criterion for a task.

    Attributes:
        description: The criterion text.
        met: Whether this criterion has been satisfied.
    """

    model_config = ConfigDict(frozen=True)

    description: str = Field(
        min_length=1,
        description="Criterion text",
    )
    met: bool = Field(
        default=False,
        description="Whether this criterion has been satisfied",
    )

    @model_validator(mode="after")
    def _validate_description_not_blank(self) -> Self:
        """Ensure description is not whitespace-only."""
        if not self.description.strip():
            msg = "description must not be whitespace-only"
            raise ValueError(msg)
        return self


class Task(BaseModel):
    """A unit of work within the company.

    Represents a task from creation through completion, with full
    lifecycle tracking, dependency modeling, and acceptance criteria.
    Field schema matches DESIGN_SPEC Section 6.2.

    Attributes:
        id: Unique task identifier (e.g. ``"task-123"``).
        title: Short task title.
        description: Detailed task description.
        type: Classification of the task's work type.
        priority: Task urgency and importance level.
        project: Project ID this task belongs to.
        created_by: Agent ID of the task creator.
        assigned_to: Agent ID of the assignee (``None`` if unassigned).
        reviewers: Agent IDs of designated reviewers.
        dependencies: IDs of tasks this task depends on.
        artifacts_expected: Artifacts expected to be produced.
        acceptance_criteria: Structured acceptance criteria.
        estimated_complexity: Task complexity estimate.
        budget_limit: Maximum USD spend for this task.
        deadline: Optional deadline (ISO 8601 string or ``None``).
        status: Current lifecycle status.
    """

    model_config = ConfigDict(frozen=True)

    id: str = Field(min_length=1, description="Unique task identifier")
    title: str = Field(min_length=1, description="Short task title")
    description: str = Field(
        min_length=1,
        description="Detailed task description",
    )
    type: TaskType = Field(description="Task work type")
    priority: Priority = Field(
        default=Priority.MEDIUM,
        description="Task priority",
    )
    project: str = Field(
        min_length=1,
        description="Project ID this task belongs to",
    )
    created_by: str = Field(
        min_length=1,
        description="Agent ID of the task creator",
    )
    assigned_to: str | None = Field(
        default=None,
        min_length=1,
        description="Agent ID of the assignee",
    )
    reviewers: tuple[str, ...] = Field(
        default=(),
        description="Agent IDs of designated reviewers",
    )
    dependencies: tuple[str, ...] = Field(
        default=(),
        description="IDs of tasks this task depends on",
    )
    artifacts_expected: tuple[ExpectedArtifact, ...] = Field(
        default=(),
        description="Artifacts expected to be produced",
    )
    acceptance_criteria: tuple[AcceptanceCriterion, ...] = Field(
        default=(),
        description="Structured acceptance criteria",
    )
    estimated_complexity: Complexity = Field(
        default=Complexity.MEDIUM,
        description="Task complexity estimate",
    )
    budget_limit: float = Field(
        default=0.0,
        ge=0.0,
        description="Maximum USD spend for this task",
    )
    deadline: str | None = Field(
        default=None,
        description="Optional deadline (ISO 8601 string)",
    )
    status: TaskStatus = Field(
        default=TaskStatus.CREATED,
        description="Current lifecycle status",
    )

    @model_validator(mode="after")
    def _validate_non_blank_strings(self) -> Self:
        """Ensure string identifier fields are not whitespace-only."""
        for field_name in ("id", "title", "description", "project", "created_by"):
            if not getattr(self, field_name).strip():
                msg = f"{field_name} must not be whitespace-only"
                raise ValueError(msg)
        if self.assigned_to is not None and not self.assigned_to.strip():
            msg = "assigned_to must not be whitespace-only"
            raise ValueError(msg)
        if self.deadline is not None and not self.deadline.strip():
            msg = "deadline must not be whitespace-only"
            raise ValueError(msg)
        return self

    @model_validator(mode="after")
    def _validate_no_empty_collection_entries(self) -> Self:
        """Ensure no empty or whitespace-only entries in string tuples."""
        for field_name in ("reviewers", "dependencies"):
            for value in getattr(self, field_name):
                if not value.strip():
                    msg = f"Empty or whitespace-only entry in {field_name}"
                    raise ValueError(msg)
        return self

    @model_validator(mode="after")
    def _validate_no_self_dependency(self) -> Self:
        """Ensure a task does not depend on itself."""
        if self.id in self.dependencies:
            msg = f"Task {self.id!r} cannot depend on itself"
            raise ValueError(msg)
        return self

    @model_validator(mode="after")
    def _validate_no_duplicate_dependencies(self) -> Self:
        """Ensure no duplicate task IDs in dependencies."""
        if len(self.dependencies) != len(set(self.dependencies)):
            msg = "Duplicate entries in dependencies"
            raise ValueError(msg)
        return self

    @model_validator(mode="after")
    def _validate_no_duplicate_reviewers(self) -> Self:
        """Ensure no duplicate agent IDs in reviewers."""
        if len(self.reviewers) != len(set(self.reviewers)):
            msg = "Duplicate entries in reviewers"
            raise ValueError(msg)
        return self

    @model_validator(mode="after")
    def _validate_assignment_consistency(self) -> Self:
        """Ensure assigned_to is consistent with status.

        ``CREATED`` status must have ``assigned_to=None``.  Statuses beyond
        ``CREATED`` (``ASSIGNED``, ``IN_PROGRESS``, ``IN_REVIEW``,
        ``COMPLETED``) require ``assigned_to`` to be set.  ``BLOCKED``
        and ``CANCELLED`` may or may not have an assignee.
        """
        requires_assignee = {
            TaskStatus.ASSIGNED,
            TaskStatus.IN_PROGRESS,
            TaskStatus.IN_REVIEW,
            TaskStatus.COMPLETED,
        }
        if self.status is TaskStatus.CREATED and self.assigned_to is not None:
            msg = "assigned_to must be None when status is 'created'"
            raise ValueError(msg)
        if self.status in requires_assignee and self.assigned_to is None:
            msg = f"assigned_to is required when status is {self.status.value!r}"
            raise ValueError(msg)
        return self
