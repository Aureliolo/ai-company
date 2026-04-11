"""Composite detector that merges findings from multiple variants.

Runs multiple detectors of the same category concurrently via
``asyncio.TaskGroup`` and deduplicates the collected findings.
"""

import asyncio
import hashlib
from typing import TYPE_CHECKING

from synthorg.engine.classification.models import (
    ErrorFinding,
    ErrorSeverity,
)
from synthorg.observability import get_logger
from synthorg.observability.events.classification import (
    CLASSIFICATION_FINDING_DEDUPLICATED,
    DETECTOR_COMPLETE,
    DETECTOR_START,
)

if TYPE_CHECKING:
    from synthorg.budget.coordination_config import (
        DetectionScope,
        ErrorCategory,
    )
    from synthorg.engine.classification.protocol import (
        DetectionContext,
        Detector,
    )

logger = get_logger(__name__)

_SEVERITY_ORDER = {
    ErrorSeverity.LOW: 0,
    ErrorSeverity.MEDIUM: 1,
    ErrorSeverity.HIGH: 2,
}


def _dedup_key(finding: ErrorFinding) -> str:
    """Build a dedup key from turn_range + description hash + category."""
    desc_hash = hashlib.sha256(
        finding.description.encode(),
    ).hexdigest()[:16]
    return f"{finding.turn_range!r}|{desc_hash}|{finding.category.value}"


def deduplicate_findings(
    findings: tuple[ErrorFinding, ...],
) -> tuple[ErrorFinding, ...]:
    """Remove duplicate findings, keeping highest severity per group.

    Dedup key: ``(turn_range, sha256(description)[:16], category)``.
    When severity ties, evidence tuples are merged.

    Args:
        findings: Raw findings from multiple detectors.

    Returns:
        Deduplicated findings tuple.
    """
    if not findings:
        return ()

    groups: dict[str, ErrorFinding] = {}
    for finding in findings:
        key = _dedup_key(finding)
        existing = groups.get(key)
        if existing is None:
            groups[key] = finding
        else:
            # Keep the higher severity; merge evidence
            existing_rank = _SEVERITY_ORDER[existing.severity]
            new_rank = _SEVERITY_ORDER[finding.severity]
            winner = finding if new_rank > existing_rank else existing
            merged_evidence = existing.evidence + tuple(
                e for e in finding.evidence if e not in existing.evidence
            )
            groups[key] = ErrorFinding(
                category=winner.category,
                severity=winner.severity,
                description=winner.description,
                evidence=merged_evidence,
                turn_range=winner.turn_range,
            )

    deduped = tuple(groups.values())
    removed = len(findings) - len(deduped)
    if removed > 0:
        logger.debug(
            CLASSIFICATION_FINDING_DEDUPLICATED,
            removed_count=removed,
            original_count=len(findings),
        )
    return deduped


class CompositeDetector:
    """Merges findings from multiple variants of the same category.

    All sub-detectors must target the same ``ErrorCategory``.
    Runs them concurrently and deduplicates the collected findings.

    Args:
        detectors: Detector instances to compose.

    Raises:
        ValueError: If detectors have mixed categories or
            the tuple is empty.
    """

    def __init__(self, detectors: tuple[Detector, ...]) -> None:
        if not detectors:
            msg = "detectors must not be empty"
            raise ValueError(msg)
        cats = {d.category for d in detectors}
        if len(cats) > 1:
            msg = f"All detectors must share a category, got: {cats}"
            raise ValueError(msg)
        self._detectors = detectors

    @property
    def category(self) -> ErrorCategory:
        """Shared error category of all sub-detectors."""
        return self._detectors[0].category

    @property
    def supported_scopes(self) -> frozenset[DetectionScope]:
        """Union of all sub-detector scopes."""
        scopes: set[DetectionScope] = set()
        for d in self._detectors:
            scopes |= d.supported_scopes
        return frozenset(scopes)

    async def detect(
        self,
        context: DetectionContext,
    ) -> tuple[ErrorFinding, ...]:
        """Run all sub-detectors and return deduplicated findings.

        Sub-detectors run concurrently inside an ``asyncio.TaskGroup``.
        Findings are collected from task results without mutating
        shared state from inside the tasks.

        Args:
            context: Detection context with execution data.

        Returns:
            Deduplicated findings from all sub-detectors.
        """
        logger.debug(
            DETECTOR_START,
            detector=f"composite({self.category.value})",
            message_count=len(self._detectors),
        )

        async with asyncio.TaskGroup() as tg:
            tasks = [
                tg.create_task(detector.detect(context)) for detector in self._detectors
            ]

        all_findings: list[ErrorFinding] = []
        for task in tasks:
            all_findings.extend(task.result())

        deduped = deduplicate_findings(tuple(all_findings))
        logger.debug(
            DETECTOR_COMPLETE,
            detector=f"composite({self.category.value})",
            finding_count=len(deduped),
        )
        return deduped
