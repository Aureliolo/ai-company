"""Atlas CLI wrapper for declarative schema migrations.

Provides an async Python interface to the Atlas CLI for applying
migrations, checking status, and detecting drift.  Atlas manages
the ``atlas_schema_revisions`` table automatically.
"""

import asyncio
import importlib.resources
import json
import shutil
from dataclasses import dataclass
from pathlib import Path, PurePosixPath, PureWindowsPath

from synthorg.observability import get_logger
from synthorg.observability.events.persistence import (
    PERSISTENCE_MIGRATION_COMPLETED,
    PERSISTENCE_MIGRATION_FAILED,
    PERSISTENCE_MIGRATION_STARTED,
)
from synthorg.persistence.errors import MigrationError

logger = get_logger(__name__)

_ATLAS_BIN = "atlas"


def _redact_url(url: str) -> str:
    """Return scheme + host hint, stripping path/credentials."""
    scheme_end = url.find("://")
    if scheme_end == -1:
        return "REDACTED"
    return f"{url[:scheme_end]}://..."


@dataclass(frozen=True)
class MigrateResult:
    """Result of an ``atlas migrate apply`` invocation.

    Attributes:
        applied_count: Number of migrations applied in this run.
        current_version: The version the database is now at.
        output: Raw stdout from the Atlas CLI.
    """

    applied_count: int
    current_version: str
    output: str


@dataclass(frozen=True)
class MigrateStatus:
    """Current migration status of a database.

    Attributes:
        current_version: Latest applied migration version.
        pending_count: Number of migrations not yet applied.
        output: Raw stdout from the Atlas CLI.
    """

    current_version: str
    pending_count: int
    output: str


def _to_posix(path: str) -> str:
    r"""Convert a filesystem path to forward-slash POSIX form.

    On Windows, ``C:\\Users\\foo`` becomes ``C:/Users/foo``.
    On POSIX systems this is a no-op.
    """
    return str(PurePosixPath(PureWindowsPath(path)))


def _path_to_file_url(path: str) -> str:
    r"""Convert a filesystem path to a ``file://`` URL.

    Handles Windows drive-letter paths (``C:\\...``) by converting
    to forward slashes.  Atlas on Windows expects ``file://C:/...``
    (two slashes), not the RFC 8089 ``file:///C:/...`` (three).
    """
    posix_str = _to_posix(path)
    return f"file://{posix_str}"


def to_sqlite_url(path: str) -> str:
    r"""Convert a filesystem path to an Atlas SQLite URL.

    Atlas expects ``sqlite://C:/path/db.sqlite`` on Windows
    (forward-slash path), not ``sqlite://C:\\...``.

    Args:
        path: Database file path (native OS format).

    Returns:
        Atlas-compatible ``sqlite://`` URL.

    Raises:
        MigrationError: If *path* is ``":memory:"`` -- Atlas runs as
            a separate process and cannot target an in-memory database
            opened by aiosqlite in this process.
    """
    if path == ":memory:":
        msg = (
            "Atlas cannot migrate in-memory databases -- "
            "it runs as a separate process.  Use a file-backed "
            "database path instead."
        )
        logger.error(PERSISTENCE_MIGRATION_FAILED, error=msg)
        raise MigrationError(msg)
    posix_str = _to_posix(path)
    return f"sqlite://{posix_str}"


def copy_revisions(dest: Path) -> str:
    """Copy the revisions directory to *dest* and return its ``file://`` URL.

    Creates an isolated copy of the migration files so that parallel
    Atlas processes do not fight over a shared directory lock.
    Intended for test fixtures using ``tmp_path``.

    Args:
        dest: Destination directory (e.g. ``tmp_path / "revisions"``).

    Returns:
        A ``file://`` URL pointing to the copy.

    Raises:
        MigrationError: If the copy fails (permissions, disk space,
            destination already exists).
    """
    src_ref = importlib.resources.files(
        "synthorg.persistence.sqlite.revisions",
    )
    try:
        shutil.copytree(str(src_ref), str(dest))
    except (OSError, shutil.Error) as exc:
        msg = f"Failed to copy migration revisions to {dest}: {exc}"
        logger.exception(PERSISTENCE_MIGRATION_FAILED, error=str(exc))
        raise MigrationError(msg) from exc
    return _path_to_file_url(str(dest))


def _revisions_dir() -> str:
    """Return a ``file://`` URL pointing to the revisions directory.

    Uses ``importlib.resources`` to locate the ``revisions`` package
    inside the installed ``synthorg`` distribution.

    Returns:
        A ``file://`` URL suitable for Atlas ``--dir``.

    Raises:
        MigrationError: If the revisions directory cannot be located.
    """
    try:
        ref = importlib.resources.files(
            "synthorg.persistence.sqlite.revisions",
        )
        path = str(ref)
    except (ModuleNotFoundError, TypeError) as exc:
        msg = "Cannot locate migration revisions package"
        logger.exception(PERSISTENCE_MIGRATION_FAILED, error=str(exc))
        raise MigrationError(msg) from exc
    return _path_to_file_url(path)


def _require_atlas() -> str:
    """Return the path to the Atlas binary, or raise.

    Raises:
        MigrationError: If the Atlas CLI is not found on ``PATH``.
    """
    path = shutil.which(_ATLAS_BIN)
    if path is None:
        msg = (
            "Atlas CLI not found on PATH. "
            "Install from https://atlasgo.io/getting-started"
        )
        logger.error(PERSISTENCE_MIGRATION_FAILED, error=msg)
        raise MigrationError(msg)
    return path


async def _run_atlas(
    *args: str,
    db_url: str | None = None,
    revisions_url: str | None = None,
    skip_lock: bool = False,
) -> tuple[str, str]:
    """Run an Atlas CLI command and return (stdout, stderr).

    Args:
        *args: Atlas subcommand and flags.
        db_url: Optional ``--url`` value for the target database.
        revisions_url: Override for the ``--dir`` revisions URL.
            When ``None``, the installed package location is used.
        skip_lock: If ``True``, append ``--skip-lock`` to disable
            Atlas directory locking.  Use only in test fixtures
            where each worker has an isolated revisions copy.

    Returns:
        Tuple of (stdout, stderr) as decoded strings.

    Raises:
        MigrationError: If the command exits with a non-zero code.
    """
    atlas_bin = _require_atlas()
    rev_url = revisions_url or _revisions_dir()

    cmd: list[str] = [
        atlas_bin,
        *args,
        "--dir",
        rev_url,
    ]
    if skip_lock:
        cmd.append("--skip-lock")
    if db_url is not None:
        cmd.extend(["--url", db_url])

    # Redact --url value to avoid leaking credentials in logs.
    safe_cmd = []
    skip_next = False
    for token in cmd:
        if skip_next:
            safe_cmd.append("REDACTED")
            skip_next = False
        elif token == "--url":  # noqa: S105
            safe_cmd.append(token)
            skip_next = True
        else:
            safe_cmd.append(token)
    logger.debug(
        PERSISTENCE_MIGRATION_STARTED,
        command=" ".join(safe_cmd),
    )

    try:
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdin=asyncio.subprocess.DEVNULL,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
    except OSError as exc:
        msg = f"Failed to start Atlas process: {exc}"
        logger.exception(PERSISTENCE_MIGRATION_FAILED, error=msg)
        raise MigrationError(msg) from exc

    try:
        stdout_bytes, stderr_bytes = await proc.communicate()
    except asyncio.CancelledError:
        proc.kill()
        await proc.wait()
        logger.warning(
            PERSISTENCE_MIGRATION_FAILED,
            note="Atlas process killed due to cancellation",
        )
        raise
    except OSError as exc:
        proc.kill()
        await proc.wait()
        msg = f"Atlas process communication failed: {exc}"
        logger.exception(PERSISTENCE_MIGRATION_FAILED, error=msg)
        raise MigrationError(msg) from exc

    stdout = stdout_bytes.decode()
    stderr = stderr_bytes.decode()

    if proc.returncode != 0:
        msg = f"Atlas command failed (exit {proc.returncode}): {stderr}"
        logger.error(
            PERSISTENCE_MIGRATION_FAILED,
            exit_code=proc.returncode,
            stderr=stderr,
        )
        raise MigrationError(msg)

    return stdout, stderr


async def migrate_apply(
    db_url: str,
    *,
    revisions_url: str | None = None,
    skip_lock: bool = False,
) -> MigrateResult:
    """Apply pending migrations to the target database.

    Invokes ``atlas migrate apply`` with JSON output parsing.

    Args:
        db_url: Atlas-format database URL
            (e.g. ``"sqlite://C:/path/to/db.sqlite"``).
        revisions_url: Optional override for the ``--dir`` URL.
            Useful for parallel test isolation -- pass a copy of
            the revisions directory per worker to avoid directory
            lock contention.
        skip_lock: If ``True``, pass ``--skip-lock`` to Atlas.
            Use only in test fixtures where each worker has an
            isolated revisions copy.  Defaults to ``False`` so
            production multi-process deployments are protected
            by Atlas's directory lock.

    Returns:
        A ``MigrateResult`` with the number of applied migrations
        and the current schema version.

    Raises:
        MigrationError: If the migration fails or Atlas is unavailable.
    """
    logger.info(PERSISTENCE_MIGRATION_STARTED, db_url=_redact_url(db_url))

    stdout, _ = await _run_atlas(
        "migrate",
        "apply",
        "--format",
        "{{ json .Applied }}",
        db_url=db_url,
        revisions_url=revisions_url,
        skip_lock=skip_lock,
    )

    applied_count = 0
    current_version = ""
    try:
        applied = json.loads(stdout) if stdout.strip() else []
        if isinstance(applied, list):
            applied_count = len(applied)
            if applied:
                last = applied[-1]
                current_version = (
                    last.get("Version", "") if isinstance(last, dict) else ""
                )
    except json.JSONDecodeError as exc:
        msg = f"Atlas returned non-JSON output: {stdout[:200]}"
        logger.exception(
            PERSISTENCE_MIGRATION_FAILED,
            note="Atlas returned non-JSON output",
            output_sample=stdout[:200],
        )
        raise MigrationError(msg) from exc

    logger.info(
        PERSISTENCE_MIGRATION_COMPLETED,
        applied_count=applied_count,
        current_version=current_version,
    )

    return MigrateResult(
        applied_count=applied_count,
        current_version=current_version,
        output=stdout,
    )


async def migrate_status(db_url: str) -> MigrateStatus:
    """Check the migration status of a database.

    Invokes ``atlas migrate status`` to report applied and pending
    migrations.

    Args:
        db_url: Atlas-format database URL.

    Returns:
        A ``MigrateStatus`` with current version and pending count.

    Raises:
        MigrationError: If the status check fails.
    """
    stdout, _ = await _run_atlas(
        "migrate",
        "status",
        "--format",
        "{{ json . }}",
        db_url=db_url,
    )

    current_version = ""
    pending_count = 0
    try:
        data = json.loads(stdout) if stdout.strip() else {}
        if isinstance(data, dict):
            current_version = data.get("Current", "")
            pending = data.get("Pending", [])
            pending_count = len(pending) if isinstance(pending, list) else 0
    except json.JSONDecodeError as exc:
        msg = f"Atlas status returned non-JSON output: {stdout[:200]}"
        logger.exception(
            PERSISTENCE_MIGRATION_FAILED,
            note="Atlas status returned non-JSON output",
            output_sample=stdout[:200],
        )
        raise MigrationError(msg) from exc

    return MigrateStatus(
        current_version=current_version,
        pending_count=pending_count,
        output=stdout,
    )


async def migrate_apply_baseline(db_url: str, version: str) -> None:
    """Mark a database as already at a specific migration version.

    Used for existing databases that already have the schema but no
    Atlas revision history.  This records the baseline version in
    ``atlas_schema_revisions`` without executing any SQL.

    Args:
        db_url: Atlas-format database URL.
        version: Migration version to mark as applied
            (e.g. ``"20260409170223"``).

    Raises:
        MigrationError: If the baseline marking fails.
    """
    logger.info(
        PERSISTENCE_MIGRATION_STARTED,
        db_url=_redact_url(db_url),
        baseline=version,
    )

    await _run_atlas(
        "migrate",
        "apply",
        "--baseline",
        version,
        db_url=db_url,
    )

    logger.info(
        PERSISTENCE_MIGRATION_COMPLETED,
        baseline=version,
    )


async def migrate_rollback(db_url: str, *, version: str) -> None:
    """Roll back the database to a specific migration version.

    Invokes ``atlas migrate down`` to revert migrations applied
    after *version*.

    Args:
        db_url: Atlas-format database URL.
        version: Target version to roll back to.

    Raises:
        MigrationError: If the rollback fails.
    """
    logger.info(
        PERSISTENCE_MIGRATION_STARTED,
        db_url=_redact_url(db_url),
        rollback_target=version,
    )

    await _run_atlas(
        "migrate",
        "down",
        "--to-version",
        version,
        db_url=db_url,
    )

    logger.info(
        PERSISTENCE_MIGRATION_COMPLETED,
        rollback_target=version,
    )
