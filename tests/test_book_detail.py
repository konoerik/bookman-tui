"""The detail pane (BROWSE-3) and its narrow-terminal screen (BROWSE-7)."""

from __future__ import annotations

import dataclasses
from pathlib import Path

import pytest
from bookman import Book, Library, MatchBasis, NullSource
from textual.widgets import Static

from bookman_tui.app import BookmanApp
from bookman_tui.screens.browser import BrowserScreen
from bookman_tui.screens.details import DetailsScreen
from bookman_tui.widgets.book_detail import BookDetail, Trust, author_note, trust
from bookman_tui.widgets.book_table import BookTable
from bookman_tui.widgets.cover import Cover

ISBN, TITLE_AUTHOR, TITLE_ONLY = MatchBasis.ISBN, MatchBasis.TITLE_AUTHOR, MatchBasis.TITLE_ONLY


@pytest.fixture
def books(mock_root: Path) -> dict[str, Book]:
    return {book.title: book for book in Library(mock_root, source=NullSource()).scan()}


def like(book: Book, **changes) -> Book:
    return dataclasses.replace(book, **changes)


# --- trust (BROWSE-3) -------------------------------------------------------


def test_browse_3_trust_reviewed_wins_over_everything(books: dict[str, Book]) -> None:
    walden = like(books["Walden"], reviewed=True)
    assert trust(walden).mark == "✓"
    assert trust(walden).headline == "Checked by you"
    assert trust(walden).reasons == ()


def test_browse_3_trust_reviewed_says_how_it_was_matched(books: dict[str, Book]) -> None:
    assert trust(books["The Art of War"]).detail == "matched online by title only"
    assert trust(books["Grandmother's Recipes"]).detail == "not found online"
    assert trust(like(books["Dune"], reviewed=True)).detail == "matched online by ISBN"
    assert trust(like(books["Frankenstein"], reviewed=True)).detail == "matched online by title and author"
    locked = like(books["statement-reader-locked"], reviewed=True)
    assert trust(locked).detail == "couldn't read inside the file"
    assert trust(books["Dune"]).detail is None


def test_browse_3_trust_matched_by_isbn(books: dict[str, Book]) -> None:
    assert trust(books["The Hobbit"]) == Trust("✓", "Matched online by ISBN")


def test_browse_3_trust_matched_by_title_and_author(books: dict[str, Book]) -> None:
    assert trust(books["Frankenstein"]) == Trust("✓", "Matched online by title and author")


def test_browse_3_trust_not_found_online(books: dict[str, Book]) -> None:
    assert trust(books["Notes on a Quiet Afternoon"]) == Trust("?", "Needs review", ("not found online",))


def test_browse_3_trust_unreadable_file_was_not_looked_up(books: dict[str, Book]) -> None:
    assert trust(books["statement-reader-locked"]).reasons == (
        "couldn't read inside the file, so it wasn't looked up online",
    )


def test_browse_3_trust_title_only_match(books: dict[str, Book]) -> None:
    assert trust(books["Meditations"]).reasons == ("matched online by title only",)


def test_browse_3_trust_grouped_by_title_only_with_strong_match(books: dict[str, Book]) -> None:
    assert trust(books["Walden"]) == Trust("?", "Needs review", ("formats grouped by title only",))


def test_browse_3_trust_lists_every_reason_in_order(books: dict[str, Book]) -> None:
    both = like(books["Walden"], identified=TITLE_ONLY)
    assert trust(both).reasons == ("matched online by title only", "formats grouped by title only")
    lost = like(books["Walden"], identified=None)
    assert trust(lost).reasons == ("not found online", "formats grouped by title only")


def test_browse_3_trust_impossible_combination_is_a_bug(books: dict[str, Book]) -> None:
    # bookman's needs_review rule forbids this; dataclasses.replace can't
    # build it either, since needs_review is derived. Guard the branch anyway.
    class Odd:
        id = "odd"
        reviewed = False
        needs_review = False
        identified = TITLE_ONLY
        grouped = None
        formats = books["Dune"].formats

    with pytest.raises(ValueError):
        trust(Odd())  # type: ignore[arg-type]


# --- author note (BROWSE-3) -------------------------------------------------


def test_browse_3_author_note_when_record_spells_author_differently(books: dict[str, Book]) -> None:
    assert author_note(books["Frankenstein"]) == "Open Library lists the author as Mary Wollstonecraft Shelley"


def test_browse_3_no_author_note_for_initials_spacing(books: dict[str, Book]) -> None:
    assert books["The Hobbit"].record_author == "J.R.R. Tolkien"
    assert author_note(books["The Hobbit"]) is None
    assert author_note(books["Deep Work"]) is None


def test_browse_3_no_author_note_when_author_came_from_record(books: dict[str, Book]) -> None:
    assert author_note(like(books["Meditations"], author=None)) is None
    # Meditations' file had no author; bookman filled it from the record.
    assert author_note(books["Meditations"]) is None


# --- the pane in the browser ------------------------------------------------


async def open_on(mock_root: Path, title: str, size=(130, 40)):
    app = BookmanApp(library=mock_root)
    run = app.run_test(size=size)
    pilot = await run.__aenter__()
    await app.workers.wait_for_complete()
    await pilot.pause()
    table = app.screen.query_one(BookTable)
    assert app.catalog is not None
    row = [book.title for book in app.catalog.ordered()].index(title)
    table.move_cursor(row=row)
    await pilot.pause()
    return app, run, pilot


def pane_text(screen) -> str:
    return "\n".join(str(widget.render()) for widget in screen.query_one(BookDetail).query(Static))


async def test_browse_3_pane_shows_title_author_isbn_and_files(mock_root: Path) -> None:
    app, run, pilot = await open_on(mock_root, "Dune")
    try:
        text = pane_text(app.screen)
        assert "Dune" in text and "Frank Herbert" in text
        assert "ISBN 979" in text
        assert "✓ Matched online by ISBN" in text
        assert "EPUB  Dune.epub" in text and "PDF  Dune.pdf" in text
    finally:
        await run.__aexit__(None, None, None)


async def test_browse_3_pane_shows_read_issue_advice_under_its_file(mock_root: Path) -> None:
    app, run, pilot = await open_on(mock_root, "statement-reader-locked")
    try:
        text = pane_text(app.screen)
        assert "The file is protected by a password" in text
    finally:
        await run.__aexit__(None, None, None)


async def test_browse_3_pane_shows_placeholder_without_cover(mock_root: Path) -> None:
    app, run, pilot = await open_on(mock_root, "Anathem")
    try:
        await app.workers.wait_for_complete()
        await pilot.pause()
        assert app.screen.query_one(Cover).showing_placeholder
    finally:
        await run.__aexit__(None, None, None)


async def test_browse_3_pane_follows_the_cursor(mock_root: Path) -> None:
    app, run, pilot = await open_on(mock_root, "Dune")
    try:
        await pilot.press("j")
        await pilot.pause()
        assert app.screen.query_one(BookDetail).book.title == "Dune Messiah"
    finally:
        await run.__aexit__(None, None, None)


# --- narrow terminals (BROWSE-7) --------------------------------------------


async def test_browse_7_pane_beside_table_when_wide(mock_root: Path) -> None:
    app, run, pilot = await open_on(mock_root, "Dune", size=(130, 30))
    try:
        detail = app.screen.query_one(BookDetail)
        table = app.screen.query_one(BookTable)
        assert detail.display and detail.region.width > 0
        assert detail.region.x >= table.region.right
    finally:
        await run.__aexit__(None, None, None)


async def test_browse_7_pane_hidden_when_narrow(mock_root: Path) -> None:
    app, run, pilot = await open_on(mock_root, "Dune", size=(90, 30))
    try:
        assert app.screen.has_class("narrow")
        assert app.screen.query_one(BookDetail).region.width == 0
    finally:
        await run.__aexit__(None, None, None)


async def test_browse_7_enter_opens_details_only_when_narrow(mock_root: Path) -> None:
    app, run, pilot = await open_on(mock_root, "Dune", size=(130, 30))
    try:
        await pilot.press("enter")
        assert isinstance(app.screen, BrowserScreen)
        await pilot.resize_terminal(90, 30)
        await pilot.pause()
        await pilot.press("enter")
        await pilot.pause()
        assert isinstance(app.screen, DetailsScreen)
        assert app.screen.query_one(BookDetail).book.title == "Dune"
    finally:
        await run.__aexit__(None, None, None)


async def test_browse_7_escape_returns_with_the_same_book_selected(mock_root: Path) -> None:
    app, run, pilot = await open_on(mock_root, "Dune", size=(90, 30))
    try:
        await pilot.press("enter")
        await pilot.pause()
        await pilot.press("escape")
        await pilot.pause()
        assert isinstance(app.screen, BrowserScreen)
        selected = app.screen.query_one(BookTable).selected_id
        assert app.catalog is not None and app.catalog.get(selected).title == "Dune"
    finally:
        await run.__aexit__(None, None, None)
