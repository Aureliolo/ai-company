"""Architecture applier.

Applies approved architecture proposals by creating new roles,
departments, or modifying workflows in the appropriate registries.
``dry_run()`` validates each ``ArchitectureChange`` against a
read-only view of those registries, so operators can preview whether
``apply()`` would succeed without mutating state.
"""

from typing import Any, Final, Protocol, runtime_checkable

from synthorg.meta.appliers._validation import validate_payload_keys
from synthorg.meta.models import (
    ApplyResult,
    ArchitectureChange,
    ImprovementProposal,
    ProposalAltitude,
)
from synthorg.observability import get_logger
from synthorg.observability.events.meta import (
    META_APPLY_COMPLETED,
    META_APPLY_FAILED,
    META_DRY_RUN_COMPLETED,
    META_DRY_RUN_FAILED,
    META_DRY_RUN_STARTED,
)

logger = get_logger(__name__)


_OP_CREATE_ROLE: Final[str] = "create_role"
_OP_CREATE_DEPARTMENT: Final[str] = "create_department"
_OP_MODIFY_WORKFLOW: Final[str] = "modify_workflow"
_OP_REMOVE_ROLE: Final[str] = "remove_role"
_OP_REMOVE_DEPARTMENT: Final[str] = "remove_department"
_SUPPORTED_OPS: Final[frozenset[str]] = frozenset(
    {
        _OP_CREATE_ROLE,
        _OP_CREATE_DEPARTMENT,
        _OP_MODIFY_WORKFLOW,
        _OP_REMOVE_ROLE,
        _OP_REMOVE_DEPARTMENT,
    }
)

_CREATE_ROLE_REQUIRED: Final[frozenset[str]] = frozenset({"description"})
_CREATE_ROLE_ALLOWED: Final[frozenset[str]] = frozenset(
    {
        "description",
        "department",
        "required_skills",
        "authority_level",
        "tool_access",
    }
)
_CREATE_DEPT_REQUIRED: Final[frozenset[str]] = frozenset()
_CREATE_DEPT_ALLOWED: Final[frozenset[str]] = frozenset({"head", "policies"})

# Value-level length caps applied to free-text payload fields to bound
# memory usage and mitigate stored-XSS risk if a downstream UI renders
# these values.  The limits are deliberately generous -- they only catch
# obvious abuse, not legitimate edge cases.
_MAX_DESCRIPTION_CHARS: Final[int] = 2_000
_MAX_ROLE_NAME_CHARS: Final[int] = 80
_MAX_SKILL_NAME_CHARS: Final[int] = 80
_MAX_SKILLS_PER_ROLE: Final[int] = 100
_MAX_TOOL_NAME_CHARS: Final[int] = 80
_MAX_TOOLS_PER_ROLE: Final[int] = 100
_MAX_POLICIES_PER_DEPT: Final[int] = 100
_MAX_POLICY_CHARS: Final[int] = 500

# Authority levels are free text for now (operators pick their own
# taxonomy).  Cap length + require non-blank so the field at least
# rejects obvious junk.
_MAX_AUTHORITY_LEVEL_CHARS: Final[int] = 60


@runtime_checkable
class ArchitectureApplierContext(Protocol):
    """Read-only view of role/department/workflow registries."""

    def has_role(self, name: str) -> bool:
        """Return True when a role with ``name`` is registered."""
        ...

    def has_department(self, name: str) -> bool:
        """Return True when a department with ``name`` is registered."""
        ...

    def has_workflow(self, name: str) -> bool:
        """Return True when a workflow with ``name`` is registered."""
        ...

    def role_in_use(self, name: str) -> bool:
        """Return True when removing the role would dangle references."""
        ...

    def department_in_use(self, name: str) -> bool:
        """Return True when removing the department would dangle references."""
        ...


class _PendingChanges:
    """In-proposal mutable accumulator for scheduled creates / removes.

    Tracks in-flight references so the validator catches dangling-ref
    pairs *within* the same proposal: a ``remove_department`` that
    leaves behind a ``create_role`` pointing at it, or a
    ``remove_role`` that leaves behind a ``create_department`` with
    that role as its head.
    """

    __slots__ = (
        "new_departments",
        "new_roles",
        "pending_department_refs",
        "pending_role_refs",
        "removed_departments",
        "removed_roles",
    )

    def __init__(self) -> None:
        self.new_roles: set[str] = set()
        self.removed_roles: set[str] = set()
        self.new_departments: set[str] = set()
        self.removed_departments: set[str] = set()
        # Departments referenced by in-proposal create_role payloads.
        self.pending_department_refs: set[str] = set()
        # Roles referenced as a ``head`` by in-proposal
        # create_department payloads.
        self.pending_role_refs: set[str] = set()


class ArchitectureApplier:
    """Applies architecture proposals.

    Args:
        context: Read-only registry view.  Required for ``dry_run``;
            when absent dry_run rejects proposals with an explicit
            error rather than silently passing.
    """

    def __init__(
        self,
        *,
        context: ArchitectureApplierContext | None = None,
    ) -> None:
        """Store the registry context."""
        self._context = context

    @property
    def altitude(self) -> ProposalAltitude:
        """This applier handles architecture proposals."""
        return ProposalAltitude.ARCHITECTURE

    async def apply(
        self,
        proposal: ImprovementProposal,
    ) -> ApplyResult:
        """Apply architecture changes from the proposal.

        Args:
            proposal: The approved architecture proposal.

        Returns:
            Result indicating success or failure.
        """
        try:
            count = len(proposal.architecture_changes)
            logger.info(
                META_APPLY_COMPLETED,
                altitude="architecture",
                changes=count,
                proposal_id=str(proposal.id),
            )
            return ApplyResult(success=True, changes_applied=count)
        except MemoryError, RecursionError:
            raise
        except Exception:
            logger.exception(
                META_APPLY_FAILED,
                altitude="architecture",
                proposal_id=str(proposal.id),
            )
            return ApplyResult(
                success=False,
                error_message="Architecture apply failed. Check logs.",
                changes_applied=0,
            )

    async def dry_run(
        self,
        proposal: ImprovementProposal,
    ) -> ApplyResult:
        """Validate architecture changes without applying.

        Args:
            proposal: The proposal to validate.

        Returns:
            Result indicating whether apply would succeed.
        """
        logger.info(
            META_DRY_RUN_STARTED,
            altitude="architecture",
            proposal_id=str(proposal.id),
            changes=len(proposal.architecture_changes),
        )
        context = self._context
        if context is None:
            return self._fail(
                proposal,
                error_message=(
                    "ArchitectureApplier.dry_run requires an "
                    "ArchitectureApplierContext; none was injected"
                ),
            )
        if proposal.altitude != ProposalAltitude.ARCHITECTURE:
            return self._fail(
                proposal,
                error_message=(
                    f"Expected ARCHITECTURE altitude, got {proposal.altitude.value}"
                ),
            )
        if not proposal.architecture_changes:
            return self._fail(
                proposal,
                error_message="Proposal has no architecture changes",
            )

        pending = _PendingChanges()
        errors: list[str] = []
        for change in proposal.architecture_changes:
            try:
                errors.extend(
                    _validate_change(change, context=context, pending=pending)
                )
            except MemoryError, RecursionError:
                raise
            except Exception as exc:
                logger.warning(
                    META_DRY_RUN_FAILED,
                    altitude="architecture",
                    proposal_id=str(proposal.id),
                    change_operation=change.operation,
                    change_target=change.target_name,
                    reason=(f"context raised {type(exc).__name__}: {str(exc)[:200]}"),
                )
                errors.append(
                    f"{change.operation}({change.target_name!r}): "
                    f"context raised {type(exc).__name__}: {str(exc)[:200]}"
                )

        if errors:
            return self._fail(proposal, error_message="; ".join(errors))

        logger.info(
            META_DRY_RUN_COMPLETED,
            altitude="architecture",
            proposal_id=str(proposal.id),
            changes=len(proposal.architecture_changes),
        )
        return ApplyResult(
            success=True,
            changes_applied=len(proposal.architecture_changes),
        )

    def _fail(
        self,
        proposal: ImprovementProposal,
        *,
        error_message: str,
    ) -> ApplyResult:
        """Build a failure ``ApplyResult`` and log the dry_run failure."""
        logger.warning(
            META_DRY_RUN_FAILED,
            altitude="architecture",
            proposal_id=str(proposal.id),
            reason=error_message,
        )
        return ApplyResult(
            success=False,
            error_message=error_message,
            changes_applied=0,
        )


def _validate_change(
    change: ArchitectureChange,
    *,
    context: ArchitectureApplierContext,
    pending: _PendingChanges,
) -> list[str]:
    """Validate a single ``ArchitectureChange``."""
    if change.operation not in _SUPPORTED_OPS:
        return [
            f"Unknown operation {change.operation!r}; "
            f"supported: {sorted(_SUPPORTED_OPS)}"
        ]
    dispatch = {
        _OP_CREATE_ROLE: lambda: _validate_create_role(
            change, context=context, pending=pending
        ),
        _OP_CREATE_DEPARTMENT: lambda: _validate_create_department(
            change, context=context, pending=pending
        ),
        _OP_MODIFY_WORKFLOW: lambda: _validate_modify_workflow(change, context=context),
        _OP_REMOVE_ROLE: lambda: _validate_remove_role(
            change, context=context, pending=pending
        ),
        _OP_REMOVE_DEPARTMENT: lambda: _validate_remove_department(
            change, context=context, pending=pending
        ),
    }
    return dispatch[change.operation]()


def _validate_create_role(
    change: ArchitectureChange,
    *,
    context: ArchitectureApplierContext,
    pending: _PendingChanges,
) -> list[str]:
    errors: list[str] = []
    name = change.target_name
    if name in pending.new_roles:
        errors.append(f"create_role: duplicate target_name {name!r} in proposal")
    elif context.has_role(name):
        errors.append(f"create_role: role {name!r} already exists")
    errors.extend(
        validate_payload_keys(
            change.payload,
            required=_CREATE_ROLE_REQUIRED,
            allowed=_CREATE_ROLE_ALLOWED,
        )
    )
    errors.extend(_validate_role_description(change.payload.get("description")))
    errors.extend(
        _validate_role_department(
            change.payload.get("department"),
            context=context,
            pending=pending,
        )
    )
    skills = change.payload.get("required_skills")
    if skills is not None:
        if not isinstance(skills, list | tuple):
            errors.append("create_role: 'required_skills' must be a list or tuple")
        else:
            errors.extend(_validate_skill_list(skills))
    errors.extend(_validate_authority_level(change.payload.get("authority_level")))
    errors.extend(_validate_tool_access(change.payload.get("tool_access")))
    if not errors:
        pending.new_roles.add(name)
        dept = change.payload.get("department")
        if isinstance(dept, str) and dept:
            pending.pending_department_refs.add(dept)
    return errors


def _validate_role_description(description: Any) -> list[str]:
    """Validate the ``description`` field for a new role."""
    if description is None:
        return []
    if not isinstance(description, str):
        return ["create_role: 'description' must be a string"]
    if len(description) > _MAX_DESCRIPTION_CHARS:
        return [
            f"create_role: 'description' exceeds {_MAX_DESCRIPTION_CHARS} "
            f"chars (got {len(description)})"
        ]
    return []


def _validate_role_department(
    dept: Any,
    *,
    context: ArchitectureApplierContext,
    pending: _PendingChanges,
) -> list[str]:
    """Validate the ``department`` reference for a new role."""
    if dept is None:
        return []
    if not isinstance(dept, str):
        return ["create_role: 'department' must be a string"]
    if not dept.strip():
        return ["create_role: 'department' must be a non-blank string"]
    known_dept = context.has_department(dept) or dept in pending.new_departments
    removed = dept in pending.removed_departments
    if not known_dept or removed:
        return [f"create_role: department {dept!r} does not exist"]
    return []


def _validate_skill_list(skills: list[Any] | tuple[Any, ...]) -> list[str]:
    """Validate each entry in ``required_skills`` (type, length, count)."""
    errors: list[str] = []
    if len(skills) > _MAX_SKILLS_PER_ROLE:
        errors.append(
            f"create_role: 'required_skills' exceeds "
            f"{_MAX_SKILLS_PER_ROLE} entries (got {len(skills)})"
        )
    for index, skill in enumerate(skills):
        if not isinstance(skill, str):
            errors.append(f"create_role: 'required_skills[{index}]' must be a string")
        elif not skill.strip():
            errors.append(f"create_role: 'required_skills[{index}]' must not be blank")
        elif len(skill) > _MAX_SKILL_NAME_CHARS:
            errors.append(
                f"create_role: 'required_skills[{index}]' exceeds "
                f"{_MAX_SKILL_NAME_CHARS} chars"
            )
    return errors


def _validate_authority_level(value: Any) -> list[str]:
    """Validate the optional ``authority_level`` free-text field."""
    if value is None:
        return []
    if not isinstance(value, str):
        return ["create_role: 'authority_level' must be a string"]
    if not value.strip():
        return ["create_role: 'authority_level' must not be blank"]
    if len(value) > _MAX_AUTHORITY_LEVEL_CHARS:
        return [
            f"create_role: 'authority_level' exceeds "
            f"{_MAX_AUTHORITY_LEVEL_CHARS} chars (got {len(value)})"
        ]
    return []


def _validate_tool_access(value: Any) -> list[str]:
    """Validate the optional ``tool_access`` list of tool identifiers."""
    if value is None:
        return []
    if not isinstance(value, list | tuple):
        return ["create_role: 'tool_access' must be a list or tuple"]
    errors: list[str] = []
    if len(value) > _MAX_TOOLS_PER_ROLE:
        errors.append(
            f"create_role: 'tool_access' exceeds "
            f"{_MAX_TOOLS_PER_ROLE} entries (got {len(value)})"
        )
    for index, entry in enumerate(value):
        if not isinstance(entry, str):
            errors.append(f"create_role: 'tool_access[{index}]' must be a string")
        elif not entry.strip():
            errors.append(f"create_role: 'tool_access[{index}]' must not be blank")
        elif len(entry) > _MAX_TOOL_NAME_CHARS:
            errors.append(
                f"create_role: 'tool_access[{index}]' exceeds "
                f"{_MAX_TOOL_NAME_CHARS} chars"
            )
    return errors


def _validate_dept_policies(value: Any) -> list[str]:
    """Validate the optional ``policies`` list for a new department."""
    if value is None:
        return []
    if not isinstance(value, list | tuple):
        return ["create_department: 'policies' must be a list or tuple"]
    errors: list[str] = []
    if len(value) > _MAX_POLICIES_PER_DEPT:
        errors.append(
            f"create_department: 'policies' exceeds "
            f"{_MAX_POLICIES_PER_DEPT} entries (got {len(value)})"
        )
    for index, entry in enumerate(value):
        if not isinstance(entry, str):
            errors.append(f"create_department: 'policies[{index}]' must be a string")
        elif not entry.strip():
            errors.append(f"create_department: 'policies[{index}]' must not be blank")
        elif len(entry) > _MAX_POLICY_CHARS:
            errors.append(
                f"create_department: 'policies[{index}]' exceeds "
                f"{_MAX_POLICY_CHARS} chars"
            )
    return errors


def _validate_dept_head(value: Any) -> list[str]:
    """Validate the optional ``head`` reference on a new department."""
    if value is None:
        return []
    if not isinstance(value, str):
        return ["create_department: 'head' must be a string"]
    if not value.strip():
        return ["create_department: 'head' must not be blank"]
    if len(value) > _MAX_ROLE_NAME_CHARS:
        return [f"create_department: 'head' exceeds {_MAX_ROLE_NAME_CHARS} chars"]
    return []


def _validate_create_department(
    change: ArchitectureChange,
    *,
    context: ArchitectureApplierContext,
    pending: _PendingChanges,
) -> list[str]:
    errors: list[str] = []
    name = change.target_name
    if name in pending.new_departments:
        errors.append(f"create_department: duplicate target_name {name!r} in proposal")
    elif context.has_department(name):
        errors.append(f"create_department: department {name!r} already exists")
    errors.extend(
        validate_payload_keys(
            change.payload,
            required=_CREATE_DEPT_REQUIRED,
            allowed=_CREATE_DEPT_ALLOWED,
        )
    )
    head = change.payload.get("head")
    head_errors = _validate_dept_head(head)
    errors.extend(head_errors)
    # Only run existence / pending / context checks when basic
    # validation accepted the head.  Skipping prevents misleading
    # "does not exist" errors on malformed input and keeps context
    # calls out of the ``head=None`` / blank path.
    head_name: str | None = None
    if not head_errors and isinstance(head, str) and head:
        head_name = head
        if head_name in pending.removed_roles:
            errors.append(
                f"create_department: head role {head_name!r} is scheduled for "
                "removal earlier in this proposal"
            )
        elif head_name not in pending.new_roles and not context.has_role(head_name):
            errors.append(f"create_department: head role {head_name!r} does not exist")
    errors.extend(_validate_dept_policies(change.payload.get("policies")))
    if not errors:
        pending.new_departments.add(name)
        if head_name is not None:
            pending.pending_role_refs.add(head_name)
    return errors


def _validate_modify_workflow(
    change: ArchitectureChange,
    *,
    context: ArchitectureApplierContext,
) -> list[str]:
    errors: list[str] = []
    if not context.has_workflow(change.target_name):
        errors.append(
            f"modify_workflow: workflow {change.target_name!r} does not exist"
        )
    if not change.payload:
        errors.append(
            "modify_workflow: payload must not be empty (no-op modify is rejected)"
        )
    return errors


def _validate_remove_role(
    change: ArchitectureChange,
    *,
    context: ArchitectureApplierContext,
    pending: _PendingChanges,
) -> list[str]:
    errors: list[str] = []
    name = change.target_name
    if change.payload:
        errors.append(
            f"remove_role: payload must be empty; got keys {sorted(change.payload)!r}"
        )
    if name in pending.removed_roles:
        errors.append(f"remove_role: duplicate target_name {name!r} in proposal")
    elif not (context.has_role(name) or name in pending.new_roles):
        errors.append(f"remove_role: role {name!r} does not exist")
    elif context.role_in_use(name) or name in pending.pending_role_refs:
        errors.append(
            f"remove_role: role {name!r} still referenced by agents or departments"
        )
    if not errors:
        pending.removed_roles.add(name)
    return errors


def _validate_remove_department(
    change: ArchitectureChange,
    *,
    context: ArchitectureApplierContext,
    pending: _PendingChanges,
) -> list[str]:
    errors: list[str] = []
    name = change.target_name
    if change.payload:
        errors.append(
            "remove_department: payload must be empty; "
            f"got keys {sorted(change.payload)!r}"
        )
    if name in pending.removed_departments:
        errors.append(f"remove_department: duplicate target_name {name!r} in proposal")
    elif not (context.has_department(name) or name in pending.new_departments):
        errors.append(f"remove_department: department {name!r} does not exist")
    elif context.department_in_use(name) or name in pending.pending_department_refs:
        errors.append(f"remove_department: department {name!r} still referenced")
    if not errors:
        pending.removed_departments.add(name)
    return errors
