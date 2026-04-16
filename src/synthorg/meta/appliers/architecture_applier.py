"""Architecture applier.

Applies approved architecture proposals by creating new roles,
departments, or modifying workflows in the appropriate registries.
``dry_run()`` validates each ``ArchitectureChange`` against a
read-only view of those registries, so operators can preview whether
``apply()`` would succeed without mutating state.
"""

from typing import Final, Protocol, runtime_checkable

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
    """In-proposal mutable accumulator for scheduled creates / removes."""

    __slots__ = (
        "new_departments",
        "new_roles",
        "removed_departments",
        "removed_roles",
    )

    def __init__(self) -> None:
        self.new_roles: set[str] = set()
        self.removed_roles: set[str] = set()
        self.new_departments: set[str] = set()
        self.removed_departments: set[str] = set()


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
            errors.extend(_validate_change(change, context=context, pending=pending))

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
    dept = change.payload.get("department")
    if isinstance(dept, str) and dept:
        known_dept = context.has_department(dept) or dept in pending.new_departments
        removed = dept in pending.removed_departments
        if not known_dept or removed:
            errors.append(f"create_role: department {dept!r} does not exist")
    elif dept is not None and not isinstance(dept, str):
        errors.append("create_role: 'department' must be a string")
    skills = change.payload.get("required_skills")
    if skills is not None and not isinstance(skills, list | tuple):
        errors.append("create_role: 'required_skills' must be a list or tuple")
    if not errors:
        pending.new_roles.add(name)
    return errors


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
    if isinstance(head, str) and head:
        if not (context.has_role(head) or head in pending.new_roles):
            errors.append(f"create_department: head role {head!r} does not exist")
    elif head is not None and not isinstance(head, str):
        errors.append("create_department: 'head' must be a string")
    if not errors:
        pending.new_departments.add(name)
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
    if name in pending.removed_roles:
        errors.append(f"remove_role: duplicate target_name {name!r} in proposal")
    elif not context.has_role(name):
        errors.append(f"remove_role: role {name!r} does not exist")
    elif context.role_in_use(name):
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
    if name in pending.removed_departments:
        errors.append(f"remove_department: duplicate target_name {name!r} in proposal")
    elif not context.has_department(name):
        errors.append(f"remove_department: department {name!r} does not exist")
    elif context.department_in_use(name):
        errors.append(f"remove_department: department {name!r} still referenced")
    if not errors:
        pending.removed_departments.add(name)
    return errors
