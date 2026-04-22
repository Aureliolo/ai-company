"""Prompt eval: memory re-ranker temperature contract."""

import inspect

import pytest


@pytest.mark.unit
class TestRerankPromptContract:
    """Guard rails for the LLM memory re-ranker prompt surface."""

    def test_system_prompt_defined(self) -> None:
        """Re-ranker must declare a pinned system prompt constant."""
        import re

        from synthorg.memory.retrieval.reranking import llm_reranker

        source = inspect.getsource(llm_reranker)
        assert re.search(r"(?m)^_RERANK_SYSTEM_PROMPT\s*=", source), (
            "llm_reranker must define the ``_RERANK_SYSTEM_PROMPT`` constant"
        )

    def test_temperature_is_zero(self) -> None:
        """Re-ranker must call the provider with temperature=0.0.

        Without this pin the reranker becomes non-deterministic across
        CI shards, which poisons the cache keys computed from
        ``(query_text, candidate_ids)`` -- cache entries pinned to one
        ranking would then return different orderings on re-computation.

        Checked both ways:

        1. **Definition**: a ``temperature=0.0`` binding appears in the
           module source (regex match on the CompletionConfig construction).
        2. **Usage**: the module exposes a ``_RERANK_COMPLETION_CONFIG``
           instance whose ``temperature`` attribute actually equals
           ``0.0`` at runtime. Source matching alone can be fooled by
           dead code or a commented example; runtime inspection proves
           the config object the reranker passes to
           ``self._provider.complete(..., config=...)`` is the pinned one.
        """
        import re

        from synthorg.memory.retrieval.reranking import llm_reranker

        source = inspect.getsource(llm_reranker)
        assert re.search(r"temperature\s*=\s*0(?:\.0+)?", source), (
            "llm_reranker must pin temperature=0.0 on its "
            "CompletionConfig for deterministic re-ranking"
        )
        runtime_config = llm_reranker._RERANK_COMPLETION_CONFIG
        assert runtime_config.temperature == 0.0, (
            "_RERANK_COMPLETION_CONFIG.temperature must equal 0.0 at runtime; "
            f"got {runtime_config.temperature!r}"
        )
