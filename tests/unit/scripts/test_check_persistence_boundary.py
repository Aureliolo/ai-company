"""Unit tests for scripts/check_persistence_boundary.py.

Exercises the three things that matter: the driver-import matcher, the
raw-SQL literal matcher, and the ``# lint-allow: persistence-boundary
-- <reason>`` suppression marker (including its non-empty-justification
requirement).  Also covers the path-based boundary prefix logic and the
allowlist, since both carve out exceptions that regressions could
easily invalidate.

Tests load the script as a module and call its private helpers
directly rather than spawning subprocesses -- the script discovers its
project root from ``__file__``, so a subprocess invocation from tests
would scan the real source tree.
"""

import importlib.util
from pathlib import Path

import pytest

pytestmark = pytest.mark.unit

_REPO_ROOT = Path(__file__).resolve().parent.parent.parent.parent
_SCRIPT_PATH = _REPO_ROOT / "scripts" / "check_persistence_boundary.py"


def _load_script_module() -> object:
    """Import the script as a module so its private helpers are callable."""
    spec = importlib.util.spec_from_file_location(
        "_check_persistence_boundary",
        _SCRIPT_PATH,
    )
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


_MODULE = _load_script_module()


# ── driver-import matcher ───────────────────────────────────────


@pytest.mark.parametrize(
    "source",
    [
        "import aiosqlite\n",
        "import sqlite3\n",
        "import psycopg\n",
        "import psycopg_pool\n",
        "from aiosqlite import Connection\n",
        "from sqlite3 import Row\n",
        "from psycopg.rows import dict_row\n",
        "from psycopg_pool import AsyncConnectionPool\n",
        "    import aiosqlite\n",  # indented inside a TYPE_CHECKING block
        "    from psycopg import Connection\n",
    ],
)
def test_driver_import_flagged_outside_boundary(source: str, tmp_path: Path) -> None:
    """Every forbidden driver import form produces a violation."""
    target = tmp_path / "leak.py"
    target.write_text(source, encoding="utf-8")
    issues = _MODULE._scan_file(target, "src/synthorg/leak.py")  # type: ignore[attr-defined]
    assert len(issues) == 1
    assert "imports" in issues[0]


def test_non_forbidden_import_is_silent(tmp_path: Path) -> None:
    """Unrelated imports must not trip the matcher."""
    target = tmp_path / "clean.py"
    target.write_text("import asyncio\nfrom dataclasses import dataclass\n")
    assert (
        _MODULE._scan_file(target, "src/synthorg/clean.py")  # type: ignore[attr-defined]
        == []
    )


def test_comment_lines_are_not_scanned(tmp_path: Path) -> None:
    """A comment that mentions a driver name must not trip the matcher."""
    target = tmp_path / "commented.py"
    target.write_text("# This uses aiosqlite internally, documented above.\n")
    assert (
        _MODULE._scan_file(target, "src/synthorg/commented.py")  # type: ignore[attr-defined]
        == []
    )


# ── raw SQL literal matcher ─────────────────────────────────────


@pytest.mark.parametrize(
    "source",
    [
        'query = "CREATE TABLE foo (id INT)"\n',
        'sql = "INSERT INTO foo VALUES (1)"\n',
        'stmt = "ALTER TABLE foo ADD COLUMN bar TEXT"\n',
        'cleanup = "DROP TABLE foo"\n',
        'upd = "UPDATE foo SET bar = 1"\n',
        'rm = "DELETE FROM foo"\n',
        # Case-insensitive
        'lc = "create table foo (id int)"\n',
    ],
)
def test_raw_sql_in_literal_flagged(source: str, tmp_path: Path) -> None:
    """Each DDL/DML keyword pattern inside a string literal is a violation."""
    target = tmp_path / "raw.py"
    target.write_text(source, encoding="utf-8")
    issues = _MODULE._scan_file(target, "src/synthorg/raw.py")  # type: ignore[attr-defined]
    assert len(issues) == 1
    assert "raw SQL" in issues[0]


def test_raw_sql_keywords_in_identifiers_not_flagged(tmp_path: Path) -> None:
    """``CREATE_TABLE_PATTERN`` must not look like ``CREATE TABLE ...``."""
    target = tmp_path / "idents.py"
    target.write_text(
        "CREATE_TABLE_PATTERN = compile('x')\n"
        "INSERTION_COUNT = 0\n"
        "DROP_ALL_LABEL = 'drop_all'\n",
    )
    assert (
        _MODULE._scan_file(target, "src/synthorg/idents.py")  # type: ignore[attr-defined]
        == []
    )


# ── suppression marker ──────────────────────────────────────────


def test_marker_with_justification_suppresses(tmp_path: Path) -> None:
    """Valid marker + non-empty justification silences the line."""
    target = tmp_path / "allowed.py"
    target.write_text(
        "import aiosqlite  "
        "# lint-allow: persistence-boundary -- legacy shim scheduled for removal\n",
    )
    assert (
        _MODULE._scan_file(target, "src/synthorg/allowed.py")  # type: ignore[attr-defined]
        == []
    )


def test_marker_without_justification_still_flags(tmp_path: Path) -> None:
    """Marker requires ``-- <reason>`` with non-empty reason."""
    target = tmp_path / "bad_marker.py"
    target.write_text(
        "import aiosqlite  # lint-allow: persistence-boundary\n",
    )
    assert (
        _MODULE._scan_file(target, "src/synthorg/bad.py")  # type: ignore[attr-defined]
        != []
    )


def test_marker_with_empty_justification_still_flags(tmp_path: Path) -> None:
    """``-- `` with only whitespace is treated as missing justification."""
    target = tmp_path / "empty_just.py"
    target.write_text(
        "import aiosqlite  # lint-allow: persistence-boundary --   \n",
    )
    assert (
        _MODULE._scan_file(target, "src/synthorg/empty.py")  # type: ignore[attr-defined]
        != []
    )


def test_marker_without_double_dash_still_flags(tmp_path: Path) -> None:
    """Marker alone (no ``--``) is not a valid suppression."""
    target = tmp_path / "no_dash.py"
    target.write_text(
        "import aiosqlite  # lint-allow: persistence-boundary legacy shim\n",
    )
    assert (
        _MODULE._scan_file(target, "src/synthorg/no_dash.py")  # type: ignore[attr-defined]
        != []
    )


# ── boundary prefix logic ───────────────────────────────────────


@pytest.mark.parametrize(
    "rel",
    [
        "src/synthorg/persistence/sqlite/session_repo.py",
        "src/synthorg/persistence/postgres/backend.py",
        "tests/conformance/persistence/test_user_repository.py",
        "tests/unit/persistence/test_config.py",
        "tests/integration/persistence/test_fresh_install_postgres_cli.py",
        "tests/unit/api/auth/test_session_store.py",
        "tests/unit/backup/test_handlers/test_persistence_handler.py",
    ],
)
def test_persistence_prefixes_are_inside_boundary(rel: str) -> None:
    """Paths under the persistence tree are never flagged."""
    assert _MODULE._is_inside_boundary(rel)  # type: ignore[attr-defined]


@pytest.mark.parametrize(
    "rel",
    [
        "src/synthorg/api/auth/controller.py",
        "src/synthorg/memory/org/hybrid_backend.py",
        "src/synthorg/ontology/versioning.py",
        "tests/unit/api/test_app.py",
    ],
)
def test_non_persistence_paths_are_outside_boundary(rel: str) -> None:
    """Ordinary application modules and tests are inside scope."""
    assert not _MODULE._is_inside_boundary(rel)  # type: ignore[attr-defined]


# ── allowlist covers documented exceptions ──────────────────────


def test_allowlist_contains_tools_database_modules() -> None:
    """The two agent-facing SQL tools must remain allowlisted -- issue #1457."""
    allowlist = _MODULE._ALLOWLIST  # type: ignore[attr-defined]
    assert "src/synthorg/tools/database/schema_inspect.py" in allowlist
    assert "src/synthorg/tools/database/sql_query.py" in allowlist


def test_self_is_allowlisted() -> None:
    """The checker itself names drivers in patterns/messages."""
    assert (
        "scripts/check_persistence_boundary.py" in _MODULE._ALLOWLIST  # type: ignore[attr-defined]
    )
