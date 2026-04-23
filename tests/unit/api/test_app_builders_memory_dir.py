"""Tests for the tmp-root fallback logging in ``_allowed_memory_dir_roots``.

When ``tempfile.gettempdir()`` raises ``OSError`` / ``RuntimeError``
the helper drops the temp root silently for callers, but emits a
WARNING so operators can see that only ``/data`` is allowed.
"""

import os
import tempfile
from pathlib import Path

import pytest
import structlog.testing

from synthorg.api import app_builders


@pytest.mark.unit
class TestAllowedMemoryDirRoots:
    """Fallback behavior when tempfile lookup fails."""

    def test_tmproot_fallback_logs_warning(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """OSError from ``gettempdir`` logs ``API_MEMORY_DIR_TMPROOT_FALLBACK``."""

        def _boom() -> str:
            msg = "disk full"
            raise OSError(msg)

        monkeypatch.setattr(tempfile, "gettempdir", _boom)

        with structlog.testing.capture_logs() as logs:
            roots = app_builders._allowed_memory_dir_roots()

        # Only the prod ``/data`` root remains; no tmp root appended.
        assert roots == (str(Path("/data")),)
        fallback_logs = [
            log for log in logs if log.get("event") == "api.memory_dir.tmproot_fallback"
        ]
        assert len(fallback_logs) == 1
        log = fallback_logs[0]
        assert log["log_level"] == "warning"
        assert log["error_type"] == "OSError"
        assert isinstance(log["error"], str)
        assert log["error"]

    def test_happy_path_has_tmproot(self) -> None:
        """With a working ``gettempdir`` the tmp root is appended."""
        roots = app_builders._allowed_memory_dir_roots()

        assert roots[0] == str(Path("/data"))
        assert len(roots) == 2
        assert os.path.normcase(roots[1]) == os.path.normcase(
            str(Path(tempfile.gettempdir())),
        )
