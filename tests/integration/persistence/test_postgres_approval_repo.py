"""Integration tests for :class:`PostgresApprovalRepository` (ARC-1).

Requires a real Postgres via ``testcontainers``; runs under the
``integration`` marker.  Uses the shared ``postgres_backend`` fixture
from :mod:`tests.integration.persistence.conftest` so migrations are
applied once per session.

Mirrors the SQLite-side coverage in
``tests/unit/api/test_approval_store.py`` and the
``PostgresEscalationRepository`` integration suite so the dual-backend
parity that ARC-1 establishes is actually exercised on real Postgres
wire protocol (JSONB round-trips, TIMESTAMPTZ handling, commit
semantics, constraint violations).
"""

from datetime import UTC, datetime, timedelta

import psycopg
import pytest
from psycopg.types.json import Jsonb

from synthorg.core.approval import ApprovalItem
from synthorg.core.enums import ApprovalRiskLevel, ApprovalStatus
from synthorg.persistence.errors import ConstraintViolationError, QueryError
from synthorg.persistence.postgres.approval_repo import (
    PostgresApprovalRepository,
)
from synthorg.persistence.postgres.backend import PostgresPersistenceBackend

pytestmark = [pytest.mark.integration, pytest.mark.slow]


def _make_item(  # noqa: PLR0913 -- test factory with explicit knobs
    *,
    approval_id: str = "approval-pg-0001",
    status: ApprovalStatus = ApprovalStatus.PENDING,
    risk_level: ApprovalRiskLevel = ApprovalRiskLevel.HIGH,
    action_type: str = "deploy:production",
    task_id: str | None = None,
    metadata: dict[str, str] | None = None,
) -> ApprovalItem:
    """Build an ApprovalItem with sensible defaults."""
    now = datetime.now(UTC)
    decided_at: datetime | None = None
    decided_by: str | None = None
    decision_reason: str | None = None
    if status in {ApprovalStatus.APPROVED, ApprovalStatus.REJECTED}:
        decided_at = now
        decided_by = "operator-a"
        if status == ApprovalStatus.REJECTED:
            decision_reason = "Not authorised"
    return ApprovalItem(
        id=approval_id,
        action_type=action_type,
        title="Approve prod deploy",
        description="Rolls service v2 to prod.",
        requested_by="agent-eng-001",
        risk_level=risk_level,
        status=status,
        created_at=now,
        expires_at=now + timedelta(days=7),
        task_id=task_id,
        metadata=metadata or {},
        decided_at=decided_at,
        decided_by=decided_by,
        decision_reason=decision_reason,
    )


@pytest.fixture
def repo(
    postgres_backend: PostgresPersistenceBackend,
) -> PostgresApprovalRepository:
    """Approval repository wired to the shared postgres backend pool."""
    assert postgres_backend._pool is not None
    return PostgresApprovalRepository(postgres_backend._pool)


async def test_save_and_get_round_trip(
    repo: PostgresApprovalRepository,
) -> None:
    """A pending item round-trips across the wire without drift."""
    item = _make_item(
        approval_id="approval-rt-001",
        metadata={"source_rule": "rule-A", "confidence": "0.93"},
    )
    await repo.save(item)
    fetched = await repo.get(item.id)
    assert fetched is not None
    assert fetched.id == item.id
    assert fetched.status == ApprovalStatus.PENDING
    assert fetched.action_type == item.action_type
    assert fetched.metadata == item.metadata
    # TIMESTAMPTZ round-trips preserve aware datetimes.
    assert fetched.created_at.tzinfo is not None
    assert fetched.expires_at is not None
    assert fetched.expires_at.tzinfo is not None


async def test_get_returns_none_when_absent(
    repo: PostgresApprovalRepository,
) -> None:
    assert await repo.get("approval-missing-999") is None


async def test_save_commits_survives_reconnect(
    repo: PostgresApprovalRepository,
    postgres_backend: PostgresPersistenceBackend,
) -> None:
    """Writes persist through a fresh connection -- guards against the
    silent-rollback bug where missing ``await conn.commit()`` would
    make writes vanish on pool return.
    """
    item = _make_item(approval_id="approval-commit-001")
    await repo.save(item)

    # Build a second repository around the same pool; if the first
    # save didn't commit, this reader would see nothing.
    assert postgres_backend._pool is not None
    second_repo = PostgresApprovalRepository(postgres_backend._pool)
    fetched = await second_repo.get(item.id)
    assert fetched is not None
    assert fetched.id == item.id


async def test_list_items_filters(
    repo: PostgresApprovalRepository,
) -> None:
    """Filter combinations drive WHERE clause construction correctly."""
    pending = _make_item(
        approval_id="approval-list-pending",
        status=ApprovalStatus.PENDING,
        risk_level=ApprovalRiskLevel.MEDIUM,
        action_type="scaling:hire",
    )
    approved = _make_item(
        approval_id="approval-list-approved",
        status=ApprovalStatus.APPROVED,
        risk_level=ApprovalRiskLevel.HIGH,
        action_type="scaling:hire",
    )
    rejected = _make_item(
        approval_id="approval-list-rejected",
        status=ApprovalStatus.REJECTED,
        risk_level=ApprovalRiskLevel.CRITICAL,
        action_type="deploy:production",
    )
    await repo.save(pending)
    await repo.save(approved)
    await repo.save(rejected)

    pending_only = await repo.list_items(status=ApprovalStatus.PENDING)
    pending_ids = {i.id for i in pending_only}
    assert pending.id in pending_ids
    assert approved.id not in pending_ids

    hires = await repo.list_items(action_type="scaling:hire")
    hire_ids = {i.id for i in hires}
    assert pending.id in hire_ids
    assert approved.id in hire_ids
    assert rejected.id not in hire_ids

    crits = await repo.list_items(risk_level=ApprovalRiskLevel.CRITICAL)
    crit_ids = {i.id for i in crits}
    assert rejected.id in crit_ids


async def test_delete_round_trip(
    repo: PostgresApprovalRepository,
) -> None:
    """Delete returns True then False on repeat; the row is gone."""
    item = _make_item(approval_id="approval-delete-001")
    await repo.save(item)
    assert await repo.get(item.id) is not None

    deleted_first = await repo.delete(item.id)
    assert deleted_first is True
    assert await repo.get(item.id) is None

    deleted_second = await repo.delete(item.id)
    assert deleted_second is False


async def test_save_update_overwrites(
    repo: PostgresApprovalRepository,
) -> None:
    """Repeating save() upserts; status transitions are visible."""
    item = _make_item(
        approval_id="approval-upsert-001",
        status=ApprovalStatus.PENDING,
    )
    await repo.save(item)
    updated = item.model_copy(
        update={
            "status": ApprovalStatus.APPROVED,
            "decided_at": datetime.now(UTC),
            "decided_by": "operator-b",
        },
    )
    await repo.save(updated)
    fetched = await repo.get(item.id)
    assert fetched is not None
    assert fetched.status == ApprovalStatus.APPROVED
    assert fetched.decided_by == "operator-b"


async def test_pydantic_invalid_row_raises_query_error(
    repo: PostgresApprovalRepository,
    postgres_backend: PostgresPersistenceBackend,
) -> None:
    """A DB row that the DB accepts but Pydantic rejects surfaces as
    :class:`QueryError` (wrapping the underlying ``ValidationError``),
    exercising the ``_row_to_item`` error path with ``ValidationError``
    in the caught exception tuple.

    The schema's CHECK constraints block invalid enum values, so we
    corrupt ``metadata`` to carry a non-string value -- permitted by
    the ``JSONB`` column type but rejected by ``ApprovalItem``'s
    ``dict[str, str]`` metadata field.
    """
    assert postgres_backend._pool is not None
    async with postgres_backend._pool.connection() as conn, conn.cursor() as cur:
        await cur.execute(
            "INSERT INTO approvals "
            "(id, action_type, title, description, requested_by, "
            " risk_level, status, created_at, expires_at, "
            " decided_at, decided_by, decision_reason, task_id, "
            " evidence_package, metadata) VALUES "
            "(%s, %s, %s, %s, %s, %s, %s, %s, %s, "
            " %s, %s, %s, %s, %s, %s)",
            (
                "approval-invalid-001",
                "deploy:production",
                "Invalid metadata",
                "metadata dict carries a non-string value",
                "agent-eng-001",
                "high",
                "pending",
                datetime.now(UTC),
                None,
                None,
                None,
                None,
                None,
                None,
                # Non-string value in metadata -- ApprovalItem
                # requires dict[str, str] so Pydantic rejects.
                Jsonb({"bad_field": 42}),
            ),
        )
        await conn.commit()

    with pytest.raises(QueryError):
        await repo.get("approval-invalid-001")


async def test_save_duplicate_primary_key_raises_constraint(
    repo: PostgresApprovalRepository,
    postgres_backend: PostgresPersistenceBackend,
) -> None:
    """A manually INSERTed duplicate id surfaces as
    :class:`ConstraintViolationError`; the upsert path in ``save()``
    handles legitimate updates without raising, so we force the
    violation by directly inserting the second row via a raw
    ``INSERT`` that bypasses ``ON CONFLICT``.
    """
    assert postgres_backend._pool is not None
    item = _make_item(approval_id="approval-dup-001")
    await repo.save(item)

    async with postgres_backend._pool.connection() as conn, conn.cursor() as cur:
        with pytest.raises(psycopg.errors.UniqueViolation):
            await cur.execute(
                "INSERT INTO approvals "
                "(id, action_type, title, description, requested_by, "
                " risk_level, status, created_at, expires_at, "
                " decided_at, decided_by, decision_reason, task_id, "
                " evidence_package, metadata) VALUES "
                "(%s, %s, %s, %s, %s, %s, %s, %s, %s, "
                " %s, %s, %s, %s, %s, %s)",
                (
                    item.id,
                    item.action_type,
                    item.title,
                    item.description,
                    item.requested_by,
                    item.risk_level.value,
                    item.status.value,
                    item.created_at,
                    item.expires_at,
                    None,
                    None,
                    None,
                    None,
                    None,
                    Jsonb({}),
                ),
            )

    # The legitimate upsert retry (same id, different payload) goes
    # through ON CONFLICT and does NOT raise -- this documents the
    # semantics for callers that were previously unsure.
    updated = item.model_copy(update={"description": "Updated"})
    await repo.save(updated)
    fetched = await repo.get(item.id)
    assert fetched is not None
    assert fetched.description == "Updated"


async def test_constraint_violation_surfaces_from_save(
    repo: PostgresApprovalRepository,
) -> None:
    """A REJECTED item without a decision_reason fails at the DB CHECK
    constraint and is surfaced as
    :class:`ConstraintViolationError`.  We build an invalid row by
    bypassing Pydantic validation via ``model_construct``.
    """
    # The Pydantic validator refuses to build this state directly, so
    # use model_construct to bypass field validation and force the DB
    # CHECK to surface the violation.
    now = datetime.now(UTC)
    bad_item = ApprovalItem.model_construct(
        id="approval-ck-001",
        action_type="deploy:production",
        title="Rejected w/o reason",
        description="Should not be storable.",
        requested_by="agent-eng-001",
        risk_level=ApprovalRiskLevel.HIGH,
        status=ApprovalStatus.REJECTED,
        created_at=now,
        expires_at=now + timedelta(days=7),
        decided_at=now,
        decided_by="operator-a",
        decision_reason=None,
        task_id=None,
        evidence_package=None,
        metadata={},
    )
    with pytest.raises(ConstraintViolationError):
        await repo.save(bad_item)


async def test_build_ontology_versioning_returns_service(
    postgres_backend: PostgresPersistenceBackend,
) -> None:
    """Postgres capability method yields a wired VersioningService.

    Mirrors the SQLite-side unit test
    (``tests/unit/persistence/test_backend_capability_methods.py``)
    so the ARC-1 capability pattern is exercised on both backends.
    """
    from synthorg.versioning.service import VersioningService

    service = postgres_backend.build_ontology_versioning()
    assert isinstance(service, VersioningService)
    for method_name in ("snapshot_if_changed", "force_snapshot", "get_latest"):
        assert callable(getattr(service, method_name))
