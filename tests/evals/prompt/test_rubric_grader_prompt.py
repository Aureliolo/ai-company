"""Prompt eval: rubric grader temperature + prompt drift.

Rather than replay a full LLM round-trip (flaky, provider-gated), the
suite asserts the two properties that deterministically matter for a
pinned prompt surface:

1. The production config still pins ``temperature=0.0`` -- any drift
   toward higher temperatures turns the grader non-deterministic
   across CI shards.
2. The bytes of the prompt body haven't silently drifted: edits must
   either update the pinned fingerprint in this test OR ship new
   labelled examples that still pass.

Reference implementation: ``synthorg.engine.quality.graders.llm``.
"""

import pytest

from tests.evals.prompt._harness import fingerprint_prompt


@pytest.mark.unit
class TestRubricGraderPromptContract:
    """Guard rails for the LLM rubric grader prompt surface."""

    def test_temperature_is_zero(self) -> None:
        """Grader must run at temperature=0 for deterministic scores.

        Checked via an AST walk (resilient to formatting) and a
        substring cross-check (guards against accidentally removing
        the keyword during a refactor).
        """
        import ast
        import inspect

        from synthorg.engine.quality.graders.llm import LLMRubricGrader

        source = inspect.getsource(LLMRubricGrader)
        assert "temperature=0.0" in source, (
            "LLMRubricGrader must pin temperature=0.0 for determinism"
        )
        # AST-level check: find a ``temperature=0.0`` keyword
        # argument inside a ``Call`` (CompletionConfig construction)
        # anywhere in the grader class. This refuses to pass if the
        # substring appears only in a docstring.
        tree = ast.parse(source)
        found = any(
            isinstance(node, ast.keyword)
            and node.arg == "temperature"
            and isinstance(node.value, ast.Constant)
            and isinstance(node.value.value, int | float)
            and node.value.value == 0
            for node in ast.walk(tree)
        )
        assert found, (
            "LLMRubricGrader must pass ``temperature=0.0`` as a "
            "keyword argument when constructing CompletionConfig "
            "(no matching ast.keyword node found)"
        )

    # Pinned SHA-256[:16] of the grader module source. When the
    # prompt or any supporting code in ``llm.py`` changes
    # intentionally, update this value AND add a regression example
    # below to prove the new prompt still passes the grading
    # contract. The bare ``isinstance + len == 16`` check the
    # original test used could never detect drift, which is exactly
    # what fingerprint pinning is supposed to catch.
    PINNED_RUBRIC_GRADER_FP = "88db1624d56dc099"

    def test_prompt_fingerprint_is_pinned(self) -> None:
        """Detect silent prompt edits via a stable hash.

        When the prompt changes intentionally, update the pinned
        fingerprint + add a regression example below to prove the
        new prompt still passes the grading contract.
        """
        import inspect

        from synthorg.engine.quality.graders import (
            llm as _grader_module,
        )

        source = inspect.getsource(_grader_module)
        fp = fingerprint_prompt(source)
        assert fp == self.PINNED_RUBRIC_GRADER_FP, (
            f"LLM rubric grader source fingerprint drifted: got {fp!r}, "  # noqa: S608 -- assertion message, not SQL
            f"expected {self.PINNED_RUBRIC_GRADER_FP!r}. "
            "If this was intentional, update the pinned fingerprint "
            "AND extend the labelled example set to cover the new behaviour."
        )
