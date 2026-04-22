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

        found = False
        for node in ast.walk(tree):
            # Keyword argument: ``foo(temperature=0.0)``.
            if (
                isinstance(node, ast.keyword)
                and node.arg == "temperature"
                and _is_zero(node.value)
            ):
                found = True
                break
            # Assignment: ``temperature = 0.0``.
            if isinstance(node, ast.Assign):
                for target in node.targets:
                    if (
                        isinstance(target, ast.Name)
                        and target.id == "temperature"
                        and _is_zero(node.value)
                    ):
                        found = True
                        break
                if found:
                    break
            # Annotated default: ``temperature: float = 0.0``.
            if (
                isinstance(node, ast.AnnAssign)
                and isinstance(node.target, ast.Name)
                and node.target.id == "temperature"
                and node.value is not None
                and _is_zero(node.value)
            ):
                found = True
                break

        assert found, (
            "safety_classifier must pin ``temperature=0.0`` via a "
            "keyword argument, assignment, or annotated default; "
            "no such binding found in the AST."
        )
