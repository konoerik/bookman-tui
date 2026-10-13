"""EDIT, LOOKUP, REVIEW and the summary's `l` (M10, ADR-11), against a small
library and a scripted source, never the network."""

from __future__ import annotations

from pathlib import Path

import pytest
from bookman import Book, Config, Library, MetadataSourceError, NullSource, save_config
from mock_library import MockSource, Record, Spec, isbn13, write_epub
from textual.widgets import Button, Input, Static

from bookman_tui.app import BookmanApp
from bookman_tui.curating import batch_summary, could_help, edit_changes, lookup_summary
from bookman_tui.importing import ImportJob
from bookman_tui.prefs import load_prefs
from bookman_tui.screens.browser import BrowserScreen
from bookman_tui.screens.edit_dialog import EditDialog, LookupBox
from bookman_tui.screens.import_screen import ImportScreen
from bookman_tui.store import Grouping
from bookman_tui.widgets.book_detail import BookDetail

DUNE = Spec("Dune", "Frank Herbert", isbn13(1), record=Record("Dune", "Frank Herbert"))
HOBBIT = Spec("The Hobbit", "J. R. R. Tolkien", isbn13(2), record=Record("The Hobbit", "John Ronald Reuel Tolkien"))
EMMA = Spec("Emma", "Jane Austen", isbn13(3))
WALDEN = Spec("Walden", "Henry David Thoreau", isbn13(4))
DEEP_WORK = Spec("Deep Work", "Cal Newport", record=Record("Deep Work", "Cal Newport"))
"""Only in the source: what `deep_work_newport.epub` really is."""

SOURCE = MockSource([DUNE, HOBBIT, DEEP_WORK])
FOUND = MockSource(
    [DUNE, HOBBIT, DEEP_WORK, Spec("Emma", "Jane Austen", isbn13(3), record=Record("Emma", "Jane Austen"))]
)
"""The source once Emma can be found, for LOOKUP."""


class Unreachable:
    """Every request fails, as without a network (not a `NullSource`, which
    bookman takes as lookups off) [bookman 1.3.0 @ 1bdad64]."""

    def lookup_by_isbn(self, isbn: str):
        raise MetadataSourceError("network unreachable")

    def search(self, title: str, author: str | None = None):
        raise MetadataSourceError("network unreachable")

    def fetch_cover(self, url: str) -> bytes:
        raise MetadataSourceError("network unreachable")


@pytest.fixture
def library(tmp_path: Path) -> Path:
    """Dune and The Hobbit matched by ISBN; Emma, Walden and an untitled
    `deep_work_newport.epub` not found online. Saved as the configured
    library with lookups off; tests swap in a source."""
    root = tmp_path / "library"
    files = tmp_path / "files"
    files.mkdir()
    lib = Library(root, source=SOURCE)
    for spec in (DUNE, HOBBIT, EMMA, WALDEN):
        write_epub(files / f"{spec.title}.epub", spec)
        lib.import_file(files / f"{spec.title}.epub")
    write_epub(files / "deep_work_newport.epub", Spec(None))
    lib.import_file(files / "deep_work_newport.epub")
    save_config(Config(library=root, offline=True))
    return root


async def settle(app: BookmanApp, pilot) -> None:
    await app.workers.wait_for_complete()
    await pilot.pause()
    await app.workers.wait_for_complete()
    await pilot.pause()


def book(app: BookmanApp, title: str) -> Book:
    return next(b for b in app.catalog if b.title == title)


async def start(app: BookmanApp, pilot, root: Path, select: str, source=SOURCE) -> list[str]:
    """Open the library with `source`, select the book titled `select`, and
    collect notifications."""
    await settle(app, pilot)
    app.library = Library(root, source=source)
    notices: list[str] = []
    app.notify = lambda message, **kwargs: notices.append(message)
    app.screen.select(book(app, select).id)
    await pilot.pause()
    return notices


def field(app: BookmanApp, name: str) -> Input:
    return app.screen.query_one(f"#edit-{name}", Input)


async def type_into(app: BookmanApp, pilot, name: str, value: str) -> None:
    field(app, name).value = value
    await pilot.pause()


# Pure rules


def test_edit_4_changes_are_only_the_changed_fields(library: Path) -> None:
    dune = next(b for b in Library(library, source=NullSource()).scan() if b.title == "Dune")
    assert edit_changes(dune, "Dune ", "Frank Herbert", dune.isbn) == {}
    assert edit_changes(dune, "Dune Messiah", "Frank Herbert", dune.isbn) == {"title": "Dune Messiah"}
    assert edit_changes(dune, "Dune", " ", "") == {"author": None, "isbn": None}
    assert edit_changes(dune, "  ", "Frank Herbert", dune.isbn) == {"title": ""}


def test_edit_8_lookup_helps_only_with_something_missing(library: Path) -> None:
    books = {b.title: b for b in Library(library, source=NullSource()).scan()}
    assert not could_help(books["Dune"])
    assert could_help(books["Emma"])  # not matched online, no cover
    assert could_help(books["deep_work_newport"])


def test_lookup_2_summary_names_what_changed(library: Path) -> None:
    lib = Library(library, source=FOUND)
    emma = next(b for b in lib.scan() if b.title == "Emma")
    before = Book(**{**emma.__dict__})
    after = lib.reidentify(emma)
    assert lookup_summary(before, after) == "Found a cover · Identified by ISBN"
    assert lookup_summary(after, after) == "No better match found"
    assert batch_summary([(before, after), (after, after)]) == "Looked up 2 books · 1 updated"


# EDIT


async def test_edit_1_e_opens_the_dialog_with_what_helps(library: Path) -> None:
    app = BookmanApp()
    async with app.run_test(size=(120, 50)) as pilot:
        await start(app, pilot, library, "deep_work_newport")
        await pilot.press("e")
        assert isinstance(app.screen, EditDialog)
        assert app.focused is field(app, "title")
        assert field(app, "title").value == "deep_work_newport"
        assert field(app, "author").value == ""
        assert "deep_work_newport.epub" in str(app.screen.query_one("#edit-files", Static).render())
        assert "not found online" in str(app.screen.query_one("#edit-trust", Static).render())
        assert app.screen.query_one(LookupBox).value is True
        assert not app.screen.query("#edit-record-author")


async def test_edit_2_offers_the_sources_spelling(library: Path) -> None:
    app = BookmanApp()
    async with app.run_test(size=(120, 50)) as pilot:
        await start(app, pilot, library, "The Hobbit")
        await pilot.press("e")
        await pilot.click("#edit-record-author")
        assert field(app, "author").value == "John Ronald Reuel Tolkien"


async def test_edit_3_unchanged_save_closes_without_marking_reviewed(library: Path) -> None:
    app = BookmanApp()
    async with app.run_test() as pilot:
        notices = await start(app, pilot, library, "Emma")
        await pilot.press("e", "enter")
        await settle(app, pilot)
        assert isinstance(app.screen, BrowserScreen)
        assert not book(app, "Emma").reviewed
        assert notices == []


async def test_edit_3_esc_cancels(library: Path) -> None:
    app = BookmanApp()
    async with app.run_test() as pilot:
        await start(app, pilot, library, "Emma")
        await pilot.press("e")
        await type_into(app, pilot, "author", "J. Austen")
        await pilot.press("escape")
        await settle(app, pilot)
        assert isinstance(app.screen, BrowserScreen)
        assert book(app, "Emma").author == "Jane Austen"


async def test_edit_4_empty_title_is_refused_inline(library: Path) -> None:
    app = BookmanApp()
    async with app.run_test(size=(120, 50)) as pilot:
        await start(app, pilot, library, "Emma")
        await pilot.press("e")
        await type_into(app, pilot, "title", "  ")
        await pilot.press("enter")
        await settle(app, pilot)
        assert isinstance(app.screen, EditDialog)
        assert "A book needs a title." in str(app.screen.query_one("#edit-error", Static).render())


async def test_edit_5_invalid_isbn_is_refused_inline_keeping_what_was_typed(library: Path) -> None:
    app = BookmanApp()
    async with app.run_test(size=(120, 50)) as pilot:
        await start(app, pilot, library, "Emma")
        await pilot.press("e")
        await type_into(app, pilot, "author", "J. Austen")
        await type_into(app, pilot, "isbn", "123")
        await pilot.press("enter")
        await settle(app, pilot)
        assert isinstance(app.screen, EditDialog)
        assert "Not a valid ISBN" in str(app.screen.query_one("#edit-error", Static).render())
        assert field(app, "author").value == "J. Austen"
        assert app.focused is field(app, "isbn")
        assert app.busy is None


async def test_edit_6_7_hardest_case_saves_then_looks_up(library: Path) -> None:
    """The book M10 was designed for: no title or author in the file, not
    found online. Fixing both finds it."""
    app = BookmanApp()
    async with app.run_test() as pilot:
        notices = await start(app, pilot, library, "deep_work_newport")
        book_id = book(app, "deep_work_newport").id
        await pilot.press("e")
        await type_into(app, pilot, "title", "Deep Work")
        await type_into(app, pilot, "author", "Cal Newport")
        await pilot.press("enter")
        await settle(app, pilot)
        assert isinstance(app.screen, BrowserScreen)
        fixed = app.catalog.get(book_id)
        assert (fixed.title, fixed.author, fixed.reviewed) == ("Deep Work", "Cal Newport", True)
        assert fixed.cover_path is not None
        assert notices == ["Saved · Found a cover"]
        assert app.screen.selected_id == book_id  # G-3, though the title moved it
        assert app.busy is None and app.looking_up == frozenset()


async def test_edit_7_unticked_saves_without_lookup_and_is_remembered(library: Path) -> None:
    app = BookmanApp()
    async with app.run_test() as pilot:
        notices = await start(app, pilot, library, "deep_work_newport")
        await pilot.press("e")
        app.screen.query_one(LookupBox).focus()
        await pilot.press("space")
        await type_into(app, pilot, "title", "Deep Work")
        app.screen.query_one(LookupBox).focus()
        await pilot.press("enter")  # Enter saves from the checkbox too (EDIT-3)
        await settle(app, pilot)
        assert notices == ["Saved"]
        assert book(app, "Deep Work").cover_path is None
        assert load_prefs().lookup_after_edit is False
        await pilot.press("e")
        assert app.screen.query_one(LookupBox).value is False


async def test_edit_8_no_lookup_when_it_cant_help(library: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    app = BookmanApp()
    async with app.run_test() as pilot:
        notices = await start(app, pilot, library, "Dune")
        monkeypatch.setattr(app.library, "reidentify", lambda *a, **k: pytest.fail("looked up"))
        await pilot.press("e")
        await type_into(app, pilot, "author", "F. Herbert")
        await pilot.press("enter")
        await settle(app, pilot)
        assert notices == ["Saved"]
        assert book(app, "Dune").author == "F. Herbert"


# LOOKUP


async def test_lookup_1_2_l_looks_up_and_says_what_changed(library: Path) -> None:
    app = BookmanApp()
    async with app.run_test() as pilot:
        notices = await start(app, pilot, library, "Emma", source=FOUND)
        emma = book(app, "Emma")
        app.screen.action_look_up()
        assert app.looking_up == {emma.id}  # "Looking up…" while it runs
        await pilot.pause()
        await settle(app, pilot)
        assert notices == ["Found a cover · Identified by ISBN"]
        assert not book(app, "Emma").needs_review
        assert not app.screen.query_one(BookDetail).busy


async def test_lookup_1_detail_pane_shows_looking_up(library: Path) -> None:
    app = BookmanApp()
    async with app.run_test(size=(120, 50)) as pilot:
        await start(app, pilot, library, "Emma")
        app.looking_up = frozenset({book(app, "Emma").id})
        await pilot.pause()
        assert app.screen.query_one("#detail-busy").display
        app.looking_up = frozenset()


@pytest.mark.parametrize(
    ("source", "notice"),
    [(Unreachable(), "Open Library can't be reached"), (NullSource(), "Lookups are off")],
)
async def test_lookup_2_failed_or_off_changes_nothing(library: Path, source, notice: str) -> None:
    app = BookmanApp()
    async with app.run_test() as pilot:
        notices = await start(app, pilot, library, "Emma", source=source)
        await pilot.press("l")
        await settle(app, pilot)
        assert notices == [notice]
        assert book(app, "Emma").needs_review


async def test_lookup_3_reviewed_book_keeps_its_fields(library: Path) -> None:
    app = BookmanApp()
    async with app.run_test() as pilot:
        await start(app, pilot, library, "The Hobbit")
        await pilot.press("e")
        await type_into(app, pilot, "author", "Tolkien")
        await pilot.press("enter")
        await settle(app, pilot)
        await pilot.press("l")
        await settle(app, pilot)
        assert book(app, "The Hobbit").author == "Tolkien"


# G-2


async def test_g_2_a_second_change_is_refused_while_one_runs(library: Path) -> None:
    app = BookmanApp()
    async with app.run_test() as pilot:
        notices = await start(app, pilot, library, "Emma")
        app.writing = "Looking up “Dune”."
        for key in ("e", "l", "v"):
            await pilot.press(key)
        await settle(app, pilot)
        assert isinstance(app.screen, BrowserScreen)
        assert notices == ["Looking up “Dune”. Try again when it's done."] * 3
        assert not book(app, "Emma").reviewed
        app.writing = None


# REVIEW


async def test_review_1_v_toggles_reviewed(library: Path) -> None:
    app = BookmanApp()
    async with app.run_test() as pilot:
        await start(app, pilot, library, "Emma")
        await pilot.press("v")
        await settle(app, pilot)
        assert book(app, "Emma").reviewed
        assert book(app, "Emma").author == "Jane Austen"
        await pilot.press("v")
        await settle(app, pilot)
        assert not book(app, "Emma").reviewed


async def test_review_2_v_works_through_the_needs_review_group(library: Path) -> None:
    app = BookmanApp()
    async with app.run_test() as pilot:
        await start(app, pilot, library, "deep_work_newport")
        app.grouping = Grouping.STATUS
        await pilot.pause()
        ids = {title: book(app, title).id for title in ("deep_work_newport", "Emma", "Walden")}
        # Needs review, by title: deep_work_newport, Emma, Walden.
        await pilot.press("v")
        await settle(app, pilot)
        assert app.screen.selected_id == ids["Emma"]
        app.screen.select(ids["Walden"])
        await pilot.press("v")  # the last: back to the previous one
        await settle(app, pilot)
        assert app.screen.selected_id == ids["Emma"]
        await pilot.press("v")  # the only one left: stays on it
        await settle(app, pilot)
        assert app.screen.selected_id == ids["Emma"]


async def test_review_2_without_status_grouping_selection_follows_the_book(library: Path) -> None:
    app = BookmanApp()
    async with app.run_test() as pilot:
        await start(app, pilot, library, "Emma")
        await pilot.press("v")
        await settle(app, pilot)
        assert app.screen.selected_id == book(app, "Emma").id


# IMPORT-10's `l`


async def test_import_10_l_looks_up_the_books_imported_without_open_library(
    library: Path, tmp_path: Path
) -> None:
    folder = tmp_path / "new"
    folder.mkdir()
    write_epub(folder / "deep-work.epub", DEEP_WORK)
    app = BookmanApp()
    async with app.run_test() as pilot:
        notices = await start(app, pilot, library, "Emma", source=Unreachable())
        await pilot.press("i")
        assert isinstance(app.screen, ImportScreen)
        app.start_import(ImportJob(folder=folder))
        await settle(app, pilot)
        assert app.import_job is not None and len(app.import_job.lookups_failed) == 1
        app.library = Library(library, source=SOURCE)
        notices.clear()
        await pilot.press("l")
        await settle(app, pilot)
        assert isinstance(app.screen, BrowserScreen)
        assert notices == ["Looked up 1 book · 1 updated"]
        assert book(app, "Deep Work").cover_path is not None
