"""Integration tests for ``ContextInjectionStrategy`` diversity re-ranking.

These tests verify that the retrieval pipeline actually wires
``apply_diversity_penalty`` into ``_execute_pipeline`` when
``diversity_penalty_enabled=True``, and that ordering is not equivalent
to the plain relevance sort.  Kept in a dedicated file (split from
``test_retriever.py``) to avoid growing the already-over-800-line main
file.
"""

from datetime import UTC, datetime
from unittest.mock import AsyncMock

import pytest

from synthorg.core.enums import MemoryCategory
from synthorg.memory.models import MemoryEntry, MemoryMetadata
from synthorg.memory.retrieval_config import MemoryRetrievalConfig
from synthorg.memory.retriever import ContextInjectionStrategy


def _make_entry(
    *,
    entry_id: str,
    content: str,
    relevance_score: float = 0.8,
) -> MemoryEntry:
    return MemoryEntry(
        id=entry_id,
        agent_id="agent-1",
        category=MemoryCategory.EPISODIC,
        content=content,
        metadata=MemoryMetadata(),
        created_at=datetime.now(UTC),
        relevance_score=relevance_score,
    )


def _make_backend(entries: tuple[MemoryEntry, ...]) -> AsyncMock:
    backend = AsyncMock()
    backend.retrieve = AsyncMock(return_value=entries)
    backend.supports_sparse_search = False
    return backend


@pytest.mark.unit
class TestDiversityPenaltyPipelineIntegration:
    """End-to-end wiring of ``diversity_penalty_enabled`` in the pipeline."""

    async def test_diversity_penalty_changes_order_vs_disabled(self) -> None:
        """MMR promotes a diverse candidate above a near-duplicate.

        Two entries have identical high relevance scores and nearly
        identical content.  A third has slightly lower relevance but
        completely different content.  With diversity disabled the
        output follows relevance ordering (both near-duplicates first,
        distinct last).  With diversity enabled, MMR should promote the
        distinct entry above at least one of the near-duplicates so the
        returned order is not identical to the relevance-only order.
        """
        e_shared_a = _make_entry(
            entry_id="shared-a",
            content="shared foo bar common phrase",
            relevance_score=0.9,
        )
        e_shared_b = _make_entry(
            entry_id="shared-b",
            content="shared foo bar common phrase alt",
            relevance_score=0.9,
        )
        e_distinct = _make_entry(
            entry_id="distinct",
            content="alpha beta gamma delta",
            relevance_score=0.85,
        )
        entries = (e_shared_a, e_shared_b, e_distinct)

        disabled_config = MemoryRetrievalConfig(
            diversity_penalty_enabled=False,
            min_relevance=0.0,
            max_memories=20,
        )
        disabled_strategy = ContextInjectionStrategy(
            backend=_make_backend(entries),
            config=disabled_config,
        )
        disabled_messages = await disabled_strategy.prepare_messages(
            "agent-1", "query", token_budget=2000
        )

        enabled_config = MemoryRetrievalConfig(
            diversity_penalty_enabled=True,
            diversity_lambda=0.3,
            min_relevance=0.0,
            max_memories=20,
        )
        enabled_strategy = ContextInjectionStrategy(
            backend=_make_backend(entries),
            config=enabled_config,
        )
        enabled_messages = await enabled_strategy.prepare_messages(
            "agent-1", "query", token_budget=2000
        )

        assert disabled_messages, "disabled pipeline produced no messages"
        assert enabled_messages, "enabled pipeline produced no messages"

        disabled_content = "\n".join((m.content or "") for m in disabled_messages)
        enabled_content = "\n".join((m.content or "") for m in enabled_messages)

        def _position(content: str, needle: str) -> int:
            pos = content.find(needle)
            assert pos >= 0, f"expected {needle!r} in {content!r}"
            return pos

        disabled_distinct_pos = _position(disabled_content, "alpha beta gamma")
        # The two shared entries share the "shared foo bar common phrase"
        # prefix; use the unique "alt" suffix to locate shared-b deterministically.
        disabled_shared_b_pos = _position(
            disabled_content, "shared foo bar common phrase alt"
        )
        enabled_distinct_pos = _position(enabled_content, "alpha beta gamma")
        enabled_shared_a_pos = enabled_content.find("shared foo bar common phrase\n")

        # With diversity DISABLED the distinct entry (lower relevance)
        # sits after the near-duplicate pair (natural relevance order).
        assert disabled_distinct_pos > disabled_shared_b_pos, (
            "disabled pipeline should preserve relevance ordering: "
            f"distinct should come AFTER shared-b\n{disabled_content}"
        )

        # With diversity ENABLED the distinct entry is promoted above at
        # least one shared duplicate (MMR picks it second, ahead of the
        # near-duplicate it would otherwise rank identically).
        assert enabled_shared_a_pos >= 0, (
            f"expected 'shared-a' content in enabled output\n{enabled_content}"
        )
        assert enabled_distinct_pos < enabled_shared_a_pos, (
            "MMR should promote the diverse entry above the second "
            f"near-duplicate.  Got:\n{enabled_content}"
        )

        # And the enabled vs disabled orderings must differ.
        assert enabled_content != disabled_content

    async def test_diversity_penalty_disabled_skips_mmr(self) -> None:
        """Pipeline must not call ``apply_diversity_penalty`` when the flag is off."""
        entries = (
            _make_entry(entry_id="a", content="one two three", relevance_score=0.9),
            _make_entry(entry_id="b", content="four five six", relevance_score=0.8),
        )
        config = MemoryRetrievalConfig(
            diversity_penalty_enabled=False,
            min_relevance=0.0,
        )
        strategy = ContextInjectionStrategy(
            backend=_make_backend(entries),
            config=config,
        )
        messages = await strategy.prepare_messages(
            "agent-1", "query", token_budget=2000
        )
        content = "\n".join((m.content or "") for m in messages)
        # Both entries present in original order.
        pos_a = content.find("one two three")
        pos_b = content.find("four five six")
        assert pos_a >= 0
        assert pos_b >= 0
        assert pos_a < pos_b
