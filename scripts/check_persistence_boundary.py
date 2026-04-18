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
        # The boundary checker itself references driver names in
        # patterns and error messages.
        "scripts/check_persistence_boundary.py",
        # Persistence conformance tests exercise repository behaviour
        # against both backends; they touch driver primitives when
        # building fixtures.
    }
)

# Any path starting with one of these prefixes is considered inside
# the boundary and not subject to the rule.
_PERSISTENCE_PREFIXES: Final[tuple[str, ...]] = (
    "src/synthorg/persistence/",
    "tests/conformance/persistence/",
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


def _resolve_root(root: Path, project_root: Path) -> Path | None:
    """Resolve *root* to an absolute path anchored under *project_root*."""
    candidate = root if root.is_absolute() else project_root / root
    try:
        resolved = candidate.resolve(strict=False)
    except OSError:
        return None
    try:
        resolved.relative_to(project_root)
    except ValueError:
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


def main() -> int:
    """CLI entry point."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--paths",
        nargs="+",
        default=["src/synthorg", "tests"],
        help="Roots to scan (relative to repo root).",
    )
    args = parser.parse_args()

    project_root = Path(__file__).resolve().parent.parent
    roots = [Path(p) for p in args.paths]
    for root in roots:
        if _resolve_root(root, project_root) is None:
            print(
                f"refusing to scan path outside project root: {root}",
                file=sys.stderr,
            )
            return 2
    total = 0
    for path, rel in _iter_targets(roots, project_root):
        issues = _scan_file(path, rel)
        for msg in issues:
            print(msg)
        total += len(issues)
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
