"""The in-memory catalog (ADR-3): BROWSE-1 order, BROWSE-4 counts, G-3 identity."""

from __future__ import annotations

import dataclasses
from pathlib import Path

import pytest
from bookmgr import Book, Library, NullSource

from bookmgr_tui.store import Catalog, title_sort_key


@pytest.fixture
def books(mock_root: Path) -> list[Book]:
    return Library(mock_root, source=NullSource()).scan()


def like(book: Book, **changes) -> Book:
    return dataclasses.replace(book, **changes)


def test_browse_1_title_sort_ignores_leading_article() -> None:
    assert title_sort_key("The Hobbit") == title_sort_key("Hobbit")
    assert title_sort_key("A Wizard of Earthsea") == title_sort_key("wizard of earthsea")
    assert title_sort_key("An Absolutely Remarkable Thing") == title_sort_key("Absolutely Remarkable Thing")


def test_browse_1_title_sort_keeps_article_prefix_within_a_word() -> None:
    assert title_sort_key("Anathem") == title_sort_key("anathem")
    assert title_sort_key("Theory of Games") == title_sort_key("theory of games")
    assert title_sort_key("Anathem") < title_sort_key("The Hobbit") < title_sort_key("Theory of Games")


def test_browse_1_title_sort_is_case_insensitive() -> None:
    assert title_sort_key("deep work") == title_sort_key("Deep Work")


def test_browse_1_title_that_is_only_an_article_keeps_it() -> None:
    assert title_sort_key(" The ") == title_sort_key("the")
    assert title_sort_key("The") != ""


def test_browse_1_ordered_breaks_ties_by_author_then_id(books: list[Book]) -> None:
    base = books[0]
    b = like(base, id="b", title="Same", author="Zed")
    a = like(base, id="a", title="The Same", author="Abel")
    none_2 = like(base, id="2", title="same", author=None)
    none_1 = like(base, id="1", title="Same", author=None)
    ordered = Catalog([none_2, b, none_1, a]).ordered()
    assert [book.id for book in ordered] == ["a", "b", "1", "2"]


def test_browse_1_mock_library_order(books: list[Book]) -> None:
    titles = [book.title for book in Catalog(books).ordered()]
    assert titles.index("An Absolutely Remarkable Thing") < titles.index("Anathem")
    assert titles.index("The Hobbit") < titles.index("Meditations")
    assert titles == [book.title for book in Catalog(books)]


def test_catalog_duplicate_ids_raise(books: list[Book]) -> None:
    with pytest.raises(ValueError):
        Catalog([books[0], like(books[1], id=books[0].id)])


def test_catalog_get_unknown_id_returns_none(books: list[Book]) -> None:
    catalog = Catalog(books)
    assert catalog.get("no-such-id") is None
    assert catalog.get(books[3].id) is books[3]
    assert len(catalog) == 31


def test_browse_4_review_count_counts_needs_review(books: list[Book]) -> None:
    assert Catalog(books).review_count == 6
    assert Catalog().review_count == 0


def test_g_3_replace_keeps_identity_when_directory_changes(books: list[Book]) -> None:
    catalog = Catalog(books)
    hobbit = next(book for book in books if book.title == "The Hobbit")
    renamed = like(hobbit, title="There and Back Again", directory=hobbit.directory.with_name("There and Back Again"))
    catalog.replace(renamed)
    assert len(catalog) == 31
    assert catalog.get(hobbit.id) is renamed
    assert "There and Back Again" in [book.title for book in catalog.ordered()]
    assert "The Hobbit" not in [book.title for book in catalog.ordered()]


def test_replace_adds_a_new_book(books: list[Book]) -> None:
    catalog = Catalog(books[:3])
    catalog.replace(books[3])
    assert len(catalog) == 4
    assert catalog.get(books[3].id) is books[3]
