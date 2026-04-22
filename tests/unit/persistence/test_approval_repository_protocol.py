"""Structural conformance tests for ``ApprovalRepository``.

Locks the runtime-checkable persistence contract against the SQLite
concrete so a future schema/method change fails CI instead of silently
breaking ``ApprovalStore``.
"""

import aiosqlite
import pytest

from synthorg.persistence.approval_protocol import ApprovalRepository
from synthorg.persistence.sqlite.approval_repo import SQLiteApprovalRepository

pytestmark = pytest.mark.unit


class TestApprovalRepositoryProtocol:
    """``SQLiteApprovalRepository`` must satisfy ``ApprovalRepository``."""

    async def test_sqlite_impl_satisfies_protocol(self) -> None:
        """``isinstance(repo, ApprovalRepository)`` is True."""
        db = await aiosqlite.connect(":memory:")
        try:
            repo = SQLiteApprovalRepository(db)
            assert isinstance(repo, ApprovalRepository)
        finally:
            await db.close()

    def test_protocol_surface_is_stable(self) -> None:
        """The protocol's public method names are the agreed surface."""
        expected = {"delete", "get", "list_items", "save"}
        actual = {name for name in vars(ApprovalRepository) if not name.startswith("_")}
        assert expected.issubset(actual), (
            f"ApprovalRepository missing methods: {expected - actual}"
        )
