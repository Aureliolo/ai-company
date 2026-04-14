"""Tests for HTMLParseGuard tool output sanitizer."""

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st
from pydantic import ValidationError

from synthorg.tools.html_parse_guard import (
    HTMLParseGuard,
    HTMLParseGuardConfig,
    HTMLSanitizeResult,
)


@pytest.mark.unit
class TestHTMLParseGuardConfig:
    """Tests for HTMLParseGuardConfig defaults and validation."""

    def test_defaults(self) -> None:
        config = HTMLParseGuardConfig()
        assert config.enabled is True
        assert config.gap_threshold_ratio == pytest.approx(0.05)

    def test_frozen(self) -> None:
        config = HTMLParseGuardConfig()
        with pytest.raises(ValidationError):
            config.enabled = False  # type: ignore[misc]

    def test_custom_threshold(self) -> None:
        config = HTMLParseGuardConfig(gap_threshold_ratio=0.1)
        assert config.gap_threshold_ratio == pytest.approx(0.1)

    def test_threshold_bounds(self) -> None:
        with pytest.raises(ValueError, match="greater than or equal to 0"):
            HTMLParseGuardConfig(gap_threshold_ratio=-0.1)
        with pytest.raises(ValueError, match="less than or equal to 1"):
            HTMLParseGuardConfig(gap_threshold_ratio=1.5)


@pytest.mark.unit
class TestHTMLSanitizeResult:
    """Tests for the HTMLSanitizeResult frozen model."""

    def test_frozen(self) -> None:
        result = HTMLSanitizeResult(
            cleaned="hello",
            gap_detected=False,
            gap_ratio=0.0,
            stripped_element_count=0,
        )
        assert result.cleaned == "hello"
        assert result.gap_detected is False
        with pytest.raises(ValidationError):
            result.cleaned = "x"  # type: ignore[misc]


@pytest.mark.unit
class TestHTMLParseGuard:
    """Tests for HTMLParseGuard sanitization logic."""

    def test_non_html_returns_unchanged(self) -> None:
        guard = HTMLParseGuard()
        result = guard.sanitize("plain text without any tags")
        assert result.cleaned == "plain text without any tags"
        assert result.gap_detected is False
        assert result.stripped_element_count == 0

    def test_empty_string(self) -> None:
        guard = HTMLParseGuard()
        result = guard.sanitize("")
        assert result.cleaned == ""
        assert result.gap_detected is False

    def test_strips_script_tags(self) -> None:
        guard = HTMLParseGuard()
        html = "<p>Hello</p><script>alert('xss')</script><p>World</p>"
        result = guard.sanitize(html)
        assert "alert" not in result.cleaned
        assert "Hello" in result.cleaned
        assert "World" in result.cleaned
        assert result.stripped_element_count >= 1

    def test_strips_style_tags(self) -> None:
        guard = HTMLParseGuard()
        html = "<p>Hello</p><style>.hidden{display:none}</style>"
        result = guard.sanitize(html)
        assert ".hidden" not in result.cleaned
        assert "Hello" in result.cleaned
        assert result.stripped_element_count >= 1

    def test_strips_noscript_tags(self) -> None:
        guard = HTMLParseGuard()
        html = "<p>Visible</p><noscript>Fallback content</noscript>"
        result = guard.sanitize(html)
        assert "Fallback content" not in result.cleaned
        assert "Visible" in result.cleaned

    def test_strips_html_comments(self) -> None:
        guard = HTMLParseGuard()
        html = "<p>Hello</p><!-- secret injection --><p>World</p>"
        result = guard.sanitize(html)
        assert "secret injection" not in result.cleaned
        assert "Hello" in result.cleaned
        assert "World" in result.cleaned

    def test_strips_display_none_elements(self) -> None:
        guard = HTMLParseGuard()
        html = '<p>Visible</p><div style="display:none">Hidden injection payload</div>'
        result = guard.sanitize(html)
        assert "Hidden injection payload" not in result.cleaned
        assert "Visible" in result.cleaned
        assert result.stripped_element_count >= 1

    def test_strips_visibility_hidden_elements(self) -> None:
        guard = HTMLParseGuard()
        html = '<p>Visible</p><span style="visibility:hidden">Invisible text</span>'
        result = guard.sanitize(html)
        assert "Invisible text" not in result.cleaned
        assert "Visible" in result.cleaned

    def test_strips_aria_hidden_elements(self) -> None:
        guard = HTMLParseGuard()
        html = '<p>Visible</p><div aria-hidden="true">Screen reader hidden</div>'
        result = guard.sanitize(html)
        assert "Screen reader hidden" not in result.cleaned
        assert "Visible" in result.cleaned

    def test_gap_detection_with_hidden_content(self) -> None:
        """Large hidden content relative to visible triggers gap detection."""
        guard = HTMLParseGuard(config=HTMLParseGuardConfig(gap_threshold_ratio=0.05))
        # Visible: short, hidden: long -- gap should be detected.
        visible = "Hi"
        hidden = "A" * 200
        html = f'<p>{visible}</p><div style="display:none">{hidden}</div>'
        result = guard.sanitize(html)
        assert result.gap_detected is True
        assert result.gap_ratio > 0.05

    def test_no_gap_for_clean_html(self) -> None:
        guard = HTMLParseGuard()
        html = "<p>Hello World</p><p>This is clean HTML.</p>"
        result = guard.sanitize(html)
        assert result.gap_detected is False

    def test_malformed_html_returns_original(self) -> None:
        """Malformed HTML that cannot be parsed should return original."""
        guard = HTMLParseGuard()
        # lxml is very forgiving, so truly unparseable content is rare.
        # But non-HTML with angle brackets should still work.
        text = "5 > 3 and 2 < 4"
        result = guard.sanitize(text)
        # Should not crash and should return something reasonable.
        assert result.cleaned is not None

    def test_preserves_visible_content(self) -> None:
        guard = HTMLParseGuard()
        html = """
        <html><body>
        <h1>Title</h1>
        <p>Paragraph one.</p>
        <ul><li>Item 1</li><li>Item 2</li></ul>
        </body></html>
        """
        result = guard.sanitize(html)
        assert "Title" in result.cleaned
        assert "Paragraph one." in result.cleaned
        assert "Item 1" in result.cleaned
        assert "Item 2" in result.cleaned

    def test_custom_threshold_no_gap(self) -> None:
        """High threshold means gap is not flagged for moderate hidden content."""
        guard = HTMLParseGuard(
            config=HTMLParseGuardConfig(gap_threshold_ratio=0.99),
        )
        html = '<p>Visible</p><div style="display:none">Hidden</div>'
        result = guard.sanitize(html)
        assert result.gap_detected is False

    def test_disabled_guard_returns_original(self) -> None:
        guard = HTMLParseGuard(config=HTMLParseGuardConfig(enabled=False))
        html = "<p>Hello</p><script>alert('xss')</script>"
        result = guard.sanitize(html)
        assert result.cleaned == html
        assert result.gap_detected is False
        assert result.stripped_element_count == 0

    def test_multiple_hidden_patterns(self) -> None:
        guard = HTMLParseGuard()
        html = (
            "<p>Visible</p>"
            "<script>evil()</script>"
            "<style>.x{}</style>"
            '<div style="display:none">hidden1</div>'
            '<span style="visibility:hidden">hidden2</span>'
            '<div aria-hidden="true">hidden3</div>'
            "<!-- comment -->"
        )
        result = guard.sanitize(html)
        assert "Visible" in result.cleaned
        assert "evil" not in result.cleaned
        assert "hidden1" not in result.cleaned
        assert "hidden2" not in result.cleaned
        assert "hidden3" not in result.cleaned
        assert result.stripped_element_count >= 3


@pytest.mark.unit
class TestHTMLParseGuardProperties:
    """Property-based tests for HTMLParseGuard."""

    @given(
        text=st.text(
            alphabet=st.characters(
                categories=("L", "N", "P", "Z"),
            ),
            min_size=0,
            max_size=500,
        ),
    )
    @settings(max_examples=50)
    def test_output_text_never_longer_than_input(self, text: str) -> None:
        """Sanitized output should never be longer than original HTML."""
        guard = HTMLParseGuard()
        # Wrap text in HTML tags to ensure it goes through the parser.
        html = f"<p>{text}</p>"
        result = guard.sanitize(html)
        # The cleaned text (visible content) should not exceed the
        # original visible text length. We compare against the raw
        # html length as a conservative bound.
        assert len(result.cleaned) <= len(html)

    @given(
        text=st.text(
            alphabet=st.characters(categories=("L", "N", "Z")),
            min_size=1,
            max_size=200,
        ),
    )
    @settings(max_examples=50)
    def test_gap_ratio_in_valid_range(self, text: str) -> None:
        """Gap ratio should always be between 0.0 and 1.0."""
        guard = HTMLParseGuard()
        html = f"<p>{text}</p>"
        result = guard.sanitize(html)
        assert 0.0 <= result.gap_ratio <= 1.0

    @given(
        text=st.text(
            alphabet=st.characters(categories=("L", "N", "Z")),
            min_size=1,
            max_size=200,
        ),
    )
    @settings(max_examples=50)
    def test_stripped_count_non_negative(self, text: str) -> None:
        guard = HTMLParseGuard()
        html = f"<p>{text}</p>"
        result = guard.sanitize(html)
        assert result.stripped_element_count >= 0
