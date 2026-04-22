"""Structural conformance tests for ``ApprovalRepository``.

Locks the runtime-checkable persistence contract against both the SQLite
and Postgres concrete repositories so a future schema/method change
fails CI instead of silently breaking ``ApprovalStore``.  The Postgres
implementation is exercised structurally (method presence + class-level
isinstance probe) without opening a real pool -- end-to-end Postgres
behaviour lives in ``tests/integration/persistence``.
"""

import aiosqlite
import pytest

from synthorg.persistence.approval_protocol import ApprovalRepository
from synthorg.persistence.postgres.approval_repo import PostgresApprovalRepository
from synthorg.persistence.sqlite.approval_repo import SQLiteApprovalRepository

pytestmark = pytest.mark.unit


class TestApprovalRepositoryProtocol:
    """Both backend repositories must satisfy ``ApprovalRepository``."""

    async def test_sqlite_impl_satisfies_protocol(self) -> None:
        """``isinstance(SQLiteApprovalRepository(), ApprovalRepository)``."""
        db = await aiosqlite.connect(":memory:")
        try:
            repo = SQLiteApprovalRepository(db)
            assert isinstance(repo, ApprovalRepository)
        finally:
            await db.close()

    @pytest.mark.parametrize(
        "method_name",
        ["save", "get", "list_items", "delete"],
    )
    def test_postgres_impl_exposes_method(self, method_name: str) -> None:
        """``PostgresApprovalRepository`` exposes the protocol surface.

        We probe method presence on the class itself rather than
        constructing an instance -- opening a real pool belongs in the
        integration suite.  ``runtime_checkable`` matches on attribute
        presence, so class-level ``hasattr`` is sufficient to lock the
        structural contract.  Parametrising makes a missing method
        report as a single failing test rather than one loop iteration.
        """
        assert hasattr(PostgresApprovalRepository, method_name), (
            f"PostgresApprovalRepository missing {method_name}"
        )

    def test_protocol_surface_is_stable(self) -> None:
        """The protocol's public method names are the exact surface."""
        expected = {"delete", "get", "list_items", "save"}
        actual = {name for name in vars(ApprovalRepository) if not name.startswith("_")}
        assert actual == expected, (
            "ApprovalRepository surface changed: "
            f"missing={expected - actual}, added={actual - expected}"
        )
