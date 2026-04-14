"""Tests for citation domain models."""

from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from synthorg.communication.citation.models import Citation


@pytest.mark.unit
class TestCitation:
    """Citation model construction and validation."""

    def _make_citation(self, **overrides: object) -> Citation:
        defaults: dict[str, object] = {
            "number": 1,
            "url": "https://example.com/article",
            "title": "Example Article",
            "first_seen_at": datetime(2026, 4, 14, tzinfo=UTC),
            "first_seen_by_agent_id": "agent-1",
            "accessed_via": "tool",
        }
        defaults.update(overrides)
        return Citation(**defaults)  # type: ignore[arg-type]

    def test_minimal_valid(self) -> None:
        c = self._make_citation()
        assert c.number == 1
        assert str(c.url) == "https://example.com/article"
        assert c.title == "Example Article"
        assert c.first_seen_by_agent_id == "agent-1"
        assert c.accessed_via == "tool"

    def test_frozen(self) -> None:
        c = self._make_citation()
        with pytest.raises(ValidationError):
            c.number = 2  # type: ignore[misc]

    def test_number_must_be_positive(self) -> None:
        with pytest.raises(ValidationError, match="greater than or equal to 1"):
            self._make_citation(number=0)

    def test_number_negative_rejected(self) -> None:
        with pytest.raises(ValidationError):
            self._make_citation(number=-1)

    def test_accessed_via_tool(self) -> None:
        c = self._make_citation(accessed_via="tool")
        assert c.accessed_via == "tool"

    def test_accessed_via_memory(self) -> None:
        c = self._make_citation(accessed_via="memory")
        assert c.accessed_via == "memory"

    def test_accessed_via_file(self) -> None:
        c = self._make_citation(accessed_via="file")
        assert c.accessed_via == "file"

    def test_accessed_via_invalid_rejected(self) -> None:
        with pytest.raises(ValidationError):
            self._make_citation(accessed_via="unknown")

    def test_blank_title_rejected(self) -> None:
        with pytest.raises(ValidationError):
            self._make_citation(title="")

    def test_blank_agent_id_rejected(self) -> None:
        with pytest.raises(ValidationError):
            self._make_citation(first_seen_by_agent_id="")

    def test_invalid_url_rejected(self) -> None:
        with pytest.raises(ValidationError):
            self._make_citation(url="not-a-url")
