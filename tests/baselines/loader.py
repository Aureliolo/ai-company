"""Shared baseline loader for ``tests/baselines/unit_timing.json``.

Two callers parse this file:

- ``scripts/run_affected_tests.py`` (pre-push affected-tests runner)
- ``tests/conftest.py::pytest_sessionfinish`` (regression banner)

Centralising the validation here keeps both in lock-step: a baseline
that loads in one context loads identically in the other, and the
two cannot drift to different defaults / coercion rules.

The loader is deliberately strict: missing or non-positive
``test_count``, missing ``per_test_ms`` *and* ``unit_suite_seconds``,
non-finite or non-positive numeric fields all return ``None`` so the
caller skips the regression check rather than tripping on a
half-validated snapshot.
"""

import json
import math
from dataclasses import dataclass
from pathlib import Path

# Default ratio applied when the baseline JSON omits
# ``regression_threshold_ratio``.  1.3 = the per-test cost may grow by
# 30% before the rail trips.
_DEFAULT_THRESHOLD_RATIO: float = 1.3


@dataclass(frozen=True)
class BaselineSnapshot:
    """Validated numeric view of ``tests/baselines/unit_timing.json``.

    The primary regression metric is ``per_test_ms``.  When present in
    the baseline JSON, it is used directly; when absent, it is computed
    at parse time from ``unit_suite_seconds * 1000 / test_count`` so
    legacy baselines without an explicit ``per_test_ms`` field continue
    to work.

    ``threshold_ratio`` is always set: the loader defaults it to
    :data:`_DEFAULT_THRESHOLD_RATIO` when the JSON omits the field.

    ``baseline_test_count`` is retained for the partial-run guard
    (skip the check when the collected unit count is well below the
    full suite, e.g. the user ran a single test file).  The loader
    rejects baselines that omit ``test_count``, so consumers can use
    this field without a None-check.
    """

    per_test_ms: float
    threshold_ratio: float
    baseline_test_count: int


def positive_finite_float(raw: object) -> float | None:
    """Coerce *raw* to a strictly positive finite float, or ``None``.

    Strict on input shape: bools (``float(True) == 1.0``) are rejected
    explicitly.  ``True`` masquerading as a count would silently
    validate a malformed baseline; the strictness here is the
    difference between "the rail trips on real regressions" and "the
    rail trips on a typo nobody noticed".
    """
    if raw is None:
        return None
    if isinstance(raw, bool):
        # ``bool`` is a subclass of ``int``; ``float(True) == 1.0``
        # would otherwise sneak through.
        return None
    try:
        candidate = float(raw)  # type: ignore[arg-type]
    except TypeError, ValueError:
        return None
    if not math.isfinite(candidate) or candidate <= 0:
        return None
    return candidate


def positive_int(raw: object) -> int | None:
    """Coerce *raw* to a strictly positive int, or ``None``.

    Strict on input shape: bools (``True == 1``), non-integer floats
    (``12.9 -> 12``), and unrelated types are all rejected.  Loose
    coercion would let a baseline like ``"test_count": 12.9`` or
    ``"test_count": true`` parse successfully and silently distort
    the regression-guard math; the strictness here is the difference
    between "the rail trips on real regressions" and "the rail
    trips on a typo nobody noticed".
    """
    if raw is None:
        return None
    if isinstance(raw, bool):
        # ``bool`` is a subclass of ``int`` in Python; reject explicitly
        # so ``True``/``False`` cannot masquerade as a count.
        return None
    if isinstance(raw, int):
        candidate = raw
    elif isinstance(raw, float):
        if not raw.is_integer():
            return None
        candidate = int(raw)
    elif isinstance(raw, str):
        try:
            candidate = int(raw)
        except ValueError:
            return None
    else:
        return None
    return candidate if candidate > 0 else None


def load_baseline_snapshot(path: Path) -> BaselineSnapshot | None:  # noqa: PLR0911
    """Parse and validate the baseline file at *path*.

    Returns ``None`` when the file is missing, malformed, or missing
    required fields.  ``test_count`` is mandatory in every accepted
    baseline (it powers the partial-run guard).  In addition, the
    baseline must supply EITHER ``per_test_ms`` directly OR
    ``unit_suite_seconds`` -- the loader derives ``per_test_ms`` from
    ``unit_suite_seconds * 1000 / test_count`` when only the latter
    is present.  ``regression_threshold_ratio`` defaults to
    :data:`_DEFAULT_THRESHOLD_RATIO` if absent.
    """
    if not path.exists():
        return None
    try:
        baseline = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError, OSError:
        return None
    # ``json.loads`` happily returns a bare list/str/number for any
    # syntactically-valid JSON, so guard the shape before indexing.
    # Otherwise a malformed baseline crashes the caller instead of
    # cleanly disabling the regression check.
    if not isinstance(baseline, dict):
        return None

    test_count = positive_int(baseline.get("test_count"))
    if test_count is None:
        # ``test_count`` is part of the snapshot contract and powers
        # the mechanical-growth gate.  Reject the baseline outright
        # instead of returning a half-populated snapshot that silently
        # disables the count-based check.
        return None

    # ``per_test_ms`` is explicit-or-derive: if the JSON names the
    # field, the value MUST be valid (typo defence).  Only when the
    # key is absent do we derive from ``unit_suite_seconds``.
    # Without this guard, a baseline like
    # ``"per_test_ms": "fast"`` silently falls through to the derive
    # path, masking the typo and using a possibly-stale
    # ``unit_suite_seconds`` for the rail.
    if "per_test_ms" in baseline:
        per_test_ms = positive_finite_float(baseline.get("per_test_ms"))
        if per_test_ms is None:
            return None
    else:
        baseline_secs = positive_finite_float(baseline.get("unit_suite_seconds"))
        if baseline_secs is None:
            return None
        per_test_ms = baseline_secs * 1000.0 / test_count

    if "regression_threshold_ratio" in baseline:
        # Present-but-invalid is a typo we want surfaced, not silently
        # masked by the default.  A baseline that says
        # ``"regression_threshold_ratio": "fast"`` should reject the
        # baseline outright (caller treats ``None`` as "skip the
        # regression check"), not coerce to 1.3 and trip the rail on
        # the next slow run.
        threshold_ratio = positive_finite_float(
            baseline.get("regression_threshold_ratio"),
        )
        if threshold_ratio is None:
            return None
    else:
        threshold_ratio = _DEFAULT_THRESHOLD_RATIO

    return BaselineSnapshot(
        per_test_ms=per_test_ms,
        threshold_ratio=threshold_ratio,
        baseline_test_count=test_count,
    )
