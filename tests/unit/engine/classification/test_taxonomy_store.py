"""Tests for the in-memory error taxonomy store."""

from datetime import UTC, datetime, timedelta

import pytest

from synthorg.budget.coordination_config import ErrorCategory
from synthorg.engine.classification.models import (
    ClassificationResult,
    ErrorFinding,
    ErrorSeverity,
)
from synthorg.engine.classification.taxonomy_store import (
    InMemoryErrorTaxonomyStore,
)
from synthorg.engine.classification.taxonomy_store_protocol import (
    ErrorTaxonomyStore,
)
from synthorg.meta.signal_models import OrgErrorSummary, TrendDirection


def _finding(
    *,
    category: ErrorCategory = ErrorCategory.LOGICAL_CONTRADICTION,
    severity: ErrorSeverity = ErrorSeverity.HIGH,
    description: str = "finding",
) -> ErrorFinding:
    return ErrorFinding(
        category=category,
        severity=severity,
        description=description,
    )


def _result(
    *findings: ErrorFinding,
    classified_at: datetime,
    agent_id: str = "agent-1",
    task_id: str = "task-1",
    execution_id: str = "exec-1",
) -> ClassificationResult:
    cats = tuple({f.category for f in findings}) or (
        ErrorCategory.LOGICAL_CONTRADICTION,
    )
    return ClassificationResult(
        execution_id=execution_id,
        agent_id=agent_id,
        task_id=task_id,
        categories_checked=cats,
        findings=findings,
        classified_at=classified_at,
    )


@pytest.mark.unit
class TestInMemoryErrorTaxonomyStoreProtocol:
    """The in-memory impl satisfies the ErrorTaxonomyStore protocol."""

    def test_satisfies_protocol(self) -> None:
        store = InMemoryErrorTaxonomyStore()
        assert isinstance(store, ErrorTaxonomyStore)


@pytest.mark.unit
class TestInMemoryErrorTaxonomyStoreCapacity:
    """Ring-buffer size bounds and eviction."""

    def test_rejects_non_positive_capacity(self) -> None:
        with pytest.raises(ValueError, match="max_results must be >= 1"):
            InMemoryErrorTaxonomyStore(max_results=0)

    async def test_evicts_oldest_when_full(self) -> None:
        store = InMemoryErrorTaxonomyStore(max_results=3)
        base = datetime.now(UTC)
        for i in range(5):
            await store.on_classification(
                _result(
                    _finding(description=f"f{i}"),
                    classified_at=base + timedelta(seconds=i),
                    execution_id=f"exec-{i}",
                ),
            )
        assert await store.count() == 3

    async def test_respects_default_capacity(self) -> None:
        store = InMemoryErrorTaxonomyStore()
        assert await store.count() == 0

    async def test_clear_resets_buffer(self) -> None:
        store = InMemoryErrorTaxonomyStore()
        base = datetime.now(UTC)
        await store.on_classification(
            _result(_finding(), classified_at=base),
        )
        assert await store.count() == 1
        await store.clear()
        assert await store.count() == 0


@pytest.mark.unit
class TestInMemoryErrorTaxonomyStoreWindowing:
    """query_findings / summarize filter by the [since, until) window."""

    async def test_query_excludes_out_of_window(self) -> None:
        store = InMemoryErrorTaxonomyStore()
        now = datetime.now(UTC)
        before = now - timedelta(hours=2)
        inside = now - timedelta(minutes=30)
        await store.on_classification(_result(_finding(), classified_at=before))
        await store.on_classification(_result(_finding(), classified_at=inside))
        findings = await store.query_findings(
            since=now - timedelta(hours=1),
            until=now,
        )
        assert len(findings) == 1

    async def test_query_window_is_upper_bound_exclusive(self) -> None:
        """``until`` is exclusive -- findings recorded at exactly ``until`` excluded."""
        store = InMemoryErrorTaxonomyStore()
        now = datetime.now(UTC)
        at_until = now
        at_since = now - timedelta(hours=1)
        just_after_since = now - timedelta(minutes=59)
        await store.on_classification(_result(_finding(), classified_at=at_since))
        await store.on_classification(
            _result(_finding(), classified_at=just_after_since),
        )
        await store.on_classification(_result(_finding(), classified_at=at_until))
        findings = await store.query_findings(
            since=at_since,
            until=at_until,
        )
        # since is inclusive, until is exclusive -> two matches, not three
        assert len(findings) == 2

    async def test_query_rejects_naive_datetimes(self) -> None:
        store = InMemoryErrorTaxonomyStore()
        with pytest.raises(ValueError, match="timezone-aware"):
            await store.query_findings(
                since=datetime(2026, 4, 1),  # noqa: DTZ001 - intentionally naive
                until=datetime.now(UTC),
            )

    async def test_query_rejects_inverted_window(self) -> None:
        store = InMemoryErrorTaxonomyStore()
        now = datetime.now(UTC)
        with pytest.raises(ValueError, match="earlier"):
            await store.query_findings(
                since=now,
                until=now - timedelta(hours=1),
            )

    async def test_query_newest_first(self) -> None:
        store = InMemoryErrorTaxonomyStore()
        now = datetime.now(UTC)
        older = now - timedelta(minutes=30)
        newer = now - timedelta(minutes=5)
        await store.on_classification(
            _result(
                _finding(description="older"),
                classified_at=older,
            ),
        )
        await store.on_classification(
            _result(
                _finding(description="newer"),
                classified_at=newer,
            ),
        )
        findings = await store.query_findings(
            since=now - timedelta(hours=1),
            until=now,
        )
        assert findings[0].description == "newer"
        assert findings[1].description == "older"


@pytest.mark.unit
class TestInMemoryErrorTaxonomyStoreSummarize:
    """summarize produces an OrgErrorSummary."""

    async def test_empty_summary_when_no_findings(self) -> None:
        store = InMemoryErrorTaxonomyStore()
        now = datetime.now(UTC)
        summary = await store.summarize(
            since=now - timedelta(hours=1),
            until=now,
        )
        assert summary == OrgErrorSummary()
        assert summary.total_findings == 0
        assert summary.categories == ()

    async def test_summary_counts_by_category(self) -> None:
        store = InMemoryErrorTaxonomyStore()
        now = datetime.now(UTC)
        ts = now - timedelta(minutes=10)
        await store.on_classification(
            _result(
                _finding(category=ErrorCategory.LOGICAL_CONTRADICTION),
                _finding(category=ErrorCategory.NUMERICAL_DRIFT),
                _finding(category=ErrorCategory.NUMERICAL_DRIFT),
                classified_at=ts,
            ),
        )
        summary = await store.summarize(
            since=now - timedelta(hours=1),
            until=now,
        )
        assert summary.total_findings == 3
        cat_counts = {c.category: c.count for c in summary.categories}
        assert cat_counts[ErrorCategory.NUMERICAL_DRIFT.value] == 2
        assert cat_counts[ErrorCategory.LOGICAL_CONTRADICTION.value] == 1

    async def test_summary_averages_severity_per_category(self) -> None:
        store = InMemoryErrorTaxonomyStore()
        now = datetime.now(UTC)
        ts = now - timedelta(minutes=10)
        # LOW=1, MEDIUM=2, HIGH=3; avg of HIGH+LOW = 2.0.
        await store.on_classification(
            _result(
                _finding(severity=ErrorSeverity.HIGH),
                _finding(severity=ErrorSeverity.LOW),
                classified_at=ts,
            ),
        )
        summary = await store.summarize(
            since=now - timedelta(hours=1),
            until=now,
        )
        assert summary.categories[0].avg_severity == pytest.approx(2.0)

    async def test_most_severe_category_picked_by_highest_avg(self) -> None:
        store = InMemoryErrorTaxonomyStore()
        now = datetime.now(UTC)
        ts = now - timedelta(minutes=10)
        await store.on_classification(
            _result(
                _finding(
                    category=ErrorCategory.LOGICAL_CONTRADICTION,
                    severity=ErrorSeverity.LOW,
                ),
                _finding(
                    category=ErrorCategory.AUTHORITY_BREACH_ATTEMPT,
                    severity=ErrorSeverity.HIGH,
                ),
                classified_at=ts,
            ),
        )
        summary = await store.summarize(
            since=now - timedelta(hours=1),
            until=now,
        )
        expected = ErrorCategory.AUTHORITY_BREACH_ATTEMPT.value
        assert summary.most_severe_category == expected

    async def test_trend_direction_declining_when_errors_rise(self) -> None:
        """Newer half has more of category X -> DECLINING trend."""
        store = InMemoryErrorTaxonomyStore()
        now = datetime.now(UTC)
        older = now - timedelta(minutes=30)
        newer = now - timedelta(minutes=5)
        # Older: 1 finding in category A. Newer: 3 findings in category A.
        await store.on_classification(
            _result(
                _finding(category=ErrorCategory.LOGICAL_CONTRADICTION),
                classified_at=older,
            ),
        )
        await store.on_classification(
            _result(
                _finding(category=ErrorCategory.LOGICAL_CONTRADICTION),
                _finding(category=ErrorCategory.LOGICAL_CONTRADICTION),
                _finding(category=ErrorCategory.LOGICAL_CONTRADICTION),
                classified_at=newer,
            ),
        )
        summary = await store.summarize(
            since=now - timedelta(hours=1),
            until=now,
        )
        assert summary.categories[0].trend == TrendDirection.DECLINING


@pytest.mark.unit
class TestInMemoryErrorTaxonomyStoreSinkContract:
    """on_classification is best-effort and never raises."""

    async def test_swallows_unexpected_errors(self) -> None:
        store = InMemoryErrorTaxonomyStore()
        # Valid result; should not raise.
        await store.on_classification(
            _result(_finding(), classified_at=datetime.now(UTC)),
        )
        assert await store.count() == 1
