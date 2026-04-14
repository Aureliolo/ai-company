"""HTML parse guard for tool output sanitization.

Parses HTML-returning tool output with ``lxml``, strips hidden
injection vectors (scripts, styles, hidden elements), and detects
render-gap attacks where rendered text differs substantially from
raw visible HTML content.

This is a standalone post-processor called from ``ToolInvoker``,
not a middleware.
"""

import re
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from synthorg.observability import get_logger
from synthorg.observability.events.tool import (
    TOOL_HTML_PARSE_ERROR,
    TOOL_HTML_PARSE_GAP_DETECTED,
)

logger = get_logger(__name__)

# Patterns that indicate the content is likely HTML.
_HTML_TAG_PATTERN = re.compile(r"<[a-zA-Z][^>]*>")

# CSS patterns for hidden elements.
_HIDDEN_STYLE_PATTERNS = (
    re.compile(r"display\s*:\s*none", re.IGNORECASE),
    re.compile(r"visibility\s*:\s*hidden", re.IGNORECASE),
)

# Tags to strip entirely (content and all).
_STRIP_TAGS = frozenset(
    {
        "script",
        "style",
        "noscript",
        "iframe",
        "object",
        "embed",
        "applet",
    }
)

# Event handler attributes to strip from all elements.
_EVENT_HANDLER_PREFIXES = frozenset(
    {
        "onclick",
        "ondblclick",
        "onmousedown",
        "onmouseup",
        "onmouseover",
        "onmousemove",
        "onmouseout",
        "onkeypress",
        "onkeydown",
        "onkeyup",
        "onfocus",
        "onblur",
        "onsubmit",
        "onreset",
        "onselect",
        "onchange",
        "onload",
        "onerror",
        "onresize",
        "onscroll",
        "onunload",
        "onabort",
        "oninput",
        "oncontextmenu",
        "ondrag",
        "ondrop",
        "onpaste",
        "formaction",
    }
)


class HTMLParseGuardConfig(BaseModel):
    """Configuration for the HTML parse guard.

    Attributes:
        enabled: Whether sanitization is active.
        gap_threshold_ratio: Ratio of hidden-to-total content above
            which ``gap_detected`` is set to ``True``.
    """

    model_config = ConfigDict(frozen=True, allow_inf_nan=False)

    enabled: bool = Field(
        default=True,
        description="Whether HTML sanitization is active",
    )
    gap_threshold_ratio: float = Field(
        default=0.05,
        ge=0.0,
        le=1.0,
        description="Hidden-to-total content ratio threshold for gap detection",
    )


class HTMLSanitizeResult(BaseModel):
    """Result of HTML sanitization.

    Attributes:
        cleaned: Sanitized output text.
        gap_detected: Whether a significant render gap was found.
        gap_ratio: Ratio of hidden content to total content.
        stripped_element_count: Number of elements stripped.
    """

    model_config = ConfigDict(frozen=True, allow_inf_nan=False)

    cleaned: str = Field(description="Sanitized output text")
    gap_detected: bool = Field(
        default=False,
        description="Whether a significant render gap was found",
    )
    gap_ratio: float = Field(
        default=0.0,
        ge=0.0,
        le=1.0,
        description="Hidden-to-total content ratio",
    )
    stripped_element_count: int = Field(
        default=0,
        ge=0,
        description="Number of elements stripped",
    )


def _passthrough_result(content: str) -> HTMLSanitizeResult:
    """Return an unchanged result for non-HTML or disabled guard."""
    return HTMLSanitizeResult(
        cleaned=content,
        gap_detected=False,
        gap_ratio=0.0,
        stripped_element_count=0,
    )


class HTMLParseGuard:
    """Sanitize HTML tool output by stripping hidden injection vectors.

    Strips ``<script>``, ``<style>``, ``<noscript>`` tags, HTML
    comments, and elements with ``display:none``,
    ``visibility:hidden``, or ``aria-hidden="true"`` attributes.

    Detects render-gap attacks by comparing visible text length
    before and after stripping hidden content.

    Args:
        config: Guard configuration. Defaults to enabled with 5%
            gap threshold.
    """

    def __init__(
        self,
        config: HTMLParseGuardConfig | None = None,
    ) -> None:
        self._config = config or HTMLParseGuardConfig()

    def sanitize(self, raw: str) -> HTMLSanitizeResult:
        """Sanitize HTML content, stripping hidden injection vectors.

        Args:
            raw: Raw tool output (may or may not be HTML).

        Returns:
            Sanitization result with cleaned content and gap metadata.
        """
        if not self._config.enabled:
            return _passthrough_result(raw)

        if not raw or not _HTML_TAG_PATTERN.search(raw):
            return _passthrough_result(raw)

        try:
            return self._sanitize_html(raw)
        except MemoryError, RecursionError:
            raise
        except Exception as exc:
            logger.warning(
                TOOL_HTML_PARSE_ERROR,
                error=str(exc),
                error_type=type(exc).__name__,
                content_length=len(raw),
                exc_info=True,
            )
            # Return safe empty result instead of raw attacker-
            # controlled content.
            return HTMLSanitizeResult(
                cleaned="",
                gap_detected=True,
                gap_ratio=1.0,
                stripped_element_count=0,
            )

    def _sanitize_html(self, raw: str) -> HTMLSanitizeResult:
        """Parse and sanitize HTML content using lxml."""
        from lxml import html as lxml_html  # noqa: PLC0415

        doc = lxml_html.fromstring(raw)
        # Capture original text before stripping (single parse).
        original_text = doc.text_content().strip()  # type: ignore[attr-defined]
        stripped_count = self._strip_dangerous_elements(doc)
        cleaned_text = doc.text_content().strip()  # type: ignore[attr-defined]
        gap_ratio = self._compute_gap_ratio(original_text, cleaned_text)
        gap_detected = gap_ratio > self._config.gap_threshold_ratio

        if gap_detected:
            logger.warning(
                TOOL_HTML_PARSE_GAP_DETECTED,
                gap_ratio=gap_ratio,
                threshold=self._config.gap_threshold_ratio,
                stripped_count=stripped_count,
                hidden_chars=max(0, len(original_text) - len(cleaned_text)),
            )

        return HTMLSanitizeResult(
            cleaned=cleaned_text,
            gap_detected=gap_detected,
            gap_ratio=gap_ratio,
            stripped_element_count=stripped_count,
        )

    @staticmethod
    def _strip_event_handlers(doc: Any) -> int:
        """Strip event handler attributes from all elements."""
        stripped = 0
        for element in doc.iter():
            if not hasattr(element, "tag") or not isinstance(element.tag, str):
                continue
            for attr in list(element.attrib):
                if attr.lower() in _EVENT_HANDLER_PREFIXES:
                    del element.attrib[attr]
                    stripped += 1
        return stripped

    @staticmethod
    def _strip_dangerous_elements(doc: Any) -> int:
        """Strip scripts, styles, comments, and hidden elements.

        Returns the count of stripped elements.
        """
        from lxml import etree  # noqa: PLC0415

        stripped = 0

        for tag in _STRIP_TAGS:
            for element in doc.iter(tag):
                element.drop_tree()
                stripped += 1

        for comment in doc.iter(etree.Comment):
            comment.drop_tree()

        # Strip SVG script injection vectors.
        for element in doc.iter("{http://www.w3.org/2000/svg}script"):
            element.drop_tree()
            stripped += 1

        stripped += HTMLParseGuard._strip_event_handlers(doc)
        stripped += HTMLParseGuard._strip_hidden_elements(doc)

        return stripped

    @staticmethod
    def _strip_hidden_elements(doc: Any) -> int:
        """Strip elements hidden via attributes or CSS."""
        elements_to_drop: list[object] = []
        for element in doc.iter():
            if not hasattr(element, "tag") or not isinstance(element.tag, str):
                continue
            if element.get("hidden") is not None:
                elements_to_drop.append(element)
                continue
            if element.get("aria-hidden", "").lower() == "true":
                elements_to_drop.append(element)
                continue
            style = element.get("style", "")
            if style and any(p.search(style) for p in _HIDDEN_STYLE_PATTERNS):
                elements_to_drop.append(element)

        dropped = 0
        for element in elements_to_drop:
            if getattr(element, "getparent", lambda: None)() is not None:
                element.drop_tree()  # type: ignore[attr-defined]
                dropped += 1

        return dropped

    @staticmethod
    def _compute_gap_ratio(original: str, cleaned: str) -> float:
        """Compute the ratio of hidden content to total content."""
        original_len = len(original) or 1
        hidden_len = max(0, original_len - len(cleaned))
        return min(hidden_len / original_len, 1.0)
