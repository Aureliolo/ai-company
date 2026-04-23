"""Protocol for the error taxonomy store.

The store records classification findings produced by the detector
pipeline and exposes a time-windowed query surface for the signals
aggregator layer.

Design:
- The store is a :class:`~synthorg.engine.classification.protocol.ClassificationSink`
  so it can be registered alongside the performance and notification
  sinks without a separate subscription plumbing.
- Query methods are async to leave room for a durable implementation
  that reaches out to persistence without changing the protocol.
- Summaries are produced in-store so aggregators stay thin; a single
  owner of the category-roll-up logic means consistent numbers no
  matter which caller (signals, analytics, dashboards) reads them.
"""

from typing import TYPE_CHECKING, Protocol, runtime_checkable

if TYPE_CHECKING:
    from datetime import datetime

    from synthorg.engine.classification.models import ClassificationResult, ErrorFinding
    from synthorg.meta.signal_models import OrgErrorSummary


@runtime_checkable
class ErrorTaxonomyStore(Protocol):
    """Stores classification results and produces time-windowed summaries.

    Implementations must be safe to call from multiple concurrent
    tasks; the in-memory default uses a deque and an ``asyncio.Lock``.
    """

    async def on_classification(
        self,
        result: ClassificationResult,
    ) -> None:
        """Append a classification result to the store.

        Best-effort: implementations must log and swallow their own
        errors (except ``MemoryError`` / ``RecursionError``) so the
        detector pipeline is never blocked by store failures.

        Args:
            result: The completed classification result.
        """
        ...

    async def query_findings(
        self,
        *,
        since: datetime,
        until: datetime,
    ) -> tuple[ErrorFinding, ...]:
        """Return findings classified within the window.

        Args:
            since: Start of the observation window (UTC).
            until: End of the observation window (UTC).

        Returns:
            Tuple of findings whose classified_at falls in
            ``[since, until)``.  Ordered newest-first.
        """
        ...

    async def summarize(
        self,
        *,
        since: datetime,
        until: datetime,
    ) -> OrgErrorSummary:
        """Produce the org-wide error summary for the window.

        Args:
            since: Start of the observation window (UTC).
            until: End of the observation window (UTC).

        Returns:
            Populated :class:`OrgErrorSummary`; empty when the window
            contains no classifications.
        """
        ...

    async def count(self) -> int:
        """Return the number of classification results currently stored.

        Useful for diagnostics and the store-size guard in tests.
        """
        ...

    async def clear(self) -> None:
        """Drop all stored results.  Intended for test isolation."""
        ...
