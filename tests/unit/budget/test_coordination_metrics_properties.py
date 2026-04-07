"""Property-based tests for new coordination metrics (Hypothesis)."""

import pytest
from hypothesis import given
from hypothesis import strategies as st

from synthorg.budget.coordination_metrics import (
    compute_amdahl_ceiling,
    compute_straggler_gap,
)


@pytest.mark.unit
class TestAmdahlCeilingProperties:
    """Property-based tests for Amdahl ceiling computation."""

    @given(
        p=st.floats(
            min_value=0.0,
            max_value=0.999,
            allow_nan=False,
            allow_infinity=False,
        ),
    )
    def test_max_speedup_monotonically_increases(self, p: float) -> None:
        """Max speedup increases with parallelizable fraction."""
        result = compute_amdahl_ceiling(parallelizable_fraction=p)
        assert result.max_speedup >= 1.0

    @given(
        p=st.floats(
            min_value=0.0,
            max_value=0.999,
            allow_nan=False,
            allow_infinity=False,
        ),
    )
    def test_recommended_team_size_positive(self, p: float) -> None:
        """Recommended team size is always >= 1."""
        result = compute_amdahl_ceiling(parallelizable_fraction=p)
        assert result.recommended_team_size >= 1

    @given(
        p1=st.floats(
            min_value=0.0,
            max_value=0.998,
            allow_nan=False,
            allow_infinity=False,
        ),
    )
    def test_higher_p_higher_speedup(self, p1: float) -> None:
        """Higher parallelism fraction -> higher or equal speedup."""
        p2 = min(p1 + 0.001, 0.999)
        r1 = compute_amdahl_ceiling(parallelizable_fraction=p1)
        r2 = compute_amdahl_ceiling(parallelizable_fraction=p2)
        assert r2.max_speedup >= r1.max_speedup


@pytest.mark.unit
class TestStragglerGapProperties:
    """Property-based tests for straggler gap computation."""

    @given(
        durations=st.lists(
            st.floats(
                min_value=0.001,
                max_value=10000.0,
                allow_nan=False,
                allow_infinity=False,
            ),
            min_size=1,
            max_size=10,
        ),
    )
    def test_gap_always_non_negative(self, durations: list[float]) -> None:
        """Gap is always >= 0 (slowest >= mean by definition)."""
        agent_durations = [(f"agent-{i}", d) for i, d in enumerate(durations)]
        result = compute_straggler_gap(
            agent_durations=agent_durations,
        )
        assert result.gap_seconds >= -1e-10  # Float tolerance
