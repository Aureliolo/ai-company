"""Tests for SandboxResult model."""

import pytest
from pydantic import ValidationError

from ai_company.tools.sandbox.result import SandboxResult

pytestmark = [pytest.mark.unit, pytest.mark.timeout(30)]


class TestSandboxResult:
    """SandboxResult is frozen with a computed ``success`` field."""

    def test_success_when_zero_returncode_no_timeout(self) -> None:
        result = SandboxResult(
            stdout="ok",
            stderr="",
            returncode=0,
        )
        assert result.success is True

    def test_failure_when_nonzero_returncode(self) -> None:
        result = SandboxResult(
            stdout="",
            stderr="error",
            returncode=1,
        )
        assert result.success is False

    def test_failure_when_timed_out(self) -> None:
        result = SandboxResult(
            stdout="",
            stderr="timeout",
            returncode=0,
            timed_out=True,
        )
        assert result.success is False

    def test_failure_when_both_nonzero_and_timed_out(self) -> None:
        result = SandboxResult(
            stdout="",
            stderr="",
            returncode=-1,
            timed_out=True,
        )
        assert result.success is False

    def test_frozen(self) -> None:
        result = SandboxResult(
            stdout="ok",
            stderr="",
            returncode=0,
        )
        with pytest.raises(ValidationError):
            result.stdout = "modified"  # type: ignore[misc]

    def test_timed_out_defaults_false(self) -> None:
        result = SandboxResult(
            stdout="",
            stderr="",
            returncode=0,
        )
        assert result.timed_out is False

    def test_negative_returncode(self) -> None:
        result = SandboxResult(
            stdout="",
            stderr="signal",
            returncode=-9,
        )
        assert result.success is False
