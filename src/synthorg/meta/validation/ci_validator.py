"""Local CI validator for code modification proposals.

Runs ruff check, mypy, and pytest against changed files using
subprocess calls. Short-circuits on first failure to avoid
wasting time on later steps.
"""

import asyncio
import time
from pathlib import Path

from synthorg.meta.models import CIValidationResult
from synthorg.observability import get_logger
from synthorg.observability.events.meta import (
    META_CI_VALIDATION_FAILED,
    META_CI_VALIDATION_PASSED,
    META_CI_VALIDATION_STARTED,
)

logger = get_logger(__name__)

_MAX_ERROR_OUTPUT_LENGTH = 2000


class LocalCIValidator:
    """Runs local CI checks (ruff, mypy, pytest) against changed files.

    Each step runs as an async subprocess. Steps short-circuit on
    failure: if lint fails, type-check and tests are skipped.

    Args:
        timeout_seconds: Maximum wall-clock time for each subprocess.
    """

    def __init__(self, *, timeout_seconds: int = 300) -> None:
        self._timeout = timeout_seconds

    async def validate(
        self,
        *,
        project_root: Path,
        changed_files: tuple[str, ...],
    ) -> CIValidationResult:
        """Run lint, type-check, and tests against changed files.

        Args:
            project_root: Absolute path to the project root.
            changed_files: Relative paths of files that changed.

        Returns:
            CI validation result with per-step outcomes.
        """
        logger.info(
            META_CI_VALIDATION_STARTED,
            file_count=len(changed_files),
        )
        start = time.monotonic()
        errors: list[str] = []

        # Step 1: Lint.
        lint_ok = await self._run_lint(project_root, changed_files, errors)

        # Step 2: Type-check (skip if lint failed).
        typecheck_ok = False
        if lint_ok:
            typecheck_ok = await self._run_typecheck(
                project_root,
                changed_files,
                errors,
            )

        # Step 3: Tests (skip if earlier steps failed).
        tests_ok = False
        if lint_ok and typecheck_ok:
            tests_ok = await self._run_tests(
                project_root,
                changed_files,
                errors,
            )

        elapsed = time.monotonic() - start
        passed = lint_ok and typecheck_ok and tests_ok

        if passed:
            logger.info(
                META_CI_VALIDATION_PASSED,
                duration_seconds=round(elapsed, 2),
            )
        else:
            logger.warning(
                META_CI_VALIDATION_FAILED,
                duration_seconds=round(elapsed, 2),
                error_count=len(errors),
            )

        return CIValidationResult(
            passed=passed,
            lint_passed=lint_ok,
            typecheck_passed=typecheck_ok,
            tests_passed=tests_ok,
            errors=tuple(errors),
            duration_seconds=elapsed,
        )

    async def _run_lint(
        self,
        project_root: Path,
        changed_files: tuple[str, ...],
        errors: list[str],
    ) -> bool:
        """Run ruff check on changed files."""
        cmd = ["uv", "run", "ruff", "check", *changed_files]
        return await self._run_subprocess(
            cmd,
            project_root,
            "lint",
            errors,
        )

    async def _run_typecheck(
        self,
        project_root: Path,
        changed_files: tuple[str, ...],
        errors: list[str],
    ) -> bool:
        """Run mypy on changed files."""
        cmd = ["uv", "run", "mypy", *changed_files]
        return await self._run_subprocess(
            cmd,
            project_root,
            "typecheck",
            errors,
        )

    async def _run_tests(
        self,
        project_root: Path,
        changed_files: tuple[str, ...],
        errors: list[str],
    ) -> bool:
        """Run pytest on test files related to changed source files."""
        # Discover test files: for each src file, look for a
        # corresponding test file in the tests/ directory.
        test_files = _discover_test_files(project_root, changed_files)
        if not test_files:
            # No test files to run -- pass by default.
            return True
        cmd = [
            "uv",
            "run",
            "python",
            "-m",
            "pytest",
            *test_files,
            "-m",
            "unit",
            "-x",
            "-q",
        ]
        return await self._run_subprocess(
            cmd,
            project_root,
            "tests",
            errors,
        )

    async def _run_subprocess(
        self,
        cmd: list[str],
        cwd: Path,
        step_name: str,
        errors: list[str],
    ) -> bool:
        """Run a subprocess and capture failure output.

        Args:
            cmd: Command and arguments.
            cwd: Working directory.
            step_name: Human-readable step name for error messages.
            errors: Mutable list to append error descriptions to.

        Returns:
            True if the subprocess exited with code 0.
        """
        proc: asyncio.subprocess.Process | None = None
        try:
            proc = await asyncio.create_subprocess_exec(
                *cmd,
                cwd=cwd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await asyncio.wait_for(
                proc.communicate(),
                timeout=self._timeout,
            )
            if proc.returncode != 0:
                output = (
                    stdout.decode(errors="replace") + stderr.decode(errors="replace")
                ).strip()
                if len(output) > _MAX_ERROR_OUTPUT_LENGTH:
                    output = output[:_MAX_ERROR_OUTPUT_LENGTH] + "... (truncated)"
                errors.append(f"{step_name}: {output}")
                return False
            return True  # noqa: TRY300
        except TimeoutError:
            if proc is not None:
                proc.kill()
                await proc.wait()
            errors.append(
                f"{step_name}: timed out after {self._timeout}s",
            )
            return False
        except asyncio.CancelledError:
            if proc is not None:
                proc.kill()
                await proc.wait()
            raise
        except FileNotFoundError:
            errors.append(
                f"{step_name}: command not found: {cmd[0]}",
            )
            return False


def _discover_test_files(
    project_root: Path,
    changed_files: tuple[str, ...],
) -> list[str]:
    """Map changed source files to their test file paths.

    For each ``src/synthorg/meta/foo/bar.py``, looks for
    ``tests/unit/meta/test_bar.py`` or
    ``tests/unit/meta/foo/test_bar.py``.

    Args:
        project_root: Absolute path to the project root.
        changed_files: Relative paths of changed source files.

    Returns:
        List of test file paths that exist on disk.
    """
    test_files: list[str] = []
    seen: set[str] = set()
    for src in changed_files:
        parts = Path(src).parts
        if not parts or not parts[-1].endswith(".py"):
            continue
        stem = parts[-1]
        test_name = f"test_{stem}"
        # Try direct mapping under tests/unit/meta/.
        candidates = [
            str(Path("tests/unit/meta") / test_name),
        ]
        # Also try preserving subdirectory structure.
        if len(parts) > 4:  # noqa: PLR2004
            # e.g. src/synthorg/meta/strategies/foo.py
            # -> tests/unit/meta/strategies/test_foo.py
            sub = Path(*parts[3:-1])
            candidates.append(
                str(Path("tests/unit/meta") / sub / test_name),
            )
        for candidate in candidates:
            if candidate not in seen:
                full = project_root / candidate
                if full.exists():
                    test_files.append(candidate)
                    seen.add(candidate)
    return test_files
