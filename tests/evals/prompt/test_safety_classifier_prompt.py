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
            if isinstance(node, ast.Constant) and isinstance(node.value, int | float):
                return node.value == 0
            return False

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

        found = any(
            isinstance(node, ast.Call)
            and _targets_completion_config(node.func)
            and any(
                kw.arg == "temperature" and _is_zero(kw.value) for kw in node.keywords
            )
            for node in ast.walk(tree)
        )
        assert found, (
            "safety_classifier must construct a ``CompletionConfig`` with "
            "``temperature=0.0`` (or equivalent numeric zero). No such "
            "call was found in the AST."
        )
