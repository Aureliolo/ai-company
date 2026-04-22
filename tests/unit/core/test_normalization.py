"""Tests for ``synthorg.core.normalization`` helpers."""

from dataclasses import dataclass

import pytest

from synthorg.core.normalization import casefold_equals, find_by_name_ci


@pytest.mark.unit
class TestCasefoldEquals:
    """``casefold_equals`` handles Unicode + whitespace."""

    def test_same_case_matches(self) -> None:
        assert casefold_equals("alice", "alice") is True

    def test_different_case_matches(self) -> None:
        assert casefold_equals("Alice", "alice") is True

    def test_whitespace_stripped(self) -> None:
        assert casefold_equals("  Alice ", "alice") is True

    def test_distinct_strings_do_not_match(self) -> None:
        assert casefold_equals("alice", "bob") is False

    def test_german_sharp_s_casefolds(self) -> None:
        # 'straße'.casefold() == 'strasse' -- lower() would keep the ß.
        assert casefold_equals("Straße", "STRASSE") is True


@pytest.mark.unit
class TestFindByNameCi:
    """``find_by_name_ci`` linear search."""

    @dataclass
    class Item:
        name: str

    def test_returns_first_match(self) -> None:
        items = (self.Item("Alice"), self.Item("Bob"))
        assert find_by_name_ci(items, "alice") is items[0]

    def test_returns_none_on_no_match(self) -> None:
        items = (self.Item("Alice"), self.Item("Bob"))
        assert find_by_name_ci(items, "eve") is None

    def test_handles_non_string_attr(self) -> None:
        @dataclass
        class Weird:
            name: int

        assert find_by_name_ci((Weird(name=1),), "1") is None

    def test_custom_name_attr(self) -> None:
        @dataclass
        class Dept:
            title: str

        items = (Dept(title="Engineering"),)
        assert find_by_name_ci(items, "engineering", name_attr="title") is items[0]

    def test_empty_iterable(self) -> None:
        assert find_by_name_ci((), "anything") is None
