"""Tests for tool-call fingerprint computation."""

import pytest

from synthorg.engine.loop_helpers import compute_fingerprints
from synthorg.providers.models import ToolCall


@pytest.mark.unit
class TestComputeFingerprints:
    """Fingerprint computation from tool calls."""

    def test_deterministic_same_args(self) -> None:
        tc = ToolCall(id="tc-1", name="search", arguments={"query": "hello"})
        fp1 = compute_fingerprints((tc,))
        fp2 = compute_fingerprints((tc,))
        assert fp1 == fp2

    def test_order_independent_dict_keys(self) -> None:
        tc1 = ToolCall(
            id="tc-1",
            name="search",
            arguments={"a": 1, "b": 2},
        )
        tc2 = ToolCall(
            id="tc-2",
            name="search",
            arguments={"b": 2, "a": 1},
        )
        fp1 = compute_fingerprints((tc1,))
        fp2 = compute_fingerprints((tc2,))
        assert fp1 == fp2

    def test_different_args_different_fingerprint(self) -> None:
        tc1 = ToolCall(
            id="tc-1",
            name="search",
            arguments={"query": "hello"},
        )
        tc2 = ToolCall(
            id="tc-2",
            name="search",
            arguments={"query": "world"},
        )
        fp1 = compute_fingerprints((tc1,))
        fp2 = compute_fingerprints((tc2,))
        assert fp1 != fp2

    def test_empty_arguments(self) -> None:
        tc = ToolCall(id="tc-1", name="noop", arguments={})
        fp = compute_fingerprints((tc,))
        assert len(fp) == 1
        assert fp[0].startswith("noop:")

    def test_nested_dict_deterministic(self) -> None:
        tc = ToolCall(
            id="tc-1",
            name="complex",
            arguments={"outer": {"inner": [1, 2, 3]}},
        )
        fp1 = compute_fingerprints((tc,))
        fp2 = compute_fingerprints((tc,))
        assert fp1 == fp2

    def test_nested_list_deterministic(self) -> None:
        tc = ToolCall(
            id="tc-1",
            name="list_tool",
            arguments={"items": [{"a": 1}, {"b": 2}]},
        )
        fp1 = compute_fingerprints((tc,))
        fp2 = compute_fingerprints((tc,))
        assert fp1 == fp2

    def test_sorted_output_within_turn(self) -> None:
        tc_a = ToolCall(id="tc-1", name="alpha", arguments={})
        tc_b = ToolCall(id="tc-2", name="beta", arguments={})
        fp = compute_fingerprints((tc_b, tc_a))
        assert fp[0].startswith("alpha:")
        assert fp[1].startswith("beta:")

    def test_empty_tool_calls(self) -> None:
        fp = compute_fingerprints(())
        assert fp == ()

    def test_fingerprint_format(self) -> None:
        tc = ToolCall(id="tc-1", name="search", arguments={"q": "test"})
        fp = compute_fingerprints((tc,))
        assert len(fp) == 1
        name, args_hash = fp[0].split(":")
        assert name == "search"
        assert len(args_hash) == 16
        # Hash should be hexadecimal
        int(args_hash, 16)

    def test_different_tool_names_different_fingerprint(self) -> None:
        tc1 = ToolCall(id="tc-1", name="search", arguments={"q": "test"})
        tc2 = ToolCall(id="tc-2", name="read", arguments={"q": "test"})
        fp1 = compute_fingerprints((tc1,))
        fp2 = compute_fingerprints((tc2,))
        assert fp1 != fp2
