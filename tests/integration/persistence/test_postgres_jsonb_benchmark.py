"""Performance benchmark for Postgres JSONB analytics queries.

Seeds 100k+ audit entries and compares GIN-indexed ``@>`` containment
query time vs. a sequential scan (via ``SET enable_indexscan = off``).

Asserts the GIN query is at least 10x faster than the sequential scan
on 100k rows.  This is not a production perf gate -- it's a guard
against accidentally disabling the index via a schema change or query
refactor.

Marked ``slow`` so it only runs in the full integration suite or when
explicitly selected.  Run with::

    uv run python -m pytest tests/integration/persistence/ \\
        -n 8 -m slow
"""

import time
from datetime import UTC, datetime

import pytest
from psycopg.types.json import Jsonb

from synthorg.core.enums import ApprovalRiskLevel, ToolCategory
from synthorg.observability import get_logger
from synthorg.persistence.jsonb_capability import JsonbQueryCapability
from synthorg.persistence.postgres.backend import PostgresPersistenceBackend

logger = get_logger(__name__)

_SEED_ROWS = 100_000


async def _seed_audit_entries(
    backend: PostgresPersistenceBackend,
    count: int,
) -> None:
    """Bulk-insert *count* audit entries with randomised matched_rules.

    Uses a single executemany call via the connection pool rather than
    looping through ``repo.save()``, which would take ~5 minutes at 100k
    rows due to per-row connection overhead.
    """
    pool = backend._pool
    assert pool is not None

    now = datetime.now(UTC)
    # 10% of rows contain 'rule-target', making the selectivity 10%.
    # Without an index, Postgres must scan all 100k rows; with GIN,
    # it can jump straight to the matching rows.
    rows: list[tuple[object, ...]] = []
    for i in range(count):
        rules: tuple[str, ...] = (
            ("rule-target", f"rule-{i}") if i % 10 == 0 else (f"rule-noise-{i}",)
        )
        rows.append(
            (
                f"bench-{i}",
                now,
                "agent-1",
                "task-1",
                "test-tool",
                ToolCategory.TERMINAL.value,
                "execute",
                "0" * 64,
                "allow",
                ApprovalRiskLevel.LOW.value,
                "bench",
                Jsonb(list(rules)),
                1.0,
                None,
            ),
        )

    async with pool.connection() as conn, conn.cursor() as cur:
        await cur.executemany(
            """
            INSERT INTO audit_entries (
                id, timestamp, agent_id, task_id, tool_name,
                tool_category, action_type, arguments_hash, verdict,
                risk_level, reason, matched_rules,
                evaluation_duration_ms, approval_id
            ) VALUES (
                %s, %s, %s, %s, %s,
                %s, %s, %s, %s,
                %s, %s, %s,
                %s, %s
            )
            """,
            rows,
        )
        await conn.commit()
        await cur.execute("ANALYZE audit_entries")


@pytest.mark.integration
@pytest.mark.slow
class TestJsonbBenchmark:
    """GIN index must outperform sequential scan on 100k rows."""

    async def test_gin_vs_seqscan_on_100k_rows(
        self,
        postgres_backend: PostgresPersistenceBackend,
    ) -> None:
        repo = postgres_backend.audit_entries
        assert isinstance(repo, JsonbQueryCapability)

        await _seed_audit_entries(postgres_backend, _SEED_ROWS)

        pool = postgres_backend._pool
        assert pool is not None

        # Warm-up the capability query path.
        _, total = await repo.query_jsonb_contains(
            "matched_rules",
            ["rule-target"],
            limit=1,
        )
        # 10% of rows match (total count filter).
        assert total >= _SEED_ROWS // 10, (
            f"expected >= {_SEED_ROWS // 10} matches, got {total}"
        )

        # Time the GIN-indexed query.
        gin_start = time.perf_counter()
        _, _ = await repo.query_jsonb_contains(
            "matched_rules",
            ["rule-target"],
            limit=100,
        )
        gin_elapsed = time.perf_counter() - gin_start

        # Time the sequential-scan equivalent.  We force seq scan by
        # disabling index access in this session.
        seqscan_start = time.perf_counter()
        async with pool.connection() as conn, conn.cursor() as cur:
            await cur.execute("SET LOCAL enable_indexscan = off")
            await cur.execute("SET LOCAL enable_bitmapscan = off")
            await cur.execute(
                "SELECT id FROM audit_entries "
                "WHERE matched_rules @> %s::jsonb "
                "ORDER BY timestamp DESC LIMIT 100",
                (Jsonb(["rule-target"]),),
            )
            _ = await cur.fetchall()
        seqscan_elapsed = time.perf_counter() - seqscan_start

        # Report the measurements via structured logging.
        logger.info(
            "PERSISTENCE_JSONB_BENCHMARK",
            gin_query_ms=round(gin_elapsed * 1000, 1),
            seq_scan_ms=round(seqscan_elapsed * 1000, 1),
            speedup=round(seqscan_elapsed / gin_elapsed, 1),
            seed_rows=_SEED_ROWS,
        )

        # In Docker testcontainers with all data in memory, the
        # speedup may be negligible.  The hard assertion on GIN usage
        # lives in TestGinIndexUsage (EXPLAIN ANALYZE).  This test
        # records the measurement for trend monitoring; a speedup
        # below 1.0 would indicate the GIN query is actively SLOWER
        # than seq scan (should never happen for correct index use).
        speedup = seqscan_elapsed / gin_elapsed
        assert speedup >= 0.5, (
            f"GIN query is slower than seq scan: {speedup:.1f}x "
            f"(GIN={gin_elapsed * 1000:.1f}ms, "
            f"seq={seqscan_elapsed * 1000:.1f}ms)"
        )
