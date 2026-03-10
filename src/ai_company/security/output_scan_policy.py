"""Output scan response policies.

Pluggable strategies that transform ``OutputScanResult`` after the
output scanner runs.  Each policy decides how to handle detected
sensitive data — redact, withhold, log-only, or delegate based on
autonomy level.
"""

from typing import TYPE_CHECKING, Protocol, runtime_checkable

from ai_company.core.enums import AutonomyLevel
from ai_company.observability import get_logger
from ai_company.observability.events.security import (
    SECURITY_OUTPUT_SCAN_POLICY_APPLIED,
)
from ai_company.security.models import OutputScanResult

if TYPE_CHECKING:
    from collections.abc import Mapping

    from ai_company.security.autonomy.models import EffectiveAutonomy
    from ai_company.security.models import SecurityContext

logger = get_logger(__name__)


@runtime_checkable
class OutputScanResponsePolicy(Protocol):
    """Protocol for output scan response policies.

    Implementations decide how to transform an ``OutputScanResult``
    before it is returned to the invoker.
    """

    @property
    def name(self) -> str:
        """Policy name identifier."""
        ...

    def apply(
        self,
        scan_result: OutputScanResult,
        context: SecurityContext,
    ) -> OutputScanResult:
        """Apply the policy to a scan result.

        Args:
            scan_result: Result from the output scanner.
            context: Security context of the tool invocation.

        Returns:
            Transformed scan result.
        """
        ...


class RedactPolicy:
    """Return scan result as-is (redacted content preserved).

    This is the default policy — the scanner's redaction stands.
    """

    @property
    def name(self) -> str:
        """Policy name identifier."""
        return "redact"

    def apply(
        self,
        scan_result: OutputScanResult,
        context: SecurityContext,  # noqa: ARG002
    ) -> OutputScanResult:
        """Pass through the scan result unchanged.

        Args:
            scan_result: Result from the output scanner.
            context: Security context (unused).

        Returns:
            The original scan result.
        """
        logger.debug(
            SECURITY_OUTPUT_SCAN_POLICY_APPLIED,
            policy="redact",
            has_sensitive_data=scan_result.has_sensitive_data,
        )
        return scan_result


class WithholdPolicy:
    """Clear redacted content when sensitive data is found.

    Forces fail-closed in the invoker — no partial data is returned.
    """

    @property
    def name(self) -> str:
        """Policy name identifier."""
        return "withhold"

    def apply(
        self,
        scan_result: OutputScanResult,
        context: SecurityContext,  # noqa: ARG002
    ) -> OutputScanResult:
        """Clear redacted content on sensitive results.

        Args:
            scan_result: Result from the output scanner.
            context: Security context (unused).

        Returns:
            Scan result with ``redacted_content`` cleared if sensitive.
        """
        logger.debug(
            SECURITY_OUTPUT_SCAN_POLICY_APPLIED,
            policy="withhold",
            has_sensitive_data=scan_result.has_sensitive_data,
        )
        if not scan_result.has_sensitive_data:
            return scan_result
        return scan_result.model_copy(update={"redacted_content": None})


class LogOnlyPolicy:
    """Return an empty result — findings are logged but output passes through.

    Suitable for audit-only mode or high-trust agents where output
    scanning is informational rather than enforced.
    """

    @property
    def name(self) -> str:
        """Policy name identifier."""
        return "log_only"

    def apply(
        self,
        scan_result: OutputScanResult,
        context: SecurityContext,  # noqa: ARG002
    ) -> OutputScanResult:
        """Return empty result regardless of findings.

        Args:
            scan_result: Result from the output scanner.
            context: Security context (unused).

        Returns:
            Empty ``OutputScanResult``.
        """
        logger.debug(
            SECURITY_OUTPUT_SCAN_POLICY_APPLIED,
            policy="log_only",
            has_sensitive_data=scan_result.has_sensitive_data,
        )
        return OutputScanResult()


# Default autonomy-to-policy mapping.
_DEFAULT_AUTONOMY_POLICY_MAP: dict[AutonomyLevel, OutputScanResponsePolicy] = {
    AutonomyLevel.FULL: LogOnlyPolicy(),
    AutonomyLevel.SEMI: RedactPolicy(),
    AutonomyLevel.SUPERVISED: RedactPolicy(),
    AutonomyLevel.LOCKED: WithholdPolicy(),
}


class AutonomyTieredPolicy:
    """Delegate to sub-policies based on the effective autonomy level.

    Uses a configurable mapping from ``AutonomyLevel`` to a concrete
    policy.  Falls back to ``RedactPolicy`` when no autonomy is set.
    """

    def __init__(
        self,
        *,
        effective_autonomy: EffectiveAutonomy | None,
        policy_map: Mapping[AutonomyLevel, OutputScanResponsePolicy] | None = None,
    ) -> None:
        """Initialize with autonomy and optional policy map.

        Args:
            effective_autonomy: Resolved autonomy for the current run.
            policy_map: Mapping from autonomy level to policy. Uses
                defaults when ``None``.
        """
        self._effective_autonomy = effective_autonomy
        self._policy_map: Mapping[AutonomyLevel, OutputScanResponsePolicy] = (
            policy_map if policy_map is not None else _DEFAULT_AUTONOMY_POLICY_MAP
        )
        self._fallback: OutputScanResponsePolicy = RedactPolicy()

    @property
    def name(self) -> str:
        """Policy name identifier."""
        return "autonomy_tiered"

    def apply(
        self,
        scan_result: OutputScanResult,
        context: SecurityContext,
    ) -> OutputScanResult:
        """Delegate to the sub-policy for the current autonomy level.

        Args:
            scan_result: Result from the output scanner.
            context: Security context of the tool invocation.

        Returns:
            Transformed scan result from the delegated policy.
        """
        if self._effective_autonomy is None:
            delegate = self._fallback
        else:
            level = self._effective_autonomy.level
            delegate = self._policy_map.get(level, self._fallback)

        logger.debug(
            SECURITY_OUTPUT_SCAN_POLICY_APPLIED,
            policy="autonomy_tiered",
            delegate=delegate.name,
            autonomy_level=(
                self._effective_autonomy.level.value
                if self._effective_autonomy is not None
                else None
            ),
        )
        return delegate.apply(scan_result, context)
