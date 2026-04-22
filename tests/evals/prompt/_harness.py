"""Shared harness for prompt-surface evaluation suites.

Goals:

- **Deterministic CI**: pin ``temperature=0.0`` and a ``ScriptedProvider``
  so assertions are reproducible across runs.
- **Drift detection**: snapshot the exact system prompt bytes used by
  each production surface so prompt edits fail fast.
- **Grade thresholds**: every suite asserts accuracy >= threshold on
  a labelled example set so prompt regressions do not pass silently.
"""

import hashlib
from collections.abc import Callable
from dataclasses import dataclass


@dataclass(frozen=True)
class LabelledExample:
    """One input + expected-output pair for prompt grading."""

    name: str
    inp: object
    expected: object


@dataclass(frozen=True)
class EvalOutcome:
    """Result of running a prompt surface against a labelled set."""

    total: int
    passed: int
    failures: tuple[str, ...]

    @property
    def accuracy(self) -> float:
        """Fraction of examples where the surface matched expected."""
        if self.total == 0:
            return 1.0
        return self.passed / self.total


def fingerprint_prompt(prompt: str) -> str:
    """Return a short SHA-256 hex digest for a prompt body.

    Suites use this to assert the shipped prompt has not drifted
    silently: a mismatch signals that an edit was made without
    updating the pinned fingerprint + labelled examples.
    """
    return hashlib.sha256(prompt.encode("utf-8")).hexdigest()[:16]


def run_grader(
    examples: tuple[LabelledExample, ...],
    grade: Callable[[object, object], bool],
) -> EvalOutcome:
    """Run ``grade(actual_input, expected)`` across the example set."""
    failures: list[str] = []
    passed = 0
    for ex in examples:
        if grade(ex.inp, ex.expected):
            passed += 1
        else:
            failures.append(ex.name)
    return EvalOutcome(
        total=len(examples),
        passed=passed,
        failures=tuple(failures),
    )


def assert_accuracy_at_least(outcome: EvalOutcome, threshold: float) -> None:
    """Fail the test if ``outcome.accuracy`` is below ``threshold``.

    Also fails fast when ``outcome.total == 0`` (no examples were
    run) so a miswired suite cannot silently report success.
    """
    if outcome.total == 0:
        msg = (
            "prompt eval ran zero labelled examples -- suite may be "
            "miswired (empty example set, import failure, or skipped "
            "branch). Refusing to pass silently."
        )
        raise AssertionError(msg)
    if outcome.accuracy < threshold:
        failed = ", ".join(outcome.failures[:5])
        msg = (
            f"prompt eval accuracy {outcome.accuracy:.2%} "
            f"below threshold {threshold:.2%}; "
            f"{outcome.total - outcome.passed}/{outcome.total} failed. "
            f"First failures: {failed}"
        )
        raise AssertionError(msg)
