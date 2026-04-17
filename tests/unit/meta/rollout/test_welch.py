"""Tests for the pure-math Welch's t-test implementation."""

import math

import pytest
from hypothesis import given
from hypothesis import strategies as st
from pydantic import ValidationError

from synthorg.meta.rollout.regression.welch import (
    InsufficientDataError,
    WelchResult,
    ZeroVarianceError,
    welch_t_test,
)

pytestmark = pytest.mark.unit


class TestWelchTStat:
    """Verify the t-statistic and degrees of freedom formulas."""

    def test_shifted_samples_match_closed_form(self) -> None:
        a = (1.0, 2.0, 3.0, 4.0, 5.0)
        b = (5.0, 6.0, 7.0, 8.0, 9.0)
        result = welch_t_test(a, b)
        # mean_a=3, mean_b=7, var_a=var_b=2.5, n_a=n_b=5
        # t = (3 - 7) / sqrt(2.5/5 + 2.5/5) = -4.0 exactly
        # df = (1.0)**2 / (0.25**2/4 + 0.25**2/4) = 1 / 0.03125 = 32? no
        # wait: var/n = 0.5 each, so num = (0.5+0.5)^2 = 1
        # denom = 0.5^2/(n-1) + 0.5^2/(n-1) = 0.25/4 + 0.25/4 = 0.125
        # df = 1 / 0.125 = 8.0
        assert result.t == pytest.approx(-4.0, abs=1e-9)
        assert result.df == pytest.approx(8.0, abs=1e-9)

    def test_identical_samples_produce_zero_t(self) -> None:
        a = (1.0, 2.0, 3.0, 4.0, 5.0)
        b = (1.0, 2.0, 3.0, 4.0, 5.0)
        result = welch_t_test(a, b)
        assert result.t == pytest.approx(0.0, abs=1e-12)
        assert result.p_two_sided == pytest.approx(1.0, abs=1e-9)

    def test_swap_arguments_flips_t_sign(self) -> None:
        a = (1.0, 2.0, 3.0, 4.0, 5.0)
        b = (5.0, 6.0, 7.0, 8.0, 9.0)
        forward = welch_t_test(a, b)
        reverse = welch_t_test(b, a)
        assert forward.t == pytest.approx(-reverse.t, abs=1e-12)
        assert forward.df == pytest.approx(reverse.df, abs=1e-12)
        assert forward.p_two_sided == pytest.approx(
            reverse.p_two_sided,
            abs=1e-12,
        )


class TestWelchPValue:
    """Pin p-values against reference computations."""

    def test_shifted_samples_p_value(self) -> None:
        # t=-4.0, df=8.0 -> scipy.stats.t.sf(4.0, 8)*2 = 0.003948...
        a = (1.0, 2.0, 3.0, 4.0, 5.0)
        b = (5.0, 6.0, 7.0, 8.0, 9.0)
        result = welch_t_test(a, b)
        assert result.p_two_sided == pytest.approx(0.003948, abs=1e-5)

    def test_real_world_unequal_variance_example(self) -> None:
        # Real-world example with n_a=15, n_b=16 and unequal spreads.
        # Expected values computed from the Welch/Satterthwaite formulas
        # using sample variance (Bessel's correction) and the two-sided
        # incomplete-beta p-value:
        #   mean_a = 312.3/15 = 20.82, mean_b = 367.6/16 = 22.975
        #   t = -2.437137, df = 25.402081, p = 0.02213313
        a = (
            27.5,
            21.0,
            19.0,
            23.6,
            17.0,
            17.9,
            16.9,
            20.1,
            21.9,
            22.6,
            23.1,
            19.6,
            19.0,
            21.7,
            21.4,
        )
        b = (
            27.1,
            22.0,
            20.8,
            23.4,
            23.4,
            23.5,
            25.8,
            22.0,
            24.8,
            20.2,
            21.9,
            23.9,
            22.8,
            19.0,
            23.3,
            23.7,
        )
        result = welch_t_test(a, b)
        assert result.t == pytest.approx(-2.437137, abs=1e-5)
        assert result.df == pytest.approx(25.402081, abs=1e-5)
        assert result.p_two_sided == pytest.approx(0.02213313, abs=1e-7)

    def test_p_value_range_is_closed_unit(self) -> None:
        a = (1.0, 2.0, 3.0, 4.0, 5.0, 6.0)
        b = (2.0, 3.0, 4.0, 5.0, 6.0, 7.0)
        result = welch_t_test(a, b)
        assert 0.0 <= result.p_two_sided <= 1.0


class TestErrorCases:
    """Edge cases that must raise, not return garbage."""

    @pytest.mark.parametrize(
        ("left", "right", "expected_exc"),
        [
            ((1.0,), (1.0, 2.0, 3.0), InsufficientDataError),
            ((1.0, 2.0, 3.0), (), InsufficientDataError),
            # Both arms flat: se_sq == 0, test is undefined.
            ((5.0, 5.0, 5.0), (7.0, 7.0, 7.0), ZeroVarianceError),
        ],
    )
    def test_degenerate_inputs_raise(
        self,
        left: tuple[float, ...],
        right: tuple[float, ...],
        expected_exc: type[Exception],
    ) -> None:
        with pytest.raises(expected_exc):
            welch_t_test(left, right)

    @pytest.mark.parametrize(
        ("left", "right"),
        [
            # Only the left arm is constant; Welch can still run via
            # the non-zero variance on the right.
            ((5.0, 5.0, 5.0), (1.0, 2.0, 3.0)),
            # Mirror case: only the right arm is constant.
            ((1.0, 2.0, 3.0), (7.0, 7.0, 7.0)),
        ],
    )
    def test_one_arm_constant_still_runs(
        self,
        left: tuple[float, ...],
        right: tuple[float, ...],
    ) -> None:
        result = welch_t_test(left, right)
        assert 0.0 <= result.p_two_sided <= 1.0


class TestWelchResultModel:
    """The result is a frozen model with the expected shape."""

    def test_result_is_frozen(self) -> None:
        result = WelchResult(t=0.5, df=10.0, p_two_sided=0.6)
        with pytest.raises(ValidationError, match="frozen"):
            result.t = 1.0  # type: ignore[misc]

    def test_result_rejects_nan(self) -> None:
        with pytest.raises(ValidationError, match="finite"):
            WelchResult(t=math.nan, df=10.0, p_two_sided=0.5)

    def test_result_rejects_p_out_of_range(self) -> None:
        with pytest.raises(ValidationError, match="less than or equal"):
            WelchResult(t=0.0, df=10.0, p_two_sided=1.5)


class TestWelchProperties:
    """Hypothesis-based invariants."""

    @given(
        st.lists(
            st.floats(
                min_value=-1e6,
                max_value=1e6,
                allow_nan=False,
                allow_infinity=False,
            ),
            min_size=2,
            max_size=40,
        ),
        st.lists(
            st.floats(
                min_value=-1e6,
                max_value=1e6,
                allow_nan=False,
                allow_infinity=False,
            ),
            min_size=2,
            max_size=40,
        ),
    )
    def test_p_value_always_in_unit_interval(
        self,
        a: list[float],
        b: list[float],
    ) -> None:
        try:
            result = welch_t_test(tuple(a), tuple(b))
        except ZeroVarianceError:
            return
        assert 0.0 <= result.p_two_sided <= 1.0
        assert result.df > 0.0
