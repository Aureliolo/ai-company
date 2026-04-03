"""Tests for BM25 sparse encoder."""

import pytest
from hypothesis import given
from hypothesis import strategies as st
from pydantic import ValidationError

from synthorg.memory.sparse import (
    BM25Tokenizer,
    SparseVector,
)

# ── SparseVector model ────────────────────────────────────────────


@pytest.mark.unit
class TestSparseVector:
    def test_empty_vector(self) -> None:
        vec = SparseVector(indices=(), values=())
        assert vec.indices == ()
        assert vec.values == ()

    def test_frozen(self) -> None:
        vec = SparseVector(indices=(1, 2), values=(1.0, 2.0))
        with pytest.raises(ValidationError, match="frozen"):
            vec.indices = (3,)  # type: ignore[misc]

    def test_length_mismatch_rejected(self) -> None:
        with pytest.raises(
            ValueError, match="indices and values must have equal length"
        ):
            SparseVector(indices=(1, 2), values=(1.0,))

    def test_negative_values_rejected(self) -> None:
        with pytest.raises(ValueError, match="values must be positive"):
            SparseVector(indices=(1,), values=(-0.5,))

    def test_zero_values_rejected(self) -> None:
        with pytest.raises(ValueError, match="values must be positive"):
            SparseVector(indices=(1,), values=(0.0,))

    def test_negative_indices_rejected(self) -> None:
        with pytest.raises(ValueError, match="non-negative"):
            SparseVector(indices=(-1,), values=(1.0,))

    def test_unsorted_indices_rejected(self) -> None:
        with pytest.raises(ValueError, match="sorted"):
            SparseVector(indices=(5, 3), values=(1.0, 2.0))

    def test_duplicate_indices_rejected(self) -> None:
        with pytest.raises(ValueError, match="sorted"):
            SparseVector(indices=(3, 3), values=(1.0, 2.0))

    def test_is_empty(self) -> None:
        assert SparseVector(indices=(), values=()).is_empty
        assert not SparseVector(indices=(1,), values=(1.0,)).is_empty


# ── BM25Tokenizer.tokenize ───────────────────────────────────────


@pytest.mark.unit
class TestTokenize:
    def test_basic_tokenization(self) -> None:
        tokenizer = BM25Tokenizer()
        tokens = tokenizer.tokenize("Hello World")
        assert tokens == ("hello", "world")

    def test_empty_string(self) -> None:
        tokenizer = BM25Tokenizer()
        assert tokenizer.tokenize("") == ()

    def test_whitespace_only(self) -> None:
        tokenizer = BM25Tokenizer()
        assert tokenizer.tokenize("   \t\n  ") == ()

    def test_punctuation_splitting(self) -> None:
        tokenizer = BM25Tokenizer()
        tokens = tokenizer.tokenize("hello, world! foo-bar_baz")
        # Splits on non-word chars and underscores
        assert "hello" in tokens
        assert "world" in tokens
        assert "foo" in tokens
        assert "bar" in tokens
        assert "baz" in tokens

    def test_stop_words_excluded(self) -> None:
        tokenizer = BM25Tokenizer()
        tokens = tokenizer.tokenize("the agent is in a task")
        assert "the" not in tokens
        assert "is" not in tokens
        assert "in" not in tokens
        assert "a" not in tokens
        assert "agent" in tokens
        assert "task" in tokens

    def test_stop_words_can_be_disabled(self) -> None:
        tokenizer = BM25Tokenizer(remove_stop_words=False)
        tokens = tokenizer.tokenize("the agent is in a task")
        assert "the" in tokens
        assert "is" in tokens

    def test_unicode_normalization_and_casefold(self) -> None:
        tokenizer = BM25Tokenizer()
        # casefold: sharp-s -> "ss"; NFKC: fullwidth chars normalized
        tokens_ss = tokenizer.tokenize("Stra\u00dfe agent")
        assert "strasse" in tokens_ss
        assert "agent" in tokens_ss
        # Verify casefold unifies with plain ASCII form
        tokens_plain = tokenizer.tokenize("STRASSE agent")
        assert "strasse" in tokens_plain

    def test_numbers_preserved(self) -> None:
        tokenizer = BM25Tokenizer()
        tokens = tokenizer.tokenize("error code 404")
        assert "error" in tokens
        assert "code" in tokens
        assert "404" in tokens

    def test_duplicate_tokens_preserved(self) -> None:
        tokenizer = BM25Tokenizer()
        tokens = tokenizer.tokenize("test test test")
        assert tokens.count("test") == 3


# ── BM25Tokenizer.encode ─────────────────────────────────────────


@pytest.mark.unit
class TestEncode:
    def test_empty_string_returns_empty_vector(self) -> None:
        tokenizer = BM25Tokenizer()
        vec = tokenizer.encode("")
        assert vec.is_empty

    def test_stop_words_only_returns_empty(self) -> None:
        tokenizer = BM25Tokenizer()
        vec = tokenizer.encode("the a is in on")
        assert vec.is_empty

    def test_deterministic(self) -> None:
        tokenizer = BM25Tokenizer()
        vec1 = tokenizer.encode("hello world")
        vec2 = tokenizer.encode("hello world")
        assert vec1 == vec2

    def test_different_texts_differ(self) -> None:
        tokenizer = BM25Tokenizer()
        vec1 = tokenizer.encode("authentication tokens")
        vec2 = tokenizer.encode("database migrations")
        assert vec1 != vec2

    def test_indices_sorted(self) -> None:
        tokenizer = BM25Tokenizer()
        vec = tokenizer.encode("zebra apple mango banana")
        assert list(vec.indices) == sorted(vec.indices)

    def test_all_values_positive(self) -> None:
        tokenizer = BM25Tokenizer()
        vec = tokenizer.encode("hello world test")
        assert all(v > 0 for v in vec.values)

    def test_repeated_token_increases_tf(self) -> None:
        tokenizer = BM25Tokenizer()
        vec_single = tokenizer.encode("error")
        vec_triple = tokenizer.encode("error error error")
        # Same index, but higher TF value for repeated token
        assert vec_single.indices == vec_triple.indices
        assert vec_triple.values[0] > vec_single.values[0]

    def test_tf_values_are_counts(self) -> None:
        tokenizer = BM25Tokenizer()
        vec = tokenizer.encode("test test test unique")
        # With 2 unique tokens: "test" (3x) and "unique" (1x)
        values_sorted = sorted(vec.values, reverse=True)
        assert values_sorted[0] == 3.0
        assert values_sorted[1] == 1.0

    def test_non_empty_text_produces_non_empty_vector(self) -> None:
        tokenizer = BM25Tokenizer()
        vec = tokenizer.encode("meaningful content here")
        assert not vec.is_empty
        assert len(vec.indices) > 0
        assert len(vec.values) > 0

    def test_indices_are_non_negative(self) -> None:
        tokenizer = BM25Tokenizer()
        vec = tokenizer.encode("hello world test content")
        assert all(idx >= 0 for idx in vec.indices)


# ── Property-based tests ─────────────────────────────────────────


@pytest.mark.unit
class TestSparseProperties:
    @given(
        text=st.text(
            min_size=1,
            alphabet=st.characters(categories=("L",)),  # type: ignore[arg-type]
        )
    )
    def test_encoding_is_deterministic(self, text: str) -> None:
        tokenizer = BM25Tokenizer(remove_stop_words=False)
        assert tokenizer.encode(text) == tokenizer.encode(text)

    @given(
        text=st.text(
            min_size=1,
            alphabet=st.characters(categories=("L",)),  # type: ignore[arg-type]
        )
    )
    def test_non_empty_alpha_produces_non_empty_vector(self, text: str) -> None:
        tokenizer = BM25Tokenizer(remove_stop_words=False)
        vec = tokenizer.encode(text)
        assert not vec.is_empty

    @given(
        text=st.text(
            min_size=1,
            alphabet=st.characters(categories=("L",)),  # type: ignore[arg-type]
        )
    )
    def test_indices_always_sorted(self, text: str) -> None:
        tokenizer = BM25Tokenizer(remove_stop_words=False)
        vec = tokenizer.encode(text)
        assert list(vec.indices) == sorted(vec.indices)

    @given(
        text=st.text(
            min_size=1,
            alphabet=st.characters(categories=("L",)),  # type: ignore[arg-type]
        )
    )
    def test_values_always_positive(self, text: str) -> None:
        tokenizer = BM25Tokenizer(remove_stop_words=False)
        vec = tokenizer.encode(text)
        if not vec.is_empty:
            assert all(v > 0 for v in vec.values)

    @given(
        text=st.text(
            min_size=1,
            alphabet=st.characters(categories=("L",)),  # type: ignore[arg-type]
        )
    )
    def test_indices_always_non_negative(self, text: str) -> None:
        tokenizer = BM25Tokenizer(remove_stop_words=False)
        vec = tokenizer.encode(text)
        if not vec.is_empty:
            assert all(idx >= 0 for idx in vec.indices)
