"""Utilities for agent evaluation testing.

Provides ``n1_prefix_replay`` for regression testing multi-turn
agent behavior by replaying the first N-1 turns of a recorded
trace and letting the agent generate only the final turn.
"""

from collections.abc import Callable

from synthorg.engine.loop_protocol import ExecutionResult, TurnRecord


async def n1_prefix_replay(
    trace: ExecutionResult,
    *,
    replay_fn: Callable[[tuple[TurnRecord, ...]], TurnRecord],
) -> TurnRecord:
    """Replay first N-1 turns, let agent generate turn N only.

    Avoids compounding errors when evaluating multi-turn behaviors:
    the agent receives the exact context from a real execution up
    to turn N-1, and is evaluated only on its generation of turn N.

    Args:
        trace: Complete execution result with N turns.
        replay_fn: Callable that takes the prefix turns (0..N-2)
            and returns the agent's generated final turn.

    Returns:
        The agent's generated final turn, for comparison against
        ``trace.turns[-1]``.

    Raises:
        ValueError: If trace has fewer than 2 turns.
    """
    if len(trace.turns) < 2:
        msg = f"Trace must have >= 2 turns for N-1 replay, got {len(trace.turns)}"
        raise ValueError(msg)

    prefix = trace.turns[:-1]
    return replay_fn(prefix)
