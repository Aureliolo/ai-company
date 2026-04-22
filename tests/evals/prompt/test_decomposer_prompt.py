"""Prompt eval: decomposer temperature contract."""

import inspect

import pytest


@pytest.mark.unit
class TestDecomposerPromptContract:
    """Guard rails for the LLM criteria decomposer prompt surface."""

    def test_temperature_is_zero(self) -> None:
        """Decomposer must run at temperature=0 for deterministic splits."""
        import re

        from synthorg.engine.quality.decomposers.llm import (
            LLMCriteriaDecomposer,
        )

        source = inspect.getsource(LLMCriteriaDecomposer)
        # Require ``temperature`` bound to exactly ``0`` / ``0.0`` via
        # ``=`` or ``:`` (dataclass / Field / keyword argument forms).
        # Raw substring matching would succeed on a comment that
        # merely mentions ``temperature=0.0`` without binding it.
        pattern = r"temperature\s*(?::\s*[\w\[\], ]*)?\s*=\s*0(?:\.0+)?\b"
        assert re.search(pattern, source), (
            "LLMCriteriaDecomposer must pin temperature=0.0 "
            "(checked via a binding pattern, not substring)"
        )
