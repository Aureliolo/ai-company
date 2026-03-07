"""Max delegation depth check (pure function)."""

from ai_company.communication.loop_prevention.models import GuardCheckOutcome

_MECHANISM = "max_depth"


def check_delegation_depth(
    delegation_chain: tuple[str, ...],
    max_depth: int,
) -> GuardCheckOutcome:
    """Check whether the delegation chain exceeds maximum depth.

    Args:
        delegation_chain: Current chain of delegator agent IDs.
        max_depth: Maximum allowed chain length.

    Returns:
        Outcome with passed=True if within limit.
    """
    if len(delegation_chain) >= max_depth:
        return GuardCheckOutcome(
            passed=False,
            mechanism=_MECHANISM,
            message=(
                f"Delegation chain length {len(delegation_chain)} "
                f"reaches or exceeds max depth {max_depth}"
            ),
        )
    return GuardCheckOutcome(passed=True, mechanism=_MECHANISM)
