"""Tests for extractive preservation."""

import pytest

from synthorg.memory.consolidation.extractive import ExtractivePreserver

pytestmark = pytest.mark.timeout(30)


@pytest.mark.unit
class TestExtractivePreserver:
    """ExtractivePreserver extraction behaviour."""

    def test_extracts_anchors(self) -> None:
        preserver = ExtractivePreserver(anchor_length=20)
        content = "A" * 100
        result = preserver.extract(content)
        assert "[START]" in result
        assert "[MID]" in result
        assert "[END]" in result

    def test_extracts_identifiers(self) -> None:
        preserver = ExtractivePreserver()
        content = (
            "The user_id is abc-123-def and the commit hash is "
            "a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2."
        )
        result = preserver.extract(content)
        assert "[Extractive preservation]" in result
        assert "Key facts:" in result
        assert "a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2" in result

    def test_extracts_urls(self) -> None:
        preserver = ExtractivePreserver()
        content = "API endpoint: https://api.example.com/v2/users/12345"
        result = preserver.extract(content)
        assert "https://api.example.com/v2/users/12345" in result

    def test_extracts_key_value_pairs(self) -> None:
        preserver = ExtractivePreserver()
        content = "host: 192.168.1.100\nport: 5432\ntimeout: 30"
        result = preserver.extract(content)
        assert "Key facts:" in result
        assert "host: 192.168.1.100" in result
        assert "port: 5432" in result

    def test_preserves_empty_value_assignments(self) -> None:
        """Blank-value key=value pairs are preserved verbatim."""
        preserver = ExtractivePreserver()
        content = "API_KEY=\nDEBUG=true"
        result = preserver.extract(content)
        assert "API_KEY=" in result
        assert "DEBUG=true" in result

    def test_max_facts_limit(self) -> None:
        preserver = ExtractivePreserver(max_facts=3)
        content = "\n".join(f"key_{i}: value_{i}" for i in range(20))
        result = preserver.extract(content)
        assert "Key facts:" in result
        # Count individual fact lines (one per line, prefixed with "- ")
        fact_lines = [line for line in result.splitlines() if line.startswith("- ")]
        assert len(fact_lines) <= 3

    def test_anchor_length_parameter(self) -> None:
        preserver = ExtractivePreserver(anchor_length=50)
        content = "X" * 500
        result = preserver.extract(content)
        # Each anchor should be at most anchor_length chars
        for line in result.splitlines():
            if line.startswith(("[START]", "[END]")):
                # Anchor content (after tag + space)
                anchor_text = line.split("] ", 1)[1] if "] " in line else ""
                assert len(anchor_text) <= 53  # 50 + "..."

    def test_short_content(self) -> None:
        """Content shorter than anchor_length uses single anchor."""
        preserver = ExtractivePreserver(anchor_length=150)
        content = "short text"
        result = preserver.extract(content)
        assert "[Extractive preservation]" in result
        assert "[START] short text" in result
        # Short content should not duplicate into MID/END
        assert "[MID]" not in result
        assert "[END]" not in result

    def test_invalid_max_facts(self) -> None:
        with pytest.raises(ValueError, match="max_facts"):
            ExtractivePreserver(max_facts=0)

    def test_invalid_anchor_length(self) -> None:
        with pytest.raises(ValueError, match="anchor_length"):
            ExtractivePreserver(anchor_length=0)
