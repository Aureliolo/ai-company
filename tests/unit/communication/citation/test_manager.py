"""Tests for CitationManager."""

import pytest
from pydantic import ValidationError

from synthorg.communication.citation.manager import CitationManager


@pytest.mark.unit
class TestCitationManager:
    """CitationManager add, dedup, render, and handoff operations."""

    def test_empty_manager(self) -> None:
        mgr = CitationManager()
        assert mgr.citations == ()
        assert len(mgr.url_to_number) == 0

    def test_add_first_citation(self) -> None:
        mgr = CitationManager()
        mgr2 = mgr.add(
            url="https://example.com/article",
            title="Article",
            agent_id="agent-1",
        )
        assert len(mgr2.citations) == 1
        assert mgr2.citations[0].number == 1
        assert mgr2.citations[0].title == "Article"
        assert mgr2.citations[0].first_seen_by_agent_id == "agent-1"
        # Original unchanged (immutability)
        assert len(mgr.citations) == 0

    def test_add_two_different_urls(self) -> None:
        mgr = (
            CitationManager()
            .add(url="https://a.com", title="A", agent_id="ag-1")
            .add(url="https://b.com", title="B", agent_id="ag-2")
        )
        assert len(mgr.citations) == 2
        assert mgr.citations[0].number == 1
        assert mgr.citations[1].number == 2

    def test_dedup_same_url(self) -> None:
        mgr = (
            CitationManager()
            .add(url="https://example.com", title="First", agent_id="ag-1")
            .add(url="https://example.com", title="Second", agent_id="ag-2")
        )
        assert len(mgr.citations) == 1
        assert mgr.citations[0].title == "First"
        assert mgr.citations[0].first_seen_by_agent_id == "ag-1"

    def test_dedup_normalized_url(self) -> None:
        mgr = (
            CitationManager()
            .add(
                url="HTTPS://Example.COM/page#frag",
                title="First",
                agent_id="ag-1",
            )
            .add(
                url="https://example.com/page",
                title="Second",
                agent_id="ag-2",
            )
        )
        assert len(mgr.citations) == 1

    def test_render_inline_known_url(self) -> None:
        mgr = CitationManager().add(
            url="https://example.com",
            title="Example",
            agent_id="ag-1",
        )
        assert mgr.render_inline("https://example.com") == "[1]"

    def test_render_inline_unknown_url(self) -> None:
        mgr = CitationManager()
        assert mgr.render_inline("https://unknown.com") == ""

    def test_render_inline_normalizes_input(self) -> None:
        mgr = CitationManager().add(
            url="https://example.com",
            title="Example",
            agent_id="ag-1",
        )
        assert mgr.render_inline("HTTPS://EXAMPLE.COM/") == "[1]"

    def test_render_sources_section_empty(self) -> None:
        mgr = CitationManager()
        assert mgr.render_sources_section() == ""

    def test_render_sources_section_one(self) -> None:
        mgr = CitationManager().add(
            url="https://example.com/article",
            title="My Article",
            agent_id="ag-1",
        )
        section = mgr.render_sources_section()
        assert "## Sources" in section
        assert "[1]" in section
        assert "My Article" in section
        assert "https://example.com/article" in section

    def test_render_sources_section_multiple(self) -> None:
        mgr = (
            CitationManager()
            .add(url="https://a.com", title="A", agent_id="ag-1")
            .add(url="https://b.com", title="B", agent_id="ag-2")
        )
        section = mgr.render_sources_section()
        assert "[1]" in section
        assert "[2]" in section

    def test_accessed_via_passed_through(self) -> None:
        mgr = CitationManager().add(
            url="https://example.com",
            title="Example",
            agent_id="ag-1",
            accessed_via="memory",
        )
        assert mgr.citations[0].accessed_via == "memory"

    def test_frozen(self) -> None:
        mgr = CitationManager()
        with pytest.raises(ValidationError):
            mgr.citations = ()  # type: ignore[misc]


@pytest.mark.unit
class TestCitationManagerHandoff:
    """Serialization roundtrip via HandoffArtifact payload."""

    def test_empty_roundtrip(self) -> None:
        mgr = CitationManager()
        payload = mgr.to_handoff_payload()
        restored = CitationManager.from_handoff_payload(payload)
        assert restored.citations == ()
        assert len(restored.url_to_number) == 0

    def test_roundtrip_preserves_citations(self) -> None:
        mgr = (
            CitationManager()
            .add(url="https://a.com", title="A", agent_id="ag-1")
            .add(url="https://b.com", title="B", agent_id="ag-2")
        )
        payload = mgr.to_handoff_payload()
        restored = CitationManager.from_handoff_payload(payload)
        assert len(restored.citations) == 2
        assert restored.citations[0].number == 1
        assert restored.citations[0].title == "A"
        assert restored.citations[1].number == 2
        assert restored.citations[1].title == "B"

    def test_roundtrip_preserves_url_to_number(self) -> None:
        mgr = CitationManager().add(
            url="https://example.com",
            title="Example",
            agent_id="ag-1",
        )
        payload = mgr.to_handoff_payload()
        restored = CitationManager.from_handoff_payload(payload)
        assert restored.render_inline("https://example.com") == "[1]"

    def test_multi_hop_dedup(self) -> None:
        """Simulate A -> B -> C handoff with dedup."""
        # Agent A adds a citation
        mgr_a = CitationManager().add(
            url="https://shared.com",
            title="Shared",
            agent_id="agent-a",
        )
        # Handoff to B
        mgr_b = CitationManager.from_handoff_payload(
            mgr_a.to_handoff_payload(),
        )
        # B adds same URL (should dedup) + new URL
        mgr_b = mgr_b.add(
            url="https://shared.com",
            title="Shared Again",
            agent_id="agent-b",
        ).add(
            url="https://new.com",
            title="New",
            agent_id="agent-b",
        )
        assert len(mgr_b.citations) == 2
        # First citation kept agent-a as first_seen_by
        assert mgr_b.citations[0].first_seen_by_agent_id == "agent-a"
