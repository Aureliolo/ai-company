"""Tests for shared graph utilities (topological sort, adjacency maps)."""

import pytest

from synthorg.engine.workflow.graph_utils import (
    build_adjacency_maps,
    topological_sort,
)
from tests.unit.engine.workflow.conftest import (
    make_edge,
    make_end_node,
    make_start_node,
    make_task_node,
    make_workflow,
)


class TestTopologicalSort:
    """Kahn's algorithm for topological ordering."""

    @pytest.mark.unit
    def test_linear_chain(self) -> None:
        ids = ["a", "b", "c"]
        adj: dict[str, list[str]] = {"a": ["b"], "b": ["c"]}
        result = topological_sort(ids, adj)
        assert result == ["a", "b", "c"]

    @pytest.mark.unit
    def test_diamond_graph(self) -> None:
        ids = ["a", "b", "c", "d"]
        adj: dict[str, list[str]] = {
            "a": ["b", "c"],
            "b": ["d"],
            "c": ["d"],
        }
        result = topological_sort(ids, adj)
        assert result.index("a") < result.index("b")
        assert result.index("a") < result.index("c")
        assert result.index("b") < result.index("d")
        assert result.index("c") < result.index("d")

    @pytest.mark.unit
    def test_single_node(self) -> None:
        result = topological_sort(["a"], {})
        assert result == ["a"]

    @pytest.mark.unit
    def test_empty_graph(self) -> None:
        result = topological_sort([], {})
        assert result == []

    @pytest.mark.unit
    def test_cycle_raises_value_error(self) -> None:
        ids = ["a", "b"]
        adj: dict[str, list[str]] = {"a": ["b"], "b": ["a"]}
        with pytest.raises(ValueError, match="cycle"):
            topological_sort(ids, adj)

    @pytest.mark.unit
    def test_self_loop_raises_value_error(self) -> None:
        ids = ["a"]
        adj: dict[str, list[str]] = {"a": ["a"]}
        with pytest.raises(ValueError, match="cycle"):
            topological_sort(ids, adj)

    @pytest.mark.unit
    def test_disconnected_nodes(self) -> None:
        ids = ["a", "b", "c"]
        adj: dict[str, list[str]] = {}
        result = topological_sort(ids, adj)
        assert set(result) == {"a", "b", "c"}


class TestBuildAdjacencyMaps:
    """Build forward, reverse, and typed-outgoing adjacency maps."""

    @pytest.mark.unit
    def test_simple_workflow(self) -> None:
        wf = make_workflow(
            nodes=(
                make_start_node(),
                make_task_node("task-1"),
                make_end_node(),
            ),
            edges=(
                make_edge("e1", "start-1", "task-1"),
                make_edge("e2", "task-1", "end-1"),
            ),
        )
        adjacency, reverse_adj, outgoing = build_adjacency_maps(wf)

        assert adjacency["start-1"] == ["task-1"]
        assert adjacency["task-1"] == ["end-1"]
        assert reverse_adj["task-1"] == ["start-1"]
        assert reverse_adj["end-1"] == ["task-1"]
        assert len(outgoing["start-1"]) == 1

    @pytest.mark.unit
    def test_returns_plain_dicts(self) -> None:
        """Ensure defaultdict is not leaked to callers."""
        wf = make_workflow(
            nodes=(make_start_node(), make_end_node()),
            edges=(make_edge("e1", "start-1", "end-1"),),
        )
        adjacency, reverse_adj, outgoing = build_adjacency_maps(wf)
        assert type(adjacency) is dict
        assert type(reverse_adj) is dict
        assert type(outgoing) is dict
