"""Pre-push / CI persistence-boundary gate.

Enforces the rule: ``src/synthorg/persistence/`` is the only place that
may import ``aiosqlite``, ``sqlite3``, ``psycopg``, or ``psycopg_pool``,
or emit raw SQL DDL/DML keywords in string literals.  Every durable
feature must go through a repository Protocol in ``persistence/``.

Sanctioned exceptions (agent tools that legitimately need raw DB
introspection) are listed in ``_ALLOWLIST`` below.  To opt out on a
single line, add ``# lint-allow: persistence-boundary -- <reason>``
as a trailing comment on that line.  The justification after ``--`` is
required and must be non-empty.

Exits non-zero with a structured list on violations.

Usage:
    python scripts/check_persistence_boundary.py
    python scripts/check_persistence_boundary.py --paths src/synthorg
"""

import argparse
import io
import os
import re
import subprocess
import sys
import tokenize
from pathlib import Path
from typing import Final

# ── Patterns ────────────────────────────────────────────────────

# Driver imports: forbidden outside the persistence/ boundary.
_DRIVER_IMPORT_RE: Final[re.Pattern[str]] = re.compile(
    r"""(?:
        ^\s*import\s+(?P<mod>aiosqlite|sqlite3|psycopg|psycopg_pool)\b
        |
        ^\s*from\s+(?P<frm>aiosqlite|sqlite3|psycopg|psycopg_pool)[\.\s]
        |
        ^\s*from\s+(?P<frm2>aiosqlite|sqlite3|psycopg|psycopg_pool)\b
    )""",
    re.VERBOSE,
)

# Raw SQL DDL/DML keywords inside a string literal.  The trailing
# whitespace guard keeps "CREATE TABLE" / "INSERT INTO" from matching
# "CREATE_TABLE_PATTERN" or "INSERTION_COUNT".  Heuristic -- a handful
# of false positives are expected and can be silenced with the marker.
_RAW_SQL_RE: Final[re.Pattern[str]] = re.compile(
    r"""['"]                                   # opening quote
        [^'"]*?                                # any preamble
        \b(?:
            CREATE\s+TABLE
            |INSERT\s+INTO
            |ALTER\s+TABLE
            |DROP\s+TABLE
            |UPDATE\s+\w+\s+SET
            |DELETE\s+FROM
        )\b
        [^'"]*                                 # any trailing SQL
        ['"]""",
    re.VERBOSE | re.IGNORECASE,
)

# Mutation audit log calls inside the persistence boundary.  Captures the
# event constant on the same line as ``logger.info(``/``logger.debug(``/
# ``logger.warning(`` OR on the immediately following line (the latter
# is the canonical multi-line shape used across the codebase).  Repos
# must not log mutations themselves -- the service layer is the audit
# point.  Per-line opt-out via the existing ``# lint-allow: persistence-
# boundary -- <reason>`` marker.
_MUTATION_LOG_RE: Final[re.Pattern[str]] = re.compile(
    r"""logger\.(?:info|debug|warning)\s*\(\s*
        (?:\#[^\n]*\n\s*)?                     # optional inline comment
        (?P<constant>[A-Z][A-Z0-9_]*?_(?:SAVED|CREATED|UPDATED|DELETED|PERSISTED))\b
    """,
    re.VERBOSE | re.MULTILINE | re.DOTALL,
)

# Lifecycle / infrastructure events whose constants happen to end in a
# mutation suffix but are NOT entity-mutation audits (the rule targets
# entity audit, not "the backend started" / "TimescaleDB hypertable was
# initialised" lifecycle).  Each entry must carry a justification.
_MUTATION_LOG_ALLOWED_CONSTANTS: Final[frozenset[str]] = frozenset(
    {
        # Backend factory: lifecycle event when the persistence backend
        # itself is constructed; not an entity mutation.
        "PERSISTENCE_BACKEND_CREATED",
        # TimescaleDB hypertable conversion: schema-evolution lifecycle,
        # fired once per migration (not per row mutation).
        "PERSISTENCE_TIMESCALEDB_HYPERTABLE_CREATED",
        # Filesystem artifact storage: blob-store deletion event from
        # the storage abstraction (separate concern from the artifact
        # repository which already has its own audit at the service
        # layer via API_ARTIFACT_DELETED).
        "PERSISTENCE_ARTIFACT_STORAGE_DELETED",
    }
)

# ── Allowlist ───────────────────────────────────────────────────

# Files outside ``persistence/`` that are sanctioned exceptions.
# Only add a file here after a deliberate decision to carry SQL
# outside the repository boundary (e.g. agent tools that introspect
# arbitrary DB schemas at runtime).  Every entry should have a brief
# comment explaining *why* the exception is justified.
_ALLOWLIST: Final[frozenset[str]] = frozenset(
    {
        # Agent-facing DB introspection tool.  Returns table/column
        # metadata from whatever DB the operator configured -- the
        # repository abstraction does not expose this shape by design.
        "src/synthorg/tools/database/schema_inspect.py",
        # Agent-facing arbitrary-SQL tool.  Operator-gated; runs
        # user-supplied SELECTs against the configured DB.  Cannot
        # ride the repository pattern because SQL strings are the
        # payload.
        "src/synthorg/tools/database/sql_query.py",
        # Destructive-operation detector scans user-supplied SQL for
        # DDL keywords -- the DDL literals are the *payload* of the
        # security check, not SQL emitted by the app.
        "src/synthorg/security/rules/destructive_op_detector.py",
        # The boundary checker itself references driver names in
        # patterns and error messages.
        "scripts/check_persistence_boundary.py",
        # Shared conftest bootstraps the test database via aiosqlite.
        "tests/conftest.py",
        # Integration / unit tests that legitimately hold driver
        # handles for cross-subsystem fixtures.
        "tests/integration/engine/identity/test_identity_versioning.py",
        "tests/integration/engine/workflow/test_subworkflows_e2e.py",
        "tests/integration/hr/training/test_training_persistence.py",
        "tests/unit/hr/test_persistence.py",
        "tests/unit/memory/embedding/test_fine_tune_orchestrator.py",
        "tests/unit/meta/test_approval_repo.py",
        "tests/unit/ontology/drift/test_store.py",
        "tests/unit/tools/database/test_sql_query.py",
        "tests/unit/tools/database/test_schema_inspect.py",
        # Destructive-op-detector tests feed SQL fragments as test
        # inputs to the detector -- same reason as the detector itself.
        "tests/unit/security/rules/test_destructive_op_detector.py",
        # Boundary-checker self-test: feeds SQL keyword fixtures into
        # the matcher to prove it flags them.  The strings ARE the test
        # input -- adding suppression markers per line would defeat the
        # exact behavior under test.
        "tests/unit/scripts/test_check_persistence_boundary.py",
    }
)

# Any path starting with one of these prefixes is considered inside
# the boundary and not subject to the rule.
_PERSISTENCE_PREFIXES: Final[tuple[str, ...]] = (
    "src/synthorg/persistence/",
    "tests/conformance/persistence/",
    # Per-backend unit tests drive repositories directly and
    # legitimately build aiosqlite / psycopg fixtures.
    "tests/unit/persistence/",
    "tests/integration/persistence/",
    # Auth-store unit tests instantiate repositories with an
    # aiosqlite connection fixture -- same shape as above.
    "tests/unit/api/auth/",
    # Backup handler tests exercise sqlite3 file-level copy/restore.
    "tests/unit/backup/test_handlers/",
)

_SUPPRESSION_MARKER: Final[str] = "lint-allow: persistence-boundary"


def _line_has_trailing_marker(line: str) -> bool:
    """Return True iff *line* carries the marker as a trailing ``#`` comment.

    The marker must be followed by ``--`` and non-empty justification
    text -- ``# lint-allow: persistence-boundary -- legacy fixture``.
    """
    try:
        tokens = list(tokenize.generate_tokens(io.StringIO(line).readline))
    except tokenize.TokenError, IndentationError, SyntaxError:
        return False
    for tok in tokens:
        if tok.type != tokenize.COMMENT:
            continue
        comment = tok.string.lstrip("#").strip()
        if not comment.startswith(_SUPPRESSION_MARKER):
            continue
        # Require "-- <non-empty>" after the marker prefix.
        suffix = comment[len(_SUPPRESSION_MARKER) :].strip()
        if suffix.startswith("--"):
            justification = suffix[2:].strip()
            if justification:
                return True
    return False


def _is_inside_boundary(rel: str) -> bool:
    """Return True iff *rel* lives inside the persistence boundary."""
    return any(rel.startswith(prefix) for prefix in _PERSISTENCE_PREFIXES)


def _scan_file(file_path: Path, rel: str) -> list[str]:
    """Return violation messages for a single file."""
    try:
        text = file_path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as exc:
        return [f"{rel}:0: unable to scan file: {exc}"]
    issues: list[str] = []
    for idx, line in enumerate(text.splitlines(), start=1):
        if _line_has_trailing_marker(line):
            continue
        stripped = line.lstrip()
        if stripped.startswith("#"):
            continue
        # Driver imports -- only match on logical import lines.
        for match in _DRIVER_IMPORT_RE.finditer(line):
            mod = match.group("mod") or match.group("frm") or match.group("frm2")
            if mod:
                issues.append(
                    f"{rel}:{idx}: imports '{mod}' outside the persistence "
                    "boundary; wrap the call in a repository under "
                    "src/synthorg/persistence/ (or add "
                    "'# lint-allow: persistence-boundary -- <reason>' if the "
                    "exception is genuinely sanctioned)."
                )
        # Raw SQL DDL/DML keywords in string literals.
        if _RAW_SQL_RE.search(line):
            issues.append(
                f"{rel}:{idx}: raw SQL DDL/DML keyword in a string literal "
                "outside persistence/; move it into a repository module or "
                "add '# lint-allow: persistence-boundary -- <reason>'."
            )
    return issues


def _scan_persistence_mutation_logs(file_path: Path, rel: str) -> list[str]:
    """Return mutation-log violations for a persistence-boundary file.

    Repos must not log mutations themselves; service-layer events are
    the canonical audit point.  This scanner finds every
    ``logger.info|debug|warning(<EVENT>)`` whose ``EVENT`` constant ends
    in ``_SAVED``/``_CREATED``/``_UPDATED``/``_DELETED``/``_PERSISTED``,
    skipping (a) sanctioned lifecycle constants on
    ``_MUTATION_LOG_ALLOWED_CONSTANTS`` and (b) any line that carries
    the ``# lint-allow: persistence-boundary -- <reason>`` marker.
    """
    try:
        text = file_path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as exc:
        return [f"{rel}:0: unable to scan file: {exc}"]
    issues: list[str] = []
    lines = text.splitlines()
    for match in _MUTATION_LOG_RE.finditer(text):
        constant = match.group("constant")
        if constant in _MUTATION_LOG_ALLOWED_CONSTANTS:
            continue
        # Compute the line where ``logger.<level>(`` starts so the
        # violation message points at the call, not the constant.
        line_no = text.count("\n", 0, match.start()) + 1
        # Allow per-line opt-out on the ``logger.<level>(`` line OR on
        # the constant's line (multi-line calls span both).
        constant_line_no = text.count("\n", 0, match.start("constant")) + 1
        if _line_has_trailing_marker(lines[line_no - 1]) or _line_has_trailing_marker(
            lines[constant_line_no - 1]
        ):
            continue
        issues.append(
            f"{rel}:{line_no}: repo-level mutation audit log "
            f"'{constant}' must move to the service layer "
            "(repositories must not log mutations themselves; see "
            "docs/reference/persistence-boundary.md). Add "
            "'# lint-allow: persistence-boundary -- <reason>' on the "
            "logger call line ONLY when the event is a non-entity "
            "lifecycle/infrastructure signal."
        )
    return issues


def _resolve_root(root: Path, project_root: Path) -> Path | None:
    """Resolve *root* to an absolute path strictly under *project_root*.

    Uses :func:`os.path.commonpath` (rather than :meth:`Path.relative_to`)
    as the containment check so CodeQL's path-injection data-flow
    analysis recognises the sanitizer.
    """
    candidate = root if root.is_absolute() else project_root / root
    try:
        resolved = candidate.resolve(strict=False)
    except OSError:
        return None
    project_root_str = os.fspath(project_root.resolve(strict=False))
    resolved_str = os.fspath(resolved)
    try:
        common = os.path.commonpath([project_root_str, resolved_str])
    except ValueError:
        return None
    if common != project_root_str:
        return None
    return resolved


def _git_tracked_python_files(
    abs_root: Path,
    project_root: Path,
) -> list[tuple[Path, str]]:
    """Return every tracked ``*.py`` file under *abs_root* as ``(abs, rel)``."""
    rel_root = abs_root.relative_to(project_root).as_posix() or "."
    try:
        result = subprocess.run(
            ["git", "ls-files", "-z", "--", f"{rel_root}/*.py"],
            check=True,
            capture_output=True,
            cwd=project_root,
        )
    except subprocess.CalledProcessError, FileNotFoundError:
        return [
            (p, p.relative_to(project_root).as_posix()) for p in abs_root.rglob("*.py")
        ]
    out = result.stdout.decode("utf-8", errors="replace")
    paths = [p for p in out.split("\0") if p]
    return [((project_root / rel_path), rel_path) for rel_path in paths]


def _iter_targets(
    roots: list[Path],
    project_root: Path,
) -> list[tuple[Path, str]]:
    """Yield ``(absolute_path, posix_relative_path)`` for every file to scan.

    Files inside the persistence boundary and on the allowlist are
    excluded up front -- they are never violations.
    """
    targets: list[tuple[Path, str]] = []
    for root in roots:
        abs_root = _resolve_root(root, project_root)
        if abs_root is None or not abs_root.exists():
            continue
        for path, rel in _git_tracked_python_files(abs_root, project_root):
            if _is_inside_boundary(rel):
                continue
            if rel in _ALLOWLIST:
                continue
            # Tests other than persistence conformance fall under the
            # rule so a stray driver import in a unit test still trips
            # the gate.  Explicit exceptions belong in _ALLOWLIST.
            targets.append((path, rel))
    return targets


_PERSISTENCE_SRC_PREFIX: Final[str] = "src/synthorg/persistence/"


def _iter_persistence_targets(
    roots: list[Path],
    project_root: Path,
) -> list[tuple[Path, str]]:
    """Yield ``(absolute_path, posix_relative_path)`` for persistence files.

    The mutation-log gate only ever needs to scan
    ``src/synthorg/persistence/``; user-supplied ``--paths`` are used as
    a *coarse opt-in* (skip persistence scanning entirely if no path
    overlaps the persistence tree) but do **not** drive the actual
    enumeration -- that is anchored at a hard-coded prefix under
    ``project_root``.  Avoiding user-input on the final filesystem read
    keeps CodeQL's path-injection analysis happy and prevents the
    persistence sweep from accidentally widening scope when callers
    pass aggressive ``--paths``.

    Tests under ``tests/.../persistence/`` are intentionally excluded
    -- the rule applies to production code; tests that exercise repo
    internals can log whatever they need.
    """
    if not _persistence_in_scope(roots, project_root):
        return []
    persistence_root = project_root / _PERSISTENCE_SRC_PREFIX.rstrip("/")
    if not persistence_root.is_dir():
        return []
    targets: list[tuple[Path, str]] = []
    for path, rel in _git_tracked_python_files(persistence_root, project_root):
        if rel.startswith(_PERSISTENCE_SRC_PREFIX):
            targets.append((path, rel))
    return targets


def _persistence_in_scope(roots: list[Path], project_root: Path) -> bool:
    """Return ``True`` when at least one ``--paths`` entry overlaps persistence.

    Coarse opt-in for the mutation-log sweep -- uses the same
    containment check as :func:`_resolve_root` so the boundary is
    consistent.  The function never returns the user-supplied path
    itself, only a boolean derived from it.
    """
    persistence_prefix = (project_root / _PERSISTENCE_SRC_PREFIX.rstrip("/")).resolve(
        strict=False
    )
    for root in roots:
        resolved = _resolve_root(root, project_root)
        if resolved is None:
            continue
        # Either the user path is inside persistence, or persistence is
        # inside the user path -- both count as "persistence is in
        # scope".  Compare resolved string forms so CodeQL recognises
        # the prefix relationship.
        resolved_str = os.fspath(resolved)
        prefix_str = os.fspath(persistence_prefix)
        if (
            resolved_str == prefix_str
            or resolved_str.startswith(prefix_str + os.sep)
            or prefix_str.startswith(resolved_str + os.sep)
        ):
            return True
    return False


class ProjectRootError(Exception):
    """Raised when ``--repo-root`` cannot be resolved to a usable directory.

    Carries the diagnostic message intended for stderr so :func:`main`
    can format it consistently and exit with a non-zero status.
    """


def _resolve_project_root(repo_root: Path | None) -> Path:
    """Resolve the project root from CLI arguments.

    Args:
        repo_root: User-supplied repo root from ``--repo-root``, or
            ``None`` to fall back to the script's own parent directory.

    Returns:
        A resolved :class:`Path` to the project root.

    Raises:
        ProjectRootError: If ``--repo-root`` is inaccessible (OSError on
            resolve) or does not point at a directory.  The message
            attached to the exception is suitable for printing directly
            to stderr.
    """
    default_root = Path(__file__).resolve().parent.parent
    if repo_root is None:
        return default_root
    try:
        resolved = repo_root.resolve(strict=True)
    except OSError as exc:
        msg = f"--repo-root not accessible: {repo_root} ({exc})"
        raise ProjectRootError(msg) from exc
    if not resolved.is_dir():
        msg = f"--repo-root must be a directory: {resolved}"
        raise ProjectRootError(msg)
    return resolved


def _scan_all(
    roots: list[Path],
    project_root: Path,
) -> int:
    """Run both scanning passes, print issues, return total count."""
    total = 0
    for path, rel in _iter_targets(roots, project_root):
        issues = _scan_file(path, rel)
        for msg in issues:
            print(msg)
        total += len(issues)
    # Mutation-log gate: scan persistence-boundary files for repo-level
    # mutation audit logs.  These violate the service-layer rule
    # (repositories must not log mutations themselves).
    for path, rel in _iter_persistence_targets(roots, project_root):
        issues = _scan_persistence_mutation_logs(path, rel)
        for msg in issues:
            print(msg)
        total += len(issues)
    return total


def main() -> int:
    """CLI entry point."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--paths",
        nargs="+",
        default=["src/synthorg", "tests"],
        help="Roots to scan (relative to repo root).",
    )
    parser.add_argument(
        "--repo-root",
        type=Path,
        default=None,
        help=(
            "Project root to anchor path resolution against.  Defaults to "
            "the ancestor directory of this script; pass "
            "${{ github.workspace }} in CI to remove all ambiguity."
        ),
    )
    args = parser.parse_args()

    try:
        project_root = _resolve_project_root(args.repo_root)
    except ProjectRootError as exc:
        print(str(exc), file=sys.stderr)
        return 2

    roots = [Path(p) for p in args.paths]
    for root in roots:
        if _resolve_root(root, project_root) is None:
            print(
                f"refusing to scan path outside project root: {root}",
                file=sys.stderr,
            )
            return 2

    total = _scan_all(roots, project_root)
    if total:
        print(
            f"\n{total} persistence-boundary violation(s) found.  See "
            "docs/guides/persistence-migrations.md for the repository "
            "pattern and the opt-out marker format.",
            file=sys.stderr,
        )
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
