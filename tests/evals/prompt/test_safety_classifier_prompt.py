"""Prompt eval: safety classifier temperature contract."""

import inspect

import pytest


@pytest.mark.unit
class TestSafetyClassifierPromptContract:
    """Guard rails for the approval safety classifier prompt surface."""

    def test_temperature_is_zero(self) -> None:
        """Safety classifier must run at temperature=0 for a stable verdict.

        Uses an AST walk rather than substring matching so the check
        is resilient to formatting (``temperature=0.0`` vs
        ``temperature = 0.0``) and can't be fooled by a docstring
        or comment that merely mentions the phrase.
        """
        import ast

        from synthorg.security import safety_classifier

        source = inspect.getsource(safety_classifier)
        tree = ast.parse(source)

        def _is_zero(node: ast.AST) -> bool:
            # Reject bools explicitly -- ``isinstance(True, int)`` is
            # ``True`` in Python, so without this guard a
            # ``temperature=False`` binding would silently satisfy the
            # assertion.
            if not isinstance(node, ast.Constant):
                return False
            value = node.value
            if isinstance(value, bool):
                return False
            return isinstance(value, int | float) and value == 0

        # Restrict the search to ``CompletionConfig(..., temperature=0)``
        # calls so an unrelated module-level binding (e.g. a docstring
        # example assigned to ``temperature``) cannot make this test
        # false-pass. The classifier constructs its config via the
        # ``CompletionConfig`` class from ``synthorg.providers.models``.
        def _targets_completion_config(func: ast.AST) -> bool:
            if isinstance(func, ast.Name):
                return func.id == "CompletionConfig"
            if isinstance(func, ast.Attribute):
                return func.attr == "CompletionConfig"
            return False

        # Tighten the traversal: only walk the body of
        # ``_classify_via_llm`` (the single function that actually
        # builds the CompletionConfig) rather than the entire module,
        # so a CompletionConfig stubbed elsewhere in the file (tests,
        # helpers) cannot satisfy the assertion.
        classify_fn: ast.FunctionDef | ast.AsyncFunctionDef | None = None
        for node in ast.walk(tree):
            if (
                isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef)
                and node.name == "_classify_via_llm"
            ):
                classify_fn = node
                break
        assert classify_fn is not None, (
            "safety_classifier must expose a ``_classify_via_llm`` function "
            "that drives the LLM call and pins its CompletionConfig."
        )

        found = any(
            isinstance(n, ast.Call)
            and _targets_completion_config(n.func)
            and any(kw.arg == "temperature" and _is_zero(kw.value) for kw in n.keywords)
            for n in ast.walk(classify_fn)
        )
        assert found, (
            "safety_classifier must construct a ``CompletionConfig`` with "
            "``temperature=0.0`` inside ``_classify_via_llm``. No such "
            "call was found in that function's AST."
        )
