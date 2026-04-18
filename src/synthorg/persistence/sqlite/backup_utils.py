"""SQLite file-level backup primitives.

Wraps the stdlib ``sqlite3`` operations (``VACUUM INTO``,
``PRAGMA integrity_check``) that sit outside the repository pattern
because they operate on the database *file* rather than on a
repository's logical rows.  Kept inside ``persistence/`` so the
boundary linter's 'only persistence/ may import sqlite3' rule holds.
"""

import contextlib
import sqlite3
from pathlib import Path


def vacuum_into(source_path: str, target_path: str) -> int:
    """Execute ``VACUUM INTO`` to produce a consistent DB copy.

    Args:
        source_path: Path to the live SQLite database.
        target_path: Path for the backup copy.

    Returns:
        Size of the resulting backup file in bytes.
    """
    with contextlib.closing(sqlite3.connect(source_path)) as conn:
        conn.execute("VACUUM INTO ?", (target_path,))
    return Path(target_path).stat().st_size


def integrity_check(db_path: str) -> bool:
    """Run ``PRAGMA integrity_check`` on a SQLite database file."""
    with contextlib.closing(sqlite3.connect(db_path)) as conn:
        result = conn.execute("PRAGMA integrity_check").fetchone()
        return result is not None and result[0] == "ok"
