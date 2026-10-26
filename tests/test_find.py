"""FIND: search (FIND-1, 2, 5, 6), in the store and through the browser."""

from __future__ import annotations

import dataclasses
from pathlib import Path

import pytest
from bookmgr import Book, Library, NullSource
from textual.widgets import Input, Static

from bookmgr_tui.app import BookmgrApp
from bookmgr_tui.store import BookRow, Catalog, match_summary, matched_fields, matches
from bookmgr_tui.widgets.book_table import BookTable


def rows(books) -> list[BookRow]:
    return [BookRow(book) for book in books]


@pytest.fixture
def catalog(mock_root: Path) -> Catalog:
    return Catalog(Library(mock_root, source=NullSource()).scan())


def titles(books: list[Book]) -> list[str]:
    return [book.title for book in books]


def test_find_1_matches_title_or_author_ignoring_case(catalog: Catalog) -> None:
    assert titles(catalog.search("DUNE")) == ["Children of Dune", "Dune", "Dune Messiah"]
    assert titles(catalog.search("le guin")) == ["The Left Hand of Darkness", "A Wizard of Earthsea"]


def test_find_1_isbn_matches_with_or_without_hyphens_and_spaces(catalog: Catalog) -> None:
    for query in ("9798900000022", "979-8-9000-0002-2", "979 89000 00022", "00000022"):
        assert titles(catalog.search(query)) == ["Dune"], query


def test_find_1_blank_query_matches_every_book(catalog: Catalog) -> None:
    assert catalog.search("") == catalog.ordered()
    assert catalog.search("   ") == catalog.ordered()


def test_find_1_book_without_author_or_isbn_matches_on_title(catalog: Catalog) -> None:
    book = next(book for book in catalog if book.title == "Quarterly Garden Planner")
    assert matches(book, "garden")
    assert not matches(book, "-")  # punctuation alone is not an ISBN search


def test_find_7_matched_fields_names_each_field_hit(catalog: Catalog) -> None:
    dune = next(book for book in catalog if book.title == "Dune")
    assert matched_fields(dune, "dune") == ("title",)
    assert matched_fields(dune, "her") == ("author",)
    assert matched_fields(dune, "0022") == ("ISBN",)
    assert matched_fields(dune, "zzz") == ()
    assert matched_fields(dune, "") == ()


def test_find_7_summary_counts_books_once_and_each_field(catalog: Catalog) -> None:
    # "an" is in both title and author of e.g. "Anathem" by Neal Stephenson.
    books = catalog.search("an")
    both = [book for book in books if matched_fields(book, "an") == ("title", "author")]
    assert both, "the mock library should have a book matching on title and author"
    summary = match_summary(books, "an")
    title, author = (sum(field in matched_fields(b, "an") for b in books) for field in ("title", "author"))
    assert summary == f"{len(books)} books · {title} title · {author} author · 0 ISBN"
    assert title + author > len(books)


def test_find_7_summary_singular_and_isbn(catalog: Catalog) -> None:
    assert match_summary(catalog.search("979-8900-000022"), "979-8900-000022") == (
        "1 book · 0 title · 0 author · 1 ISBN"
    )


async def loaded(app: BookmgrApp, pilot) -> BookTable:
    await app.workers.wait_for_complete()
    await pilot.pause()
    return app.screen.query_one(BookTable)


async def search_for(pilot, text: str) -> None:
    await pilot.press("slash", *text)
    await pilot.pause()


def listed(table: BookTable) -> list[str]:
    return [str(table.get_row(key)[1]) for key in table.rows]


def selected_title(app: BookmgrApp) -> str | None:
    book_id = app.screen.query_one(BookTable).selected_id
    book = app.catalog.get(book_id) if app.catalog and book_id else None
    return book.title if book else None


async def test_find_1_typing_narrows_the_list_and_counts_it(mock_root: Path) -> None:
    app = BookmgrApp(library=mock_root)
    async with app.run_test(size=(120, 30)) as pilot:
        table = await loaded(app, pilot)
        box = app.screen.query_one("#search", Input)
        bar = app.screen.query_one("#search-bar")
        assert not bar.display
        await search_for(pilot, "dune")
        assert bar.display and box.has_focus
        assert listed(table) == ["Children of Dune", "Dune", "Dune Messiah"]
        assert str(app.screen.query_one("#status", Static).render()) == "3 of 31 books · 6 need review · by title"


async def test_find_1_enter_returns_to_the_list_and_the_box_stays(mock_root: Path) -> None:
    app = BookmgrApp(library=mock_root)
    async with app.run_test(size=(120, 30)) as pilot:
        table = await loaded(app, pilot)
        await search_for(pilot, "weir")
        await pilot.press("enter")
        await pilot.pause()
        box = app.screen.query_one("#search", Input)
        assert table.has_focus
        assert app.screen.query_one("#search-bar").display and box.value == "weir"
        assert listed(table) == ["The Martian", "Project Hail Mary"]


async def test_find_1_letters_type_into_the_box_instead_of_acting(mock_root: Path) -> None:
    app = BookmgrApp(library=mock_root)
    async with app.run_test(size=(120, 30)) as pilot:
        await loaded(app, pilot)
        await search_for(pilot, "quiet")
        assert app.is_running  # `q` was typed, not Quit
        assert app.search == "quiet"


@pytest.mark.parametrize("from_list", [False, True])
async def test_find_2_escape_clears_the_search(mock_root: Path, from_list: bool) -> None:
    app = BookmgrApp(library=mock_root)
    async with app.run_test(size=(120, 30)) as pilot:
        table = await loaded(app, pilot)
        await search_for(pilot, "dune")
        if from_list:
            await pilot.press("enter")
        await pilot.press("escape")
        await pilot.pause()
        box = app.screen.query_one("#search", Input)
        assert app.search == "" and box.value == ""
        assert not app.screen.query_one("#search-bar").display
        assert table.has_focus
        assert len(listed(table)) == 31
        assert str(app.screen.query_one("#status", Static).render()) == "31 books · 6 need review · by title"


async def test_find_5_no_match_names_the_search(mock_root: Path) -> None:
    app = BookmgrApp(library=mock_root)
    async with app.run_test(size=(120, 30)) as pilot:
        table = await loaded(app, pilot)
        await search_for(pilot, "zzz[x]")
        message = app.screen.query_one("#books-message", Static)
        assert not table.display and message.display
        assert str(message.render()) == 'No books match "zzz[x]"'
        assert str(app.screen.query_one("#status", Static).render()) == "0 of 31 books · 6 need review · by title"


async def test_find_6_selection_stays_if_it_matches_else_first_match(mock_root: Path) -> None:
    app = BookmgrApp(library=mock_root)
    async with app.run_test(size=(120, 30)) as pilot:
        table = await loaded(app, pilot)
        dune = next(book for book in app.catalog if book.title == "Dune Messiah")
        table.show(rows(app.catalog.ordered()), dune.id)
        await pilot.pause()
        await search_for(pilot, "dune")
        assert selected_title(app) == "Dune Messiah"
        await search_for(pilot, "")  # `/` again; the box keeps "dune"
        await pilot.press("ctrl+a", "ctrl+k", *"weir")
        await pilot.pause()
        assert selected_title(app) == "The Martian"


async def test_find_6_clearing_returns_to_the_book_selected_before(mock_root: Path) -> None:
    app = BookmgrApp(library=mock_root)
    async with app.run_test(size=(120, 30)) as pilot:
        table = await loaded(app, pilot)
        hobbit = next(book for book in app.catalog if book.title == "The Hobbit")
        table.show(rows(app.catalog.ordered()), hobbit.id)
        await pilot.pause()
        await search_for(pilot, "hobbitzz")  # matches until "z", then nothing
        await pilot.press("escape")
        await pilot.pause()
        assert selected_title(app) == "The Hobbit"


async def test_find_6_book_that_stops_matching_leaves_and_next_is_selected(mock_root: Path) -> None:
    app = BookmgrApp(library=mock_root)
    async with app.run_test(size=(120, 30)) as pilot:
        table = await loaded(app, pilot)
        await search_for(pilot, "dune")
        await pilot.press("enter")
        assert selected_title(app) == "Children of Dune"
        # An action (a title edit, until EDIT exists) makes it stop matching.
        book = next(book for book in app.catalog if book.title == "Children of Dune")
        app.catalog.replace(dataclasses.replace(book, title="Children of Arrakis"))
        app.catalog = app.catalog
        await pilot.pause()
        assert listed(table) == ["Dune", "Dune Messiah"]
        assert selected_title(app) == "Dune"


async def test_find_7_counts_show_beside_the_box_and_hide_when_cleared(mock_root: Path) -> None:
    app = BookmgrApp(library=mock_root)
    async with app.run_test(size=(120, 30)) as pilot:
        await loaded(app, pilot)
        counts = app.screen.query_one("#search-counts", Static)
        await search_for(pilot, "dune")
        assert str(counts.render()) == "3 books · 3 title · 0 author · 0 ISBN"
        await pilot.press("escape")
        await pilot.pause()
        assert not app.screen.query_one("#search-bar").display
