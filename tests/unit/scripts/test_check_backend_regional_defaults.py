"""Unit tests for scripts/check_backend_regional_defaults.py.

Exercises every rule (currency, currency-symbol, _usd suffix, locale,
localhost:<port>) plus the suppression marker, the allowlist paths,
and the comment-line skip.
"""

import json
import os
import subprocess
import sys
import uuid
from collections.abc import Generator
from pathlib import Path

import pytest

pytestmark = pytest.mark.unit

_REPO_ROOT = Path(__file__).resolve().parent.parent.parent.parent
_SCRIPT = _REPO_ROOT / "scripts" / "check_backend_regional_defaults.py"


def _write(path: Path, content: str) -> Path:
    """Write a fixture file and return its path."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    return path


def _run(file_path: Path) -> subprocess.CompletedProcess[str]:
    """Invoke the check script in CLI mode on a specific file."""
    # Inputs are test-owned paths pointing at our own script; safe.
    return subprocess.run(  # noqa: S603
        [sys.executable, str(_SCRIPT), str(file_path)],
        capture_output=True,
        text=True,
        cwd=str(_REPO_ROOT),
        check=False,
    )


def _run_hook(file_path: Path) -> subprocess.CompletedProcess[str]:
    """Invoke the check script as a PostToolUse hook."""
    payload = json.dumps({"tool_input": {"file_path": str(file_path)}})
    return subprocess.run(  # noqa: S603
        [sys.executable, str(_SCRIPT)],
        input=payload,
        capture_output=True,
        text=True,
        cwd=str(_REPO_ROOT),
        check=False,
    )


@pytest.fixture
def src_dir() -> Generator[Path]:
    """Create a per-test scratch tree inside ``src/synthorg/``.

    The script computes its project root from ``__file__``, so we cannot
    swap that; instead, write fixtures under a unique subdirectory of
    ``src/synthorg/__tmp_test_fixtures__/`` (per pytest-xdist worker +
    per call) so parallel tests do not race on the same file path.
    """
    worker_id = os.environ.get("PYTEST_XDIST_WORKER", "main")
    unique = f"{worker_id}-{uuid.uuid4().hex[:8]}"
    fixture_root = _REPO_ROOT / "src" / "synthorg" / "__tmp_test_fixtures__" / unique
    fixture_root.mkdir(parents=True, exist_ok=True)
    yield fixture_root
    for path in sorted(fixture_root.rglob("*"), reverse=True):
        if path.is_file():
            path.unlink()
        elif path.is_dir():
            path.rmdir()
    fixture_root.rmdir()


class TestCurrencyDetection:
    """Hardcoded ISO 4217 codes are flagged; unknown codes are not."""

    def test_hardcoded_usd_flagged(self, src_dir: Path) -> None:
        fp = _write(src_dir / "demo.py", 'x = "USD"\n')
        result = _run(fp)
        assert result.returncode == 1
        assert "hardcoded ISO 4217 code" in result.stdout
        assert "USD" in result.stdout

    def test_hardcoded_eur_flagged(self, src_dir: Path) -> None:
        fp = _write(src_dir / "demo.py", 'x = "EUR"\n')
        result = _run(fp)
        assert result.returncode == 1
        assert "EUR" in result.stdout

    def test_three_letter_non_iso_not_flagged(self, src_dir: Path) -> None:
        """Random 3-letter uppercase strings are not flagged."""
        fp = _write(src_dir / "demo.py", 'x = "XYZ"\nkey = "ABC"\n')
        result = _run(fp)
        assert result.returncode == 0

    def test_currency_symbol_adjacent_to_digit(self, src_dir: Path) -> None:
        fp = _write(src_dir / "demo.py", 'msg = "price is $100"\n')
        result = _run(fp)
        assert result.returncode == 1
        assert "hardcoded currency symbol" in result.stdout

    def test_euro_symbol_adjacent_to_digit(self, src_dir: Path) -> None:
        fp = _write(src_dir / "demo.py", 'msg = "price is \u20ac50"\n')
        result = _run(fp)
        assert result.returncode == 1


class TestUsdSuffix:
    """Identifiers ending in ``_usd`` are flagged."""

    def test_cost_usd_field_flagged(self, src_dir: Path) -> None:
        fp = _write(src_dir / "demo.py", "cost_usd = 0.05\n")
        result = _run(fp)
        assert result.returncode == 1
        assert "'_usd'" in result.stdout

    def test_unrelated_identifier_not_flagged(self, src_dir: Path) -> None:
        fp = _write(src_dir / "demo.py", "cost_eur = 0.05\ntotal = 10\n")
        result = _run(fp)
        assert result.returncode == 0


class TestLocale:
    """BCP 47 locale literals are flagged."""

    def test_en_us_flagged(self, src_dir: Path) -> None:
        fp = _write(src_dir / "demo.py", 'locale = "en-US"\n')
        result = _run(fp)
        assert result.returncode == 1
        assert "BCP 47 locale" in result.stdout

    def test_de_de_flagged(self, src_dir: Path) -> None:
        fp = _write(src_dir / "demo.py", 'locale = "de-DE"\n')
        result = _run(fp)
        assert result.returncode == 1


class TestLocalhost:
    """``localhost:<port>`` in application code is flagged."""

    def test_localhost_port_flagged(self, src_dir: Path) -> None:
        fp = _write(src_dir / "demo.py", 'url = "http://localhost:8080/api"\n')
        result = _run(fp)
        assert result.returncode == 1
        assert "localhost:<port>" in result.stdout

    def test_ipv4_localhost_flagged(self, src_dir: Path) -> None:
        fp = _write(src_dir / "demo.py", 'url = "http://127.0.0.1:8080"\n')
        result = _run(fp)
        assert result.returncode == 1

    def test_localhost_without_port_not_flagged(self, src_dir: Path) -> None:
        """Bare ``localhost`` with no port is host-mapping-friendly."""
        fp = _write(src_dir / "demo.py", 'host = "localhost"\n')
        result = _run(fp)
        assert result.returncode == 0


class TestSuppressionMarker:
    """``# lint-allow: regional-defaults`` suppresses findings."""

    def test_marker_on_same_line(self, src_dir: Path) -> None:
        fp = _write(
            src_dir / "demo.py",
            'x = "USD"  # lint-allow: regional-defaults\n',
        )
        result = _run(fp)
        assert result.returncode == 0

    def test_marker_on_preceding_line(self, src_dir: Path) -> None:
        fp = _write(
            src_dir / "demo.py",
            '# lint-allow: regional-defaults\nx = "USD"\n',
        )
        result = _run(fp)
        assert result.returncode == 0


class TestCommentLinesSkipped:
    """Pure-comment lines are not scanned (they discuss forbidden values)."""

    def test_comment_line_with_usd(self, src_dir: Path) -> None:
        fp = _write(src_dir / "demo.py", '# We used to hardcode "USD" here\n')
        result = _run(fp)
        assert result.returncode == 0


class TestScopeLimit:
    """Only ``src/synthorg/`` Python files are scanned."""

    def test_outside_scope_ignored(self, tmp_path: Path) -> None:
        """Files outside src/synthorg/ return 0 regardless of content."""
        fp = _write(tmp_path / "random.py", 'x = "USD"\n')
        result = _run(fp)
        assert result.returncode == 0


class TestHookMode:
    """JSON-on-stdin invocation matches PostToolUse hook contract."""

    def test_hook_clean_file(self, src_dir: Path) -> None:
        fp = _write(src_dir / "demo.py", 'locale = "en"\n')
        result = _run_hook(fp)
        assert result.returncode == 0

    def test_hook_dirty_file(self, src_dir: Path) -> None:
        fp = _write(src_dir / "demo.py", 'x = "USD"\n')
        result = _run_hook(fp)
        assert result.returncode == 1
        assert "USD" in result.stdout
