"""Tests for workspace isolation protocol."""

import pytest

from ai_company.engine.workspace.protocol import WorkspaceIsolationStrategy


class TestWorkspaceIsolationStrategy:
    """Tests for WorkspaceIsolationStrategy protocol."""

    @pytest.mark.unit
    def test_protocol_is_runtime_checkable(self) -> None:
        """Protocol can be used with isinstance checks."""
        assert hasattr(WorkspaceIsolationStrategy, "__protocol_attrs__") or (
            hasattr(WorkspaceIsolationStrategy, "_is_runtime_protocol")
            and WorkspaceIsolationStrategy._is_runtime_protocol
        )

    @pytest.mark.unit
    def test_non_conforming_class_rejected(self) -> None:
        """A class missing methods does not satisfy the protocol."""

        class NotAStrategy:
            pass

        assert not isinstance(NotAStrategy(), WorkspaceIsolationStrategy)

    @pytest.mark.unit
    def test_protocol_defines_expected_methods(self) -> None:
        """Protocol declares the expected method signatures."""
        expected = {
            "setup_workspace",
            "teardown_workspace",
            "merge_workspace",
            "list_active_workspaces",
            "get_strategy_type",
        }
        # Protocol methods are in __abstractmethods__ or annotations
        members = {
            name for name in dir(WorkspaceIsolationStrategy) if not name.startswith("_")
        }
        assert expected.issubset(members)
