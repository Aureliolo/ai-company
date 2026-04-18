"""Pre-push / CI forbidden-literal gate.

Stricter counterpart to ``check_backend_regional_defaults.py``: scans every
tracked Python file under ``src/synthorg/`` for a curated list of
forbidden patterns that have no legitimate use in application code.
Designed for pre-push and GitHub Actions.

Only ``*.py`` files are scanned.  Docs are intentionally NOT scanned --
operator-facing deployment guides legitimately contain ``localhost:<port>``
examples and the occasional ``'en-US'`` / currency-code reference.

Forbidden patterns (all outside tests/, CLI Go code, and explicit allowlists):

* Identifier suffix ``_usd``
* Bare ISO 4217 currency literal in any curated code -- ``'USD'``,
  ``'EUR'``, ``'GBP'``, ``'JPY'``, etc.  Matches are gated against
  ``_ISO_4217_CODES`` so unrelated three-letter strings (HTTP methods
  like ``'GET'``, role names like ``'CEO'``, license ids) never trip
  the gate.
* Bare BCP 47 language-region tag -- ``'en-US'``, ``'de-DE'``,
  ``'fr-FR'``, etc.
* ``localhost:<port>`` references in application code

Exits non-zero with a structured list on violations.

Usage:
    python scripts/check_forbidden_literals.py
    python scripts/check_forbidden_literals.py --paths src/synthorg

Security:
    ``--paths`` arguments are resolved against the project root and
    rejected if they escape it.  This prevents the script from being
    coerced into scanning (and emitting paths for) files outside the
    repository when invoked with an attacker-controlled argv.
"""

import argparse
import re
import sys
from pathlib import Path
from typing import Final

_USD_FIELD_RE: Final[re.Pattern[str]] = re.compile(
    r"\b[A-Za-z_][A-Za-z0-9_]*_usd\b",
)
# Any quoted 3-uppercase-letter token.  Filtered downstream against
# ``_ISO_4217_CODES`` so only genuine currency codes raise.
_BARE_CURRENCY_RE: Final[re.Pattern[str]] = re.compile(
    r"""(?<![A-Z_])['"]([A-Z]{3})['"](?![A-Z_])""",
)
# ISO 4217 allowlist mirrored from ``check_backend_regional_defaults.py``.
# Kept deliberately in sync: both scripts decide "is this string a
# currency code?" the same way.
_ISO_4217_CODES: Final[frozenset[str]] = frozenset(
    {
        "AUD", "BRL", "CAD", "CHF", "CNY", "CZK", "DKK", "EUR",
        "GBP", "HKD", "HUF", "IDR", "ILS", "INR", "JPY", "KRW",
        "MXN", "NOK", "NZD", "PLN", "SEK", "SGD", "THB", "TRY",
        "TWD", "USD", "VND", "ZAR", "BIF", "CLP", "DJF", "GNF",
        "ISK", "KMF", "MGA", "PYG", "RWF", "UGX", "VUV", "XAF",
        "XOF", "XPF", "BHD", "IQD", "JOD", "KWD", "LYD", "OMR",
        "TND",
    }
)  # fmt: skip
# BCP 47 language-region tag: two lowercase letters, a dash, two or
# three uppercase letters.  Filtering here is intentionally liberal --
# if a test string happens to collide with a BCP 47 shape, move it
# into a test file (already excluded) or wrap it in the suppression
# marker.
_BARE_LOCALE_RE: Final[re.Pattern[str]] = re.compile(
    r"""['"][a-z]{2}-[A-Z]{2,3}['"]""",
)
_LOCALHOST_PORT_RE: Final[re.Pattern[str]] = re.compile(
    r"(?:localhost|127\.0\.0\.1):\d+",
)

# Paths whose explicit purpose is to enumerate or demo these literals.
_ALLOWLIST: Final[frozenset[str]] = frozenset(
    {
        "src/synthorg/budget/currency.py",
        "src/synthorg/budget/config.py",
        "src/synthorg/core/types.py",
        "src/synthorg/settings/definitions/budget.py",
        "src/synthorg/settings/definitions/display.py",
        "src/synthorg/api/config.py",
        "src/synthorg/communication/config.py",
        "src/synthorg/persistence/config.py",
        "src/synthorg/providers/presets.py",
        "src/synthorg/providers/discovery.py",
        "src/synthorg/settings/definitions/api.py",
        "src/synthorg/workers/__main__.py",
        "src/synthorg/memory/embedding/fine_tune_runner.py",
        "scripts/check_backend_regional_defaults.py",
        "scripts/check_forbidden_literals.py",
        "scripts/check_web_design_system.py",
        "scripts/_web_design_patterns.py",
    }
)

_SUPPRESSION_MARKER: Final[str] = "lint-allow: regional-defaults"


def _scan_file(file_path: Path, rel: str) -> list[str]:
    """Return violation messages for a single file.

    Read errors (permissions, corrupt encoding) are reported as
    ``<rel>:0: unable to scan file: <cause>`` instead of being swallowed.
    A pre-push gate that fails open on unreadable files would silently
    disable enforcement -- we prefer to surface the failure.
    """
    try:
        text = file_path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as exc:
        return [f"{rel}:0: unable to scan file: {exc}"]
    issues: list[str] = []
    for idx, line in enumerate(text.splitlines(), start=1):
        if _SUPPRESSION_MARKER in line:
            continue
        stripped = line.lstrip()
        # Ignore pure-comment lines -- they discuss forbidden literals.
        if stripped.startswith(("#", "//")):
            continue
        issues.extend(
            f"{rel}:{idx}: identifier {match.group(0)!r} ends in '_usd'"
            for match in _USD_FIELD_RE.finditer(line)
        )
        for match in _BARE_CURRENCY_RE.finditer(line):
            code = match.group(1)
            if code in _ISO_4217_CODES:
                issues.append(
                    f"{rel}:{idx}: hardcoded ISO 4217 code {code!r} in application code"
                )
        if _BARE_LOCALE_RE.search(line):
            issues.append(f"{rel}:{idx}: hardcoded BCP 47 locale literal")
        if _LOCALHOST_PORT_RE.search(line):
            issues.append(
                f"{rel}:{idx}: hardcoded localhost:<port> in application code"
            )
    return issues


def _resolve_root(root: Path, project_root: Path) -> Path | None:
    """Resolve *root* to an absolute path anchored under *project_root*.

    Returns ``None`` if the resolved path is outside the project root --
    the caller should treat that as a fatal argv error rather than a
    silent skip.  This is the path-traversal guard: a ``--paths ../..``
    argument is a configuration mistake, not a valid scan target.
    """
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


def _iter_targets(roots: list[Path], project_root: Path) -> list[tuple[Path, str]]:
    """Yield ``(absolute_path, posix_relative_path)`` for every file to scan.

    Only Python source files are scanned.  Markdown docs are deliberately
    excluded (see module docstring): they host legitimate examples of the
    very literals this gate forbids in application code.
    """
    targets: list[tuple[Path, str]] = []
    for root in roots:
        abs_root = _resolve_root(root, project_root)
        if abs_root is None or not abs_root.exists():
            continue
        for path in abs_root.rglob("*.py"):
            rel = path.relative_to(project_root).as_posix()
            if rel in _ALLOWLIST:
                continue
            if rel.startswith("tests/") or "/tests/" in rel:
                continue
            if rel.startswith("cli/"):
                continue
            targets.append((path, rel))
    return targets


def main() -> int:
    """CLI entry point."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--paths",
        nargs="+",
        default=["src/synthorg"],
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
            f"\n{total} forbidden literal(s) found. "
            "Fix them or add a '# lint-allow: regional-defaults' marker "
            "if the value is legitimately demonstrative.",
            file=sys.stderr,
        )
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
