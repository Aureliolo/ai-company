"""Smoke tests to verify project setup."""

import re

import pytest


@pytest.mark.unit
def test_package_importable() -> None:
    """Verify the ai_company package can be imported."""
    import ai_company

    assert hasattr(ai_company, "__version__")


@pytest.mark.unit
def test_version_format() -> None:
    """Verify version string follows semver format."""
    from ai_company import __version__

    pattern = r"^\d+\.\d+\.\d+([a-zA-Z0-9.+-]+)?$"
    assert re.match(pattern, __version__), f"Version {__version__!r} is not semver"


@pytest.mark.unit
def test_markers_registered(pytestconfig: pytest.Config) -> None:
    """Verify custom markers are registered (strict-markers won't fail)."""
    raw_markers: list[str] = pytestconfig.getini("markers")  # type: ignore[assignment]
    marker_names = {m.split(":")[0].strip() for m in raw_markers}
    expected = {"unit", "integration", "e2e", "slow"}
    missing = expected - marker_names
    assert expected.issubset(marker_names), f"Missing markers: {missing}"
