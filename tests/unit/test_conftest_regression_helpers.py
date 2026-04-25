"""Unit tests for the conftest regression helpers.

Covers ``_load_baseline_for_conftest`` and ``_emit_regression_banner``
extracted from ``tests/conftest.py::pytest_sessionfinish``.  The hook
itself is hard to exercise without a real session, but the helpers are
pure functions.
"""

import importlib.util
import json
from pathlib import Path

import pytest

pytestmark = pytest.mark.unit

_TESTS_ROOT = Path(__file__).resolve().parent.parent
_CONFTEST_PATH = _TESTS_ROOT / "conftest.py"


def _load_conftest_module() -> object:
    """Import ``tests/conftest.py`` as a regular module for white-box use.

    Pytest already loads the conftest as part of suite collection, but
    we cannot import it via the normal ``tests.conftest`` path because
    pytest disables direct conftest imports.  ``importlib`` sidesteps
    that restriction so we can call the private helpers from inside a
    unit test.
    """
    spec = importlib.util.spec_from_file_location(
        "_conftest_under_test",
        _CONFTEST_PATH,
    )
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


_MODULE_CACHE: object | None = None


def _module() -> object:
    """Lazy-loaded handle on the conftest module.

    The module is loaded on first call and cached.  Loading it at
    import time (the previous shape) re-executed every top-level
    side effect in ``tests/conftest.py`` -- including its many fixture
    registrations and module-level state -- every time the test file
    was collected, even when no test that needed the conftest module
    actually ran.
    """
    global _MODULE_CACHE  # noqa: PLW0603
    if _MODULE_CACHE is None:
        _MODULE_CACHE = _load_conftest_module()
    return _MODULE_CACHE


def _patch_baseline(
    monkeypatch: pytest.MonkeyPatch,
    baseline_path: Path,
) -> None:
    """Point the conftest's baseline path at *baseline_path*."""
    monkeypatch.setattr(_module(), "_BASELINE_PATH", baseline_path)


def test_load_baseline_returns_full_triple(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A well-formed baseline parses into ``(secs, count, ratio)``."""
    baseline = tmp_path / "unit_timing.json"
    baseline.write_text(
        json.dumps(
            {
                "unit_suite_seconds": 100.0,
                "test_count": 10_000,
                "regression_threshold_ratio": 1.5,
            },
        ),
        encoding="utf-8",
    )
    _patch_baseline(monkeypatch, baseline)
    result = _module()._load_baseline_for_conftest()  # type: ignore[attr-defined]
    assert result is not None
    secs, count, ratio = result
    assert secs == pytest.approx(100.0)
    assert count == 10_000
    assert ratio == pytest.approx(1.5)


def test_load_baseline_defaults_threshold_ratio(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Missing ``regression_threshold_ratio`` defaults to ``1.3``."""
    baseline = tmp_path / "unit_timing.json"
    baseline.write_text(
        json.dumps(
            {
                "unit_suite_seconds": 100.0,
                "test_count": 10_000,
            },
        ),
        encoding="utf-8",
    )
    _patch_baseline(monkeypatch, baseline)
    result = _module()._load_baseline_for_conftest()  # type: ignore[attr-defined]
    assert result is not None
    _, _, ratio = result
    assert ratio == pytest.approx(1.3)


def test_load_baseline_returns_none_when_missing(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A missing baseline file returns ``None`` (skip the check)."""
    _patch_baseline(monkeypatch, tmp_path / "missing.json")
    assert _module()._load_baseline_for_conftest() is None  # type: ignore[attr-defined]


def test_load_baseline_raises_for_malformed_json(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Malformed JSON raises ``BaselineMalformedError`` rather than skipping.

    The previous behaviour silently returned ``None``, which masked
    the very class of typo the regression rail exists to catch.  A
    corrupt baseline must surface so the operator fixes the file
    instead of pushing without the regression check.
    """
    from tests.baselines.loader import BaselineMalformedError

    baseline = tmp_path / "unit_timing.json"
    baseline.write_text("not json", encoding="utf-8")
    _patch_baseline(monkeypatch, baseline)
    with pytest.raises(BaselineMalformedError):
        _module()._load_baseline_for_conftest()  # type: ignore[attr-defined]


def test_load_baseline_raises_when_required_field_missing(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A baseline missing ``unit_suite_seconds`` AND ``per_test_ms`` raises.

    Without either field, the loader has no per-test cost to compare
    against -- silently disabling the rail would let a typo slip
    through unnoticed.
    """
    from tests.baselines.loader import BaselineMalformedError

    baseline = tmp_path / "unit_timing.json"
    baseline.write_text(
        json.dumps({"test_count": 10_000}),
        encoding="utf-8",
    )
    _patch_baseline(monkeypatch, baseline)
    with pytest.raises(BaselineMalformedError):
        _module()._load_baseline_for_conftest()  # type: ignore[attr-defined]


def test_emit_regression_banner_writes_to_stderr(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """The banner contains the headline metric numbers and the footer."""
    _module()._emit_regression_banner(  # type: ignore[attr-defined]
        elapsed=200.0,
        unit_count=10_000,
        baseline_secs=100.0,
        baseline_count=10_000,
        threshold_ratio=1.3,
    )
    captured = capsys.readouterr()
    # No stdout output -- banner goes to stderr only.
    assert captured.out == ""
    err = captured.err
    assert "REGRESSION DETECTED" in err
    # Baseline per-test ms = 100s * 1000 / 10000 = 10.00ms
    assert "10.00ms" in err
    # Current per-test ms = 200s * 1000 / 10000 = 20.00ms
    assert "20.00ms" in err
    # Cap = 10 * 1.3 = 13.00ms
    assert "13.00ms" in err
    # Footer remediation lines must be present.
    assert "Run A/B against origin/main" in err
    assert "Do NOT delete tests" in err
