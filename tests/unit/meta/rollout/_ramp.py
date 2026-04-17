"""Shared deterministic sample generator for rollout tests."""


def ramp(center: float, observations: int, spread: float) -> tuple[float, ...]:
    """Build a deterministic symmetric ramp around ``center``.

    The ramp is symmetric around ``center`` with half-width ``spread``.
    For even ``observations`` the sample mean equals ``center`` exactly;
    for odd ``observations`` the ramp is also symmetric and centered
    on ``center`` (the middle value is exactly ``center``) so the mean
    equals ``center`` up to floating-point precision. The spread is
    clamped to ``min(spread, center)`` so samples stay non-negative,
    which is required for quality / success / spend fields.

    Args:
        center: Target mean of the ramp. Must be ``>= 0``.
        observations: Number of samples. Must be a non-negative ``int``.
        spread: Half-width of the ramp. Must be ``>= 0``.

    Raises:
        ValueError: If any argument is negative.
    """
    if observations < 0:
        msg = f"observations must be non-negative; got {observations}"
        raise ValueError(msg)
    if center < 0.0:
        msg = f"center must be non-negative; got {center}"
        raise ValueError(msg)
    if spread < 0.0:
        msg = f"spread must be non-negative; got {spread}"
        raise ValueError(msg)
    if observations == 0:
        return ()
    if observations == 1:
        return (center,)
    safe_spread = min(spread, center)
    if safe_spread == 0.0:
        return tuple(center for _ in range(observations))
    step = 2 * safe_spread / (observations - 1)
    return tuple(center - safe_spread + step * i for i in range(observations))
