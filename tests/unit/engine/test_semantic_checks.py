"""Unit tests for AST-based semantic conflict checks.

Tests the pure check functions in semantic_checks.py with
source code strings. Each check category has parametrized
tests covering positive detections and negative (no-conflict) cases.
"""

import pytest

from synthorg.core.enums import ConflictType
from synthorg.engine.workspace.semantic_checks import (
    check_duplicate_definitions,
    check_import_conflicts,
    check_removed_references,
    check_signature_changes,
)

pytestmark = pytest.mark.unit


# ---------------------------------------------------------------------------
# check_removed_references
# ---------------------------------------------------------------------------


class TestCheckRemovedReferences:
    """Tests for detecting references to names removed by the merge."""

    def test_function_removed_and_referenced(self) -> None:
        base_sources = {
            "utils.py": "def calculate_total(items):\n    return sum(items)\n",
        }
        merged_sources = {
            "utils.py": "def compute_total(items):\n    return sum(items)\n",
            "orders.py": (
                "from utils import calculate_total\n"
                "\nresult = calculate_total([1, 2, 3])\n"
            ),
        }
        conflicts = check_removed_references(
            base_sources=base_sources,
            merged_sources=merged_sources,
        )
        assert len(conflicts) >= 1
        assert all(c.conflict_type == ConflictType.SEMANTIC for c in conflicts)
        assert any("calculate_total" in c.description for c in conflicts)

    def test_class_removed_and_referenced(self) -> None:
        base_sources = {
            "models.py": "class UserProfile:\n    pass\n",
        }
        merged_sources = {
            "models.py": "class AccountProfile:\n    pass\n",
            "views.py": "profile = UserProfile()\n",
        }
        conflicts = check_removed_references(
            base_sources=base_sources,
            merged_sources=merged_sources,
        )
        assert len(conflicts) >= 1
        assert any("UserProfile" in c.description for c in conflicts)

    def test_removed_but_not_referenced(self) -> None:
        base_sources = {
            "utils.py": "def old_func():\n    pass\n",
        }
        merged_sources = {
            "utils.py": "def new_func():\n    pass\n",
            "other.py": "x = 42\n",
        }
        conflicts = check_removed_references(
            base_sources=base_sources,
            merged_sources=merged_sources,
        )
        assert len(conflicts) == 0

    def test_name_still_present_no_conflict(self) -> None:
        base_sources = {
            "utils.py": "def calculate_total(items):\n    return sum(items)\n",
        }
        merged_sources = {
            "utils.py": "def calculate_total(items):\n    return sum(items)\n",
            "orders.py": "result = calculate_total([1, 2, 3])\n",
        }
        conflicts = check_removed_references(
            base_sources=base_sources,
            merged_sources=merged_sources,
        )
        assert len(conflicts) == 0

    def test_constant_removed_and_referenced(self) -> None:
        base_sources = {
            "config.py": "MAX_RETRIES = 3\n",
        }
        merged_sources = {
            "config.py": "RETRY_LIMIT = 3\n",
            "client.py": "for i in range(MAX_RETRIES):\n    pass\n",
        }
        conflicts = check_removed_references(
            base_sources=base_sources,
            merged_sources=merged_sources,
        )
        assert len(conflicts) >= 1
        assert any("MAX_RETRIES" in c.description for c in conflicts)

    def test_empty_sources_no_conflict(self) -> None:
        conflicts = check_removed_references(
            base_sources={},
            merged_sources={},
        )
        assert conflicts == ()

    def test_syntax_error_in_source_skipped(self) -> None:
        base_sources = {
            "bad.py": "def foo(\n",
        }
        merged_sources = {
            "bad.py": "x = 1\n",
            "other.py": "foo()\n",
        }
        # Should not raise, just skip unparseable files
        conflicts = check_removed_references(
            base_sources=base_sources,
            merged_sources=merged_sources,
        )
        assert isinstance(conflicts, tuple)


# ---------------------------------------------------------------------------
# check_signature_changes
# ---------------------------------------------------------------------------


class TestCheckSignatureChanges:
    """Tests for detecting function signature incompatibilities."""

    def test_param_removed_callers_break(self) -> None:
        base_sources = {
            "utils.py": "def process(data, verbose=False):\n    pass\n",
        }
        merged_sources = {
            "utils.py": "def process(data):\n    pass\n",
            "main.py": "process(data, verbose=True)\n",
        }
        conflicts = check_signature_changes(
            base_sources=base_sources,
            merged_sources=merged_sources,
        )
        assert len(conflicts) >= 1
        assert any("process" in c.description for c in conflicts)

    def test_required_param_added_callers_break(self) -> None:
        base_sources = {
            "utils.py": "def process(data):\n    pass\n",
        }
        merged_sources = {
            "utils.py": "def process(data, mode):\n    pass\n",
            "main.py": "process(items)\n",
        }
        conflicts = check_signature_changes(
            base_sources=base_sources,
            merged_sources=merged_sources,
        )
        assert len(conflicts) >= 1

    def test_default_param_added_no_break(self) -> None:
        base_sources = {
            "utils.py": "def process(data):\n    pass\n",
        }
        merged_sources = {
            "utils.py": "def process(data, mode='fast'):\n    pass\n",
            "main.py": "process(items)\n",
        }
        conflicts = check_signature_changes(
            base_sources=base_sources,
            merged_sources=merged_sources,
        )
        assert len(conflicts) == 0

    def test_no_callers_no_conflict(self) -> None:
        base_sources = {
            "utils.py": "def process(data, verbose=False):\n    pass\n",
        }
        merged_sources = {
            "utils.py": "def process(data):\n    pass\n",
            "other.py": "x = 42\n",
        }
        conflicts = check_signature_changes(
            base_sources=base_sources,
            merged_sources=merged_sources,
        )
        assert len(conflicts) == 0

    def test_keyword_arg_removed_detected(self) -> None:
        base_sources = {
            "utils.py": "def process(data, verbose=False):\n    pass\n",
        }
        merged_sources = {
            "utils.py": "def process(data):\n    pass\n",
            "main.py": "process(data, verbose=True)\n",
        }
        conflicts = check_signature_changes(
            base_sources=base_sources,
            merged_sources=merged_sources,
        )
        assert len(conflicts) >= 1
        assert any("verbose" in c.description for c in conflicts)

    def test_varargs_accepts_extra_positional(self) -> None:
        base_sources = {
            "utils.py": "def process(data, *args):\n    pass\n",
        }
        merged_sources = {
            "utils.py": "def process(data, *args):\n    pass\n",
            "main.py": "process(1, 2, 3, 4)\n",
        }
        conflicts = check_signature_changes(
            base_sources=base_sources,
            merged_sources=merged_sources,
        )
        assert len(conflicts) == 0

    def test_signature_unchanged_no_conflict(self) -> None:
        base_sources = {
            "utils.py": "def process(data, verbose=False):\n    pass\n",
        }
        merged_sources = {
            "utils.py": "def process(data, verbose=False):\n    pass\n",
            "main.py": "process(data, verbose=True)\n",
        }
        conflicts = check_signature_changes(
            base_sources=base_sources,
            merged_sources=merged_sources,
        )
        assert len(conflicts) == 0


# ---------------------------------------------------------------------------
# check_duplicate_definitions
# ---------------------------------------------------------------------------


class TestCheckDuplicateDefinitions:
    """Tests for detecting duplicate top-level definitions."""

    def test_duplicate_function_same_file(self) -> None:
        merged_sources = {
            "utils.py": (
                "def process(data):\n"
                "    return data.upper()\n"
                "\n"
                "def process(data):\n"
                "    return data.lower()\n"
            ),
        }
        conflicts = check_duplicate_definitions(
            merged_sources=merged_sources,
        )
        assert len(conflicts) >= 1
        assert any("process" in c.description for c in conflicts)
        assert all(c.conflict_type == ConflictType.SEMANTIC for c in conflicts)

    def test_duplicate_class_same_file(self) -> None:
        merged_sources = {
            "models.py": (
                "class Widget:\n"
                "    color = 'red'\n"
                "\n"
                "class Widget:\n"
                "    color = 'blue'\n"
            ),
        }
        conflicts = check_duplicate_definitions(
            merged_sources=merged_sources,
        )
        assert len(conflicts) >= 1
        assert any("Widget" in c.description for c in conflicts)

    def test_no_duplicates_no_conflict(self) -> None:
        merged_sources = {
            "utils.py": ("def foo():\n    pass\n\ndef bar():\n    pass\n"),
        }
        conflicts = check_duplicate_definitions(
            merged_sources=merged_sources,
        )
        assert len(conflicts) == 0

    def test_nested_same_name_not_flagged(self) -> None:
        merged_sources = {
            "utils.py": (
                "class Outer:\n"
                "    def helper(self):\n"
                "        pass\n"
                "\n"
                "def helper():\n"
                "    pass\n"
            ),
        }
        # A method inside a class and a top-level function share a name --
        # this is valid Python, not a duplicate definition at module level
        conflicts = check_duplicate_definitions(
            merged_sources=merged_sources,
        )
        assert len(conflicts) == 0

    def test_empty_sources(self) -> None:
        conflicts = check_duplicate_definitions(merged_sources={})
        assert conflicts == ()

    def test_syntax_error_skipped(self) -> None:
        merged_sources = {"bad.py": "def foo(\n"}
        conflicts = check_duplicate_definitions(merged_sources=merged_sources)
        assert isinstance(conflicts, tuple)


# ---------------------------------------------------------------------------
# check_import_conflicts
# ---------------------------------------------------------------------------


class TestCheckImportConflicts:
    """Tests for detecting imports of removed exports."""

    def test_import_of_removed_name(self) -> None:
        base_sources = {
            "utils.py": ("def helper():\n    pass\n\ndef process():\n    pass\n"),
        }
        merged_sources = {
            "utils.py": "def process():\n    pass\n",
            "main.py": "from utils import helper\n",
        }
        conflicts = check_import_conflicts(
            base_sources=base_sources,
            merged_sources=merged_sources,
        )
        assert len(conflicts) >= 1
        assert any("helper" in c.description for c in conflicts)

    def test_import_still_valid(self) -> None:
        base_sources = {
            "utils.py": "def helper():\n    pass\n",
        }
        merged_sources = {
            "utils.py": "def helper():\n    pass\n",
            "main.py": "from utils import helper\n",
        }
        conflicts = check_import_conflicts(
            base_sources=base_sources,
            merged_sources=merged_sources,
        )
        assert len(conflicts) == 0

    def test_import_star_not_flagged(self) -> None:
        base_sources = {
            "utils.py": "def helper():\n    pass\n",
        }
        merged_sources = {
            "utils.py": "def new_helper():\n    pass\n",
            "main.py": "from utils import *\n",
        }
        # Star imports cannot be checked -- skip them
        conflicts = check_import_conflicts(
            base_sources=base_sources,
            merged_sources=merged_sources,
        )
        assert len(conflicts) == 0

    def test_class_removed_import_breaks(self) -> None:
        base_sources = {
            "models.py": "class Config:\n    pass\n",
        }
        merged_sources = {
            "models.py": "class Settings:\n    pass\n",
            "app.py": "from models import Config\n",
        }
        conflicts = check_import_conflicts(
            base_sources=base_sources,
            merged_sources=merged_sources,
        )
        assert len(conflicts) >= 1
        assert any("Config" in c.description for c in conflicts)

    def test_empty_sources(self) -> None:
        conflicts = check_import_conflicts(
            base_sources={},
            merged_sources={},
        )
        assert conflicts == ()
