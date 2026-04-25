"""Unit tests for the regression guard in ``scripts/run_affected_tests.py``.

Covers ``_check_timing_regression`` and its helpers
(``_load_baseline_snapshot``, ``_check_per_test_regression``,
``_check_env_cap``).  Loads the script as a module so the private
helpers are callable.
"""

import importlib.util
import json
from pathlib import Path

import pytest

pytestmark = pytest.mark.unit

_REPO_ROOT = Path(__file__).resolve().parent.parent.parent.parent
_SCRIPT_PATH = _REPO_ROOT / "scripts" / "run_affected_tests.py"


def _load_script_module() -> object:
    """Import the script as a module so private helpers are callable."""
    spec = importlib.util.spec_from_file_location(
        "_run_affected_tests",
        _SCRIPT_PATH,
    )
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


_MODULE = _load_script_module()


def _write_baseline(
    tmp_path: Path,
    *,
    unit_suite_seconds: float = 100.0,
    test_count: int = 10_000,
    per_test_ms: float | None = None,
    regression_threshold_ratio: float | None = None,
) -> Path:
    """Write a baseline JSON file under *tmp_path* and return its path."""
    payload: dict[str, object] = {
        "unit_suite_seconds": unit_suite_seconds,
        "test_count": test_count,
    }
    if per_test_ms is not None:
        payload["per_test_ms"] = per_test_ms
    if regression_threshold_ratio is not None:
        payload["regression_threshold_ratio"] = regression_threshold_ratio
    baseline_path = tmp_path / "unit_timing.json"
    baseline_path.write_text(json.dumps(payload), encoding="utf-8")
    return baseline_path


def _patch_baseline(
    monkeypatch: pytest.MonkeyPatch,
    baseline_path: Path,
) -> None:
    """Point the script's baseline path at *baseline_path*."""
    monkeypatch.setattr(_MODULE, "_BASELINE_PATH", baseline_path)


# ── per-test rail ────────────────────────────────────────────────


def test_per_test_regression_fires_at_1_5x_growth(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Per-test cost grew 1.5x while count stayed flat: guard fires."""
    # Baseline: 100s / 10000 tests = 10ms per test
    _patch_baseline(
        monkeypatch,
        _write_baseline(
            tmp_path,
            unit_suite_seconds=100.0,
            test_count=10_000,
            regression_threshold_ratio=1.3,
        ),
    )
    # Current: 150s / 10000 tests = 15ms per test (1.5x baseline -> trips 1.3x)
    assert _MODULE._check_timing_regression(  # type: ignore[attr-defined]
        elapsed=150.0,
        run_all=True,
        test_count=10_000,
    )


def test_per_test_regression_does_not_fire_at_20pct_count_growth(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test count grew 20%; per-test cost flat. Guard does NOT fire."""
    # Baseline: 100s / 10000 tests = 10ms per test
    _patch_baseline(
        monkeypatch,
        _write_baseline(
            tmp_path,
            unit_suite_seconds=100.0,
            test_count=10_000,
            regression_threshold_ratio=1.3,
        ),
    )
    # Current: 120s / 12000 tests = 10ms per test (no per-test regression)
    assert not _MODULE._check_timing_regression(  # type: ignore[attr-defined]
        elapsed=120.0,
        run_all=True,
        test_count=12_000,
    )


def test_per_test_regression_does_not_fire_at_baseline(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Replaying baseline values exactly does not fire the guard."""
    _patch_baseline(
        monkeypatch,
        _write_baseline(
            tmp_path,
            unit_suite_seconds=100.0,
            test_count=10_000,
        ),
    )
    assert not _MODULE._check_timing_regression(  # type: ignore[attr-defined]
        elapsed=100.0,
        run_all=True,
        test_count=10_000,
    )


def test_per_test_regression_uses_explicit_per_test_ms(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """When ``per_test_ms`` is given directly, it overrides derived value."""
    # Explicit per_test_ms = 5ms (much faster than 100s/10000=10ms derived)
    _patch_baseline(
        monkeypatch,
        _write_baseline(
            tmp_path,
            unit_suite_seconds=100.0,
            test_count=10_000,
            per_test_ms=5.0,
            regression_threshold_ratio=1.3,
        ),
    )
    # Current: 80s / 10000 = 8ms.  Against derived (10ms) baseline this
    # would NOT trip; against explicit 5ms it WOULD (8 > 5*1.3=6.5).
    assert _MODULE._check_timing_regression(  # type: ignore[attr-defined]
        elapsed=80.0,
        run_all=True,
        test_count=10_000,
    )


def test_per_test_regression_skips_when_test_count_unknown(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Without a runtime test count, per-test rail abstains (env cap still fires)."""
    _patch_baseline(monkeypatch, _write_baseline(tmp_path))
    assert not _MODULE._check_timing_regression(  # type: ignore[attr-defined]
        elapsed=999.0,
        run_all=True,
        test_count=None,
    )


# ── env cap ──────────────────────────────────────────────────────


def test_env_cap_overrides_baseline(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """``UNIT_SUITE_MAX_SECONDS`` fires when elapsed exceeds it."""
    _patch_baseline(monkeypatch, _write_baseline(tmp_path))
    monkeypatch.setenv("UNIT_SUITE_MAX_SECONDS", "10")
    assert _MODULE._check_timing_regression(  # type: ignore[attr-defined]
        elapsed=15.0,
        run_all=True,
        test_count=10_000,
    )


def test_env_cap_does_not_fire_below_threshold(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Env cap above elapsed leaves per-test rail in charge."""
    _patch_baseline(monkeypatch, _write_baseline(tmp_path))
    monkeypatch.setenv("UNIT_SUITE_MAX_SECONDS", "1000")
    assert not _MODULE._check_timing_regression(  # type: ignore[attr-defined]
        elapsed=100.0,
        run_all=True,
        test_count=10_000,
    )


# ── orchestrator guards ──────────────────────────────────────────


def test_skips_when_run_all_is_false(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Affected-only runs do not compare against the baseline."""
    _patch_baseline(monkeypatch, _write_baseline(tmp_path))
    assert not _MODULE._check_timing_regression(  # type: ignore[attr-defined]
        elapsed=10_000.0,
        run_all=False,
        test_count=100,
    )


def test_skips_when_baseline_missing(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Missing baseline disables the guard cleanly."""
    monkeypatch.setattr(_MODULE, "_BASELINE_PATH", tmp_path / "missing.json")
    assert not _MODULE._check_timing_regression(  # type: ignore[attr-defined]
        elapsed=10_000.0,
        run_all=True,
        test_count=10_000,
    )


def test_raises_when_baseline_is_malformed_json(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Malformed JSON surfaces a ``BaselineMalformedError`` loudly.

    The previous behaviour silently disabled the guard on a typo, which
    defeated the very class of error the rail exists to catch.  A
    corrupt baseline must surface so the operator fixes the file
    instead of pushing without the regression check.
    """
    from tests.baselines.loader import BaselineMalformedError

    bad = tmp_path / "unit_timing.json"
    bad.write_text("not json", encoding="utf-8")
    _patch_baseline(monkeypatch, bad)
    with pytest.raises(BaselineMalformedError):
        _MODULE._check_timing_regression(  # type: ignore[attr-defined]
            elapsed=10_000.0,
            run_all=True,
            test_count=10_000,
        )


def test_raises_when_baseline_missing_fields(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Baseline missing ``test_count`` raises rather than silently skipping.

    A baseline that exists but is incomplete is a typo signal -- the
    regression guard must fail loud so the operator restores the
    missing field.
    """
    from tests.baselines.loader import BaselineMalformedError

    bad = tmp_path / "unit_timing.json"
    bad.write_text(json.dumps({"unit_suite_seconds": 100.0}), encoding="utf-8")
    _patch_baseline(monkeypatch, bad)
    with pytest.raises(BaselineMalformedError):
        _MODULE._check_timing_regression(  # type: ignore[attr-defined]
            elapsed=200.0,
            run_all=True,
            test_count=10_000,
        )


# ── snapshot loader (positive coverage) ──────────────────────────


def test_load_baseline_snapshot_returns_explicit_per_test_ms(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Snapshot prefers an explicit ``per_test_ms`` over the derived one.

    Regression guard: a JSON field rename that drops ``per_test_ms``
    silently (e.g. typo to ``per_test_milliseconds``) would otherwise
    fall back to the derived value and quietly tighten or loosen the
    rail. This test pins the explicit-field shape.
    """
    _patch_baseline(
        monkeypatch,
        _write_baseline(
            tmp_path,
            unit_suite_seconds=100.0,
            test_count=10_000,
            per_test_ms=4.5,
            regression_threshold_ratio=1.5,
        ),
    )
    snapshot = _MODULE._load_baseline_snapshot()  # type: ignore[attr-defined]
    assert snapshot is not None
    assert snapshot.per_test_ms == pytest.approx(4.5)
    assert snapshot.threshold_ratio == pytest.approx(1.5)
    assert snapshot.baseline_test_count == 10_000


def test_load_baseline_snapshot_derives_per_test_ms_when_absent(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Without ``per_test_ms`` the loader derives it from ``unit_suite_seconds``."""
    _patch_baseline(
        monkeypatch,
        _write_baseline(
            tmp_path,
            unit_suite_seconds=200.0,
            test_count=10_000,
        ),
    )
    snapshot = _MODULE._load_baseline_snapshot()  # type: ignore[attr-defined]
    assert snapshot is not None
    # 200s * 1000 / 10000 = 20.0 ms per test
    assert snapshot.per_test_ms == pytest.approx(20.0)
    # Default threshold ratio when omitted.
    assert snapshot.threshold_ratio == pytest.approx(1.3)
    assert snapshot.baseline_test_count == 10_000
