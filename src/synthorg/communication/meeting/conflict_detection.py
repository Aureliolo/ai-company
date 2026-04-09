"""Conflict detection strategies for meeting protocols.

Implements multiple conflict detection strategies for the
StructuredPhasesProtocol to determine whether discussion is needed
based on leader responses during conflict-check phase.

Strategies include:
- Keyword matching (default, simple and fast)
- Structured JSON comparison (zero-cost, deterministic)
- Judgment parsing from LLM responses
- Hybrid approaches combining multiple strategies
"""

import json
import re
from typing import Any

from synthorg.observability import get_logger

logger = get_logger(__name__)

_MIN_POSITIONS_FOR_CONFLICT: int = 2


class KeywordConflictDetector:
    """Default conflict detector using keyword matching.

    Looks for the string "CONFLICTS: YES" (case-insensitive) in
    the agent response. Allows flexible whitespace around the colon.
    This is the simplest approach and works well when agents are
    prompted to include this marker.
    """

    def detect(self, response_content: str) -> bool:
        """Detect conflicts via keyword matching.

        Looks for "CONFLICTS" followed by optional whitespace, colon,
        optional whitespace, and "YES" (all case-insensitive).

        Args:
            response_content: The conflict-check agent response text.

        Returns:
            True if conflict marker is found, False otherwise.
        """
        content_upper = response_content.upper()
        # Match "CONFLICTS" with optional space, ":", optional space, "YES"
        return bool(re.search(r"CONFLICTS\s*:\s*YES", content_upper))


class StructuredComparisonDetector:
    """Compare structured fields in agent responses.

    Expects response_content to contain JSON with a "positions" or
    "position" field containing agent positions. Parses all positions,
    compares them field-by-field. Reports conflict if any top-level
    field values differ between positions.

    Zero cost, deterministic, and does not require external calls.
    """

    def detect(self, response_content: str) -> bool:
        """Detect conflicts via structured JSON field comparison.

        Attempts to extract JSON from response_content, then compares
        all agent positions field-by-field. If any top-level field
        value differs between any two positions, returns True.

        Args:
            response_content: The conflict-check agent response (should contain JSON).

        Returns:
            True if conflicts (differing field values) detected, False otherwise.
        """
        try:
            # Try to extract JSON from response
            parsed = self._extract_json(response_content)
            if parsed is None:
                return False

            positions = self._get_positions(parsed)
            if not positions or len(positions) < _MIN_POSITIONS_FOR_CONFLICT:
                return False

            # Compare all pairs of positions field-by-field
            return self._has_field_conflicts(positions)
        except Exception:
            # If JSON parsing or comparison fails, no conflict detected
            # (safe fallback: don't assume conflict on parsing error)
            return False

    def _extract_json(self, text: str) -> dict[str, Any] | None:
        """Extract JSON object from text.

        Looks for JSON object or array patterns and parses.
        """
        # Try parsing entire text as JSON first (works for clean JSON)
        try:
            parsed = json.loads(text)
            if isinstance(parsed, dict):
                return parsed
        except json.JSONDecodeError:
            pass

        # Try to find JSON object in curly braces (first one)
        json_pattern = r"\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}"
        match = re.search(json_pattern, text, re.DOTALL)
        if match:
            try:
                parsed = json.loads(match.group())
                if isinstance(parsed, dict):
                    return parsed
            except json.JSONDecodeError:
                pass

        return None

    def _get_positions(
        self,
        data: dict[str, Any],
    ) -> list[dict[str, Any]]:
        """Extract positions from parsed JSON.

        Looks for "positions" (plural) or "position" (singular) fields.
        """
        if "positions" in data:
            positions = data["positions"]
            if isinstance(positions, list):
                return [p for p in positions if isinstance(p, dict)]

        if "position" in data:
            position = data["position"]
            if isinstance(position, dict):
                return [position]

        # If neither field exists, try list values that look like positions
        positions_list = []
        for value in data.values():
            if isinstance(value, list):
                positions_list.extend(item for item in value if isinstance(item, dict))

        return positions_list

    def _has_field_conflicts(
        self,
        positions: list[dict[str, Any]],
    ) -> bool:
        """Check if any top-level field differs between positions.

        Compares all pairs of positions. Returns True if any position
        has a different value for any top-level field compared to
        another position.
        """
        for i in range(len(positions)):
            for j in range(i + 1, len(positions)):
                pos_a = positions[i]
                pos_b = positions[j]

                # Collect all field keys
                all_keys = set(pos_a.keys()) | set(pos_b.keys())

                for key in all_keys:
                    val_a = pos_a.get(key)
                    val_b = pos_b.get(key)

                    # If values differ, conflict detected
                    if val_a != val_b:
                        return True

        return False


class LlmJudgeDetector:
    """Parse conflict judgment from LLM-structured responses.

    Expects the leader's response to contain a structured judgment,
    typically in JSON format with a "conflicts" or "judgment" field.

    The leader is prompted separately (via orchestrator) to provide
    structured judgment; this detector just parses the result.
    """

    def detect(self, response_content: str) -> bool:
        """Detect conflicts via LLM judgment parsing.

        Looks for JSON with a "conflicts" boolean field, or parses
        "JUDGE: CONFLICT" / "JUDGE: NO_CONFLICT" markers.
        Falls back to keyword detection if structured format not found.

        Args:
            response_content: The leader's structured judgment response.

        Returns:
            True if judgment indicates conflicts, False otherwise.
        """
        # Try JSON parsing first
        try:
            parsed = self._extract_json(response_content)
            if parsed:
                # Check for "conflicts" field (boolean)
                if "conflicts" in parsed:
                    conflicts = parsed["conflicts"]
                    if isinstance(conflicts, bool):
                        return conflicts

                # Check for "judgment" field
                if "judgment" in parsed:
                    judgment = parsed["judgment"]
                    if isinstance(judgment, str):
                        return "conflict" in judgment.lower()
        except Exception as e:
            logger.debug("Failed to parse response for judge conflicts", exc_info=e)

        # Fallback to keyword markers
        content_upper = response_content.upper()
        if "JUDGE: CONFLICT" in content_upper:
            return True
        if "JUDGE: NO_CONFLICT" in content_upper:
            return False

        # Fallback to generic conflict keyword
        return "CONFLICTS: YES" in content_upper

    def _extract_json(self, text: str) -> dict[str, Any] | None:
        """Extract JSON object from text."""
        json_pattern = r"\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}"
        match = re.search(json_pattern, text, re.DOTALL)
        if match:
            try:
                return json.loads(match.group())
            except json.JSONDecodeError:
                pass

        try:
            return json.loads(text)
        except json.JSONDecodeError:
            pass

        return None


class EmbeddingSimilarityDetector:
    """Placeholder for embedding-based similarity detection.

    This detector is a stub that always returns False. It exists to
    document the design for future implementation when embedding
    infrastructure is available.

    In the future, this would:
    - Extract position texts from response
    - Compute pairwise cosine similarity
    - Report conflict if any pair falls below threshold
    """

    def __init__(self, *, similarity_threshold: float = 0.7) -> None:
        """Initialize with similarity threshold.

        Args:
            similarity_threshold: Cosine similarity threshold below which
                positions are considered conflicting (default 0.7).
        """
        self.similarity_threshold = similarity_threshold

    def detect(self, _response_content: str) -> bool:
        """Placeholder: always returns False.

        Once embedding infrastructure is available, this will:
        1. Extract position texts from _response_content
        2. Compute embedding vectors for each position
        3. Calculate pairwise cosine similarity
        4. Return True if any pair has similarity < threshold

        Args:
            response_content: The conflict-check response.

        Returns:
            Always False (stub implementation).
        """
        # Stub: embedding infrastructure not yet available
        return False


class HybridDetector:
    """Embedding first, keyword fallback for ambiguous zone.

    Uses EmbeddingSimilarityDetector with a wide band (0.3-0.7).
    If similarity is in the ambiguous zone, falls back to
    KeywordConflictDetector for final verdict.

    This allows deterministic fallback when embeddings are uncertain.
    """

    def __init__(self, *, similarity_threshold: float = 0.7) -> None:
        """Initialize with similarity threshold.

        Args:
            similarity_threshold: Cosine similarity threshold (default 0.7).
        """
        self.embedding_detector = EmbeddingSimilarityDetector(
            similarity_threshold=similarity_threshold,
        )
        self.keyword_detector = KeywordConflictDetector()

    def detect(self, response_content: str) -> bool:
        """Detect conflicts using embedding + keyword fallback.

        Currently delegates to KeywordConflictDetector (since embedding
        detector is a stub). Once embeddings are available, will:
        1. Try embedding similarity
        2. If in ambiguous zone, use keyword fallback

        Args:
            response_content: The conflict-check response.

        Returns:
            True if conflicts detected via either strategy.
        """
        # For now, just use keyword detection
        # (embedding_detector is a stub that always returns False)
        return self.keyword_detector.detect(response_content)


class AutoDetector:
    """Selects detection strategy based on response content format.

    Inspects the response to determine its format:
    - If response is valid JSON with "position" or "positions" field:
      uses StructuredComparisonDetector
    - Otherwise: uses KeywordConflictDetector (default fallback)

    This allows responses to choose their optimal detection method
    implicitly based on content structure.
    """

    def __init__(self) -> None:
        """Initialize with both detector strategies."""
        self.structured_detector = StructuredComparisonDetector()
        self.keyword_detector = KeywordConflictDetector()

    def detect(self, response_content: str) -> bool:
        """Detect conflicts using format-aware strategy selection.

        Checks if response contains JSON with "position" or "positions"
        field. If so, uses StructuredComparisonDetector. Otherwise uses
        KeywordConflictDetector.

        Args:
            response_content: The conflict-check response.

        Returns:
            True if conflicts detected via selected strategy.
        """
        # Try to detect if response is structured JSON
        if self._is_structured_json(response_content):
            return self.structured_detector.detect(response_content)

        # Fall back to keyword detection
        return self.keyword_detector.detect(response_content)

    def _is_structured_json(self, text: str) -> bool:
        """Check if text is JSON with position field."""
        try:
            json_pattern = r"\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}"
            match = re.search(json_pattern, text, re.DOTALL)
            if match:
                parsed = json.loads(match.group())
                if isinstance(parsed, dict):
                    return "position" in parsed or "positions" in parsed
        except Exception as e:
            logger.debug("Failed to parse position from text", exc_info=e)

        return False
