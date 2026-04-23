"""Prompt-surface evaluation suites (HYG-1 part 10).

Each module in this package pins the temperature, model identity,
and expected-grade threshold for a prompt-driven surface so drift
in the prompt body or model config is caught deterministically.

Run with:

    uv run python -m pytest tests/evals/prompt/ --run-agent-evals -n 8
"""
