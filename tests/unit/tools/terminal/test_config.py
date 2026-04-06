"""Unit tests for terminal configuration."""

import pytest

from synthorg.tools.terminal.config import TerminalConfig


class TestTerminalConfig:
    """Tests for TerminalConfig model."""

    @pytest.mark.unit
    def test_defaults(self) -> None:
        cfg = TerminalConfig()
        assert cfg.command_allowlist == ()
        assert len(cfg.command_blocklist) > 0
        assert cfg.max_output_bytes == 1_048_576
        assert cfg.default_timeout == 30.0

    @pytest.mark.unit
    def test_frozen(self) -> None:
        cfg = TerminalConfig()
        with pytest.raises(Exception):  # noqa: B017, PT011
            cfg.default_timeout = 10.0  # type: ignore[misc]

    @pytest.mark.unit
    def test_custom_allowlist(self) -> None:
        cfg = TerminalConfig(command_allowlist=("ls", "cat"))
        assert cfg.command_allowlist == ("ls", "cat")

    @pytest.mark.unit
    def test_default_blocklist_contains_dangerous(self) -> None:
        cfg = TerminalConfig()
        blocked = " ".join(cfg.command_blocklist).lower()
        assert "rm -rf /" in blocked
        assert "mkfs" in blocked
        assert "shutdown" in blocked

    @pytest.mark.unit
    def test_timeout_bounds(self) -> None:
        TerminalConfig(default_timeout=1.0)
        TerminalConfig(default_timeout=600.0)
        with pytest.raises(Exception):  # noqa: B017, PT011
            TerminalConfig(default_timeout=0)
        with pytest.raises(Exception):  # noqa: B017, PT011
            TerminalConfig(default_timeout=601)
