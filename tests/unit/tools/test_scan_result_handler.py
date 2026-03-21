"""Tests for handle_sensitive_scan routing logic."""

from unittest.mock import patch

import pytest

from synthorg.providers.models import ToolCall
from synthorg.security.models import OutputScanResult, ScanOutcome
from synthorg.tools.base import ToolExecutionResult
from synthorg.tools.scan_result_handler import handle_sensitive_scan

pytestmark = pytest.mark.unit


def _make_tool_call() -> ToolCall:
    return ToolCall(id="tc-1", name="read_file", arguments={"path": "/workspace"})


def _make_result(**overrides: object) -> ToolExecutionResult:
    defaults: dict[str, object] = {
        "content": "original output",
        "is_error": False,
        "metadata": {"tool_name": "read_file"},
    }
    defaults.update(overrides)
    return ToolExecutionResult(**defaults)  # type: ignore[arg-type]


class TestWithheld:
    """WITHHELD outcome returns error with policy message."""

    def test_returns_error(self) -> None:
        scan = OutputScanResult(
            has_sensitive_data=True,
            findings=("API key detected",),
            outcome=ScanOutcome.WITHHELD,
        )
        result = handle_sensitive_scan(_make_tool_call(), _make_result(), scan)
        assert result.is_error is True
        assert "withheld by security policy" in result.content

    def test_metadata_has_withheld_flag(self) -> None:
        scan = OutputScanResult(
            has_sensitive_data=True,
            findings=("secret found",),
            outcome=ScanOutcome.WITHHELD,
        )
        result = handle_sensitive_scan(_make_tool_call(), _make_result(), scan)
        assert result.metadata["output_withheld"] is True

    def test_preserves_original_metadata_keys(self) -> None:
        scan = OutputScanResult(
            has_sensitive_data=True,
            findings=("secret found",),
            outcome=ScanOutcome.WITHHELD,
        )
        original = _make_result(metadata={"custom_key": "value"})
        result = handle_sensitive_scan(_make_tool_call(), original, scan)
        assert result.metadata["custom_key"] == "value"
        assert result.metadata["output_withheld"] is True

    def test_logs_withheld_event(self) -> None:
        scan = OutputScanResult(
            has_sensitive_data=True,
            findings=("API key detected",),
            outcome=ScanOutcome.WITHHELD,
        )
        with patch("synthorg.tools.scan_result_handler.logger") as mock_logger:
            handle_sensitive_scan(_make_tool_call(), _make_result(), scan)
            mock_logger.warning.assert_called_once()
            call_args = mock_logger.warning.call_args
            assert call_args[0][0] == "tool.output.withheld"


class TestRedacted:
    """REDACTED outcome returns redacted content."""

    def test_returns_redacted_content(self) -> None:
        scan = OutputScanResult(
            has_sensitive_data=True,
            findings=("password redacted",),
            redacted_content="output with [REDACTED]",
            outcome=ScanOutcome.REDACTED,
        )
        result = handle_sensitive_scan(_make_tool_call(), _make_result(), scan)
        assert result.content == "output with [REDACTED]"

    @pytest.mark.parametrize("initial_is_error", [True, False])
    def test_preserves_original_is_error(self, initial_is_error: bool) -> None:
        scan = OutputScanResult(
            has_sensitive_data=True,
            findings=("token redacted",),
            redacted_content="safe content",
            outcome=ScanOutcome.REDACTED,
        )
        original = _make_result(is_error=initial_is_error)
        result = handle_sensitive_scan(_make_tool_call(), original, scan)
        assert result.is_error is initial_is_error

    def test_metadata_has_redacted_flag_and_findings(self) -> None:
        scan = OutputScanResult(
            has_sensitive_data=True,
            findings=("password found", "token found"),
            redacted_content="safe",
            outcome=ScanOutcome.REDACTED,
        )
        result = handle_sensitive_scan(_make_tool_call(), _make_result(), scan)
        assert result.metadata["output_redacted"] is True
        assert result.metadata["redaction_findings"] == [
            "password found",
            "token found",
        ]

    def test_preserves_original_metadata_keys(self) -> None:
        scan = OutputScanResult(
            has_sensitive_data=True,
            findings=("secret redacted",),
            redacted_content="safe",
            outcome=ScanOutcome.REDACTED,
        )
        original = _make_result(metadata={"custom": 42})
        result = handle_sensitive_scan(_make_tool_call(), original, scan)
        assert result.metadata["custom"] == 42
        assert result.metadata["output_redacted"] is True

    def test_logs_redacted_event(self) -> None:
        scan = OutputScanResult(
            has_sensitive_data=True,
            findings=("password redacted",),
            redacted_content="safe",
            outcome=ScanOutcome.REDACTED,
        )
        with patch("synthorg.tools.scan_result_handler.logger") as mock_logger:
            handle_sensitive_scan(_make_tool_call(), _make_result(), scan)
            mock_logger.warning.assert_called_once()
            call_args = mock_logger.warning.call_args
            assert call_args[0][0] == "tool.output.redacted"


class TestDefensiveFallback:
    """REDACTED with None redacted_content falls back to withhold."""

    def test_returns_error_with_fail_closed(self) -> None:
        # Use model_construct to bypass validator that enforces
        # redacted_content is not None when outcome=REDACTED.
        scan = OutputScanResult.model_construct(
            has_sensitive_data=True,
            findings=("something sensitive",),
            redacted_content=None,
            outcome=ScanOutcome.REDACTED,
        )
        result = handle_sensitive_scan(_make_tool_call(), _make_result(), scan)
        assert result.is_error is True
        assert "fail-closed" in result.content

    def test_metadata_has_scan_failed_flag(self) -> None:
        scan = OutputScanResult.model_construct(
            has_sensitive_data=True,
            findings=("sensitive data",),
            redacted_content=None,
            outcome=ScanOutcome.REDACTED,
        )
        result = handle_sensitive_scan(_make_tool_call(), _make_result(), scan)
        assert result.metadata["output_scan_failed"] is True

    def test_preserves_original_metadata_keys(self) -> None:
        scan = OutputScanResult.model_construct(
            has_sensitive_data=True,
            findings=("sensitive data",),
            redacted_content=None,
            outcome=ScanOutcome.REDACTED,
        )
        original = _make_result(metadata={"origin": "test"})
        result = handle_sensitive_scan(_make_tool_call(), original, scan)
        assert result.metadata["origin"] == "test"
        assert result.metadata["output_scan_failed"] is True

    def test_logs_withheld_event_with_outcome(self) -> None:
        scan = OutputScanResult.model_construct(
            has_sensitive_data=True,
            findings=("sensitive data",),
            redacted_content=None,
            outcome=ScanOutcome.REDACTED,
        )
        with patch("synthorg.tools.scan_result_handler.logger") as mock_logger:
            handle_sensitive_scan(_make_tool_call(), _make_result(), scan)
            mock_logger.warning.assert_called_once()
            call_args = mock_logger.warning.call_args
            assert call_args[0][0] == "tool.output.withheld"
            assert call_args[1]["outcome"] == "redacted"


class TestLogOnlyFallback:
    """LOG_ONLY outcome triggers defensive fail-closed (unexpected path)."""

    def test_log_only_returns_fail_closed_error(self) -> None:
        # LOG_ONLY normally has has_sensitive_data=False, so it should
        # never reach handle_sensitive_scan.  Use model_construct to
        # bypass the validator and verify the defensive fallback.
        scan = OutputScanResult.model_construct(
            has_sensitive_data=True,
            findings=("secret detected",),
            redacted_content=None,
            outcome=ScanOutcome.LOG_ONLY,
        )
        result = handle_sensitive_scan(_make_tool_call(), _make_result(), scan)
        assert result.is_error is True
        assert "fail-closed" in result.content
        assert result.metadata["output_scan_failed"] is True

    def test_log_only_logs_outcome_value(self) -> None:
        scan = OutputScanResult.model_construct(
            has_sensitive_data=True,
            findings=("secret detected",),
            redacted_content=None,
            outcome=ScanOutcome.LOG_ONLY,
        )
        with patch("synthorg.tools.scan_result_handler.logger") as mock_logger:
            handle_sensitive_scan(_make_tool_call(), _make_result(), scan)
            mock_logger.warning.assert_called_once()
            call_args = mock_logger.warning.call_args
            assert call_args[0][0] == "tool.output.withheld"
            assert call_args[1]["outcome"] == "log_only"
