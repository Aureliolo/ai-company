"""``ApprovalStoreProtocol`` -- the approval-store contract shared across layers.

``engine`` (agent execution), ``security`` (interceptors), ``hr``
(hiring/promotion/pruning/training/scaling guards), and ``api`` all
type their dependency on the approval store against this protocol so
no caller needs to know the concrete ``ApprovalStore`` lives in
``synthorg.api.approval_store``.
"""

from typing import Protocol, runtime_checkable

from synthorg.core.approval import ApprovalItem  # noqa: TC001
from synthorg.core.enums import (
    ApprovalRiskLevel,  # noqa: TC001
    ApprovalStatus,  # noqa: TC001
)
from synthorg.core.types import NotBlankStr  # noqa: TC001


@runtime_checkable
class ApprovalStoreProtocol(Protocol):
    """CRUD + lifecycle contract for an approval-item store.

    Concrete implementations (currently ``synthorg.api.approval_store.ApprovalStore``)
    provide an in-memory cache with optional persistence-backed writes.
    Consumers depend on this protocol so the storage implementation can
    evolve without touching the engine, security, or hr layers.

    Methods mirror the public surface of ``ApprovalStore``; private
    helpers (cache invalidation, expiration checks) are not part of
    the contract.
    """

    def clear(self) -> None:
        """Reset all approval items for test isolation.

        Test-only.  Production code uses the async CRUD methods.
        """
        ...

    async def add(self, item: ApprovalItem) -> None:
        """Add a new approval item.

        Raises:
            ConflictError: If an item with the same ID already exists.
        """
        ...

    async def get(self, approval_id: NotBlankStr) -> ApprovalItem | None:
        """Get an approval item by ID, applying lazy expiration."""
        ...

    async def list_items(
        self,
        *,
        status: ApprovalStatus | None = None,
        risk_level: ApprovalRiskLevel | None = None,
        action_type: NotBlankStr | None = None,
    ) -> tuple[ApprovalItem, ...]:
        """List approval items with optional filters."""
        ...

    async def save(self, item: ApprovalItem) -> ApprovalItem | None:
        """Update an existing approval item (first-writer-wins)."""
        ...

    async def save_if_pending(
        self,
        item: ApprovalItem,
    ) -> ApprovalItem | None:
        """Conditionally update an approval item if it is still pending."""
        ...
