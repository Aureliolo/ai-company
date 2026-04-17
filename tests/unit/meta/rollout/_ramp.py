"""Shared deterministic sample generator for rollout tests."""


def ramp(center: float, observations: int, spread: float) -> tuple[float, ...]:
    """Build a deterministic symmetric ramp around ``center``.

    Preserves the requested mean exactly when ``observations`` is
    even, and introduces non-zero variance so Welch's t-test can run.
    Spread is clamped automatically when ``center`` is near zero so
    samples stay non-negative (quality / success / spend fields
    require it).
    """
    if observations == 0:
        return ()
    if observations == 1:
        return (center,)
    safe_spread = min(spread, center) if center >= 0.0 else 0.0
    if safe_spread <= 0.0:
        return tuple(center for _ in range(observations))
    step = 2 * safe_spread / (observations - 1)
    return tuple(center - safe_spread + step * i for i in range(observations))
