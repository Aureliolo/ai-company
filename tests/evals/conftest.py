"""Eval-specific conftest for agent evaluation tests.

Provides pytest options for filtering by behavior category and
setting eval-specific timeouts.  Agent-eval tests are excluded
from the default suite and only run when explicitly targeted.
"""

import pytest


def pytest_addoption(parser: pytest.Parser) -> None:
    """Add pytest CLI options for agent-eval tests."""
    group = parser.getgroup("agent_eval", "Agent evaluation options")
    group.addoption(
        "--run-agent-evals",
        action="store_true",
        default=False,
        help="Include agent-eval tests (excluded by default)",
    )
    group.addoption(
        "--eval-category",
        action="store",
        default=None,
        help="Run only agent-eval tests with this behavior category",
    )
    group.addoption(
        "--eval-timeout",
        action="store",
        type=int,
        default=300,
        help="Timeout in seconds for agent-eval tests (default: 300)",
    )


def pytest_collection_modifyitems(
    config: pytest.Config,
    items: list[pytest.Item],
) -> None:
    """Apply eval-specific filtering and timeout overrides.

    Agent-eval tests are excluded from the default suite unless
    ``--run-agent-evals`` is passed.  The ``--eval-category``
    flag further narrows within the eval suite.
    """
    run_evals = config.getoption("--run-agent-evals", default=False)
    eval_category = config.getoption("--eval-category", default=None)
    eval_timeout = config.getoption("--eval-timeout", default=300)

    for item in items:
        marker = item.get_closest_marker("agent_eval")
        if marker is None:
            continue

        # Skip unless explicitly opted-in.
        if not run_evals and eval_category is None:
            item.add_marker(
                pytest.mark.skip(
                    reason="agent-eval tests require --run-agent-evals",
                ),
            )
            continue

        # Apply eval timeout.
        item.add_marker(pytest.mark.timeout(eval_timeout))

        # Filter by category if specified.
        if eval_category is not None:
            category = marker.kwargs.get("category", "")
            if category != eval_category:
                item.add_marker(
                    pytest.mark.skip(
                        reason=f"eval category {category!r} != {eval_category!r}",
                    ),
                )
