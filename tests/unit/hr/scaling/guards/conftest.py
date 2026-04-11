"""Re-export shared fixtures for guard tests."""

from tests.unit.hr.scaling.conftest import (
    NOW,
    make_context,
    make_decision,
    make_signal,
)

__all__ = ["NOW", "make_context", "make_decision", "make_signal"]
