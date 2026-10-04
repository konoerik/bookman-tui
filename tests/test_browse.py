"""BROWSE (M1 part: empty state, status line, quit)."""

from __future__ import annotations

from pathlib import Path

from bookman import Library, NullSource
from textual.widgets import Static

from bookman_tui.app import BookmanApp, reload_summary
from bookman_tui.store import Catalog


async def test_browse_6_empty_library_invites_import(empty_library: Path) -> None:
    app = BookmanApp(library=empty_library)
    async with app.run_test() as pilot:
        await app.workers.wait_for_complete()
        await pilot.pause()
        message = str(app.screen.query_one("#books-message", Static).render())
        assert "No books yet" in message and "import" in message


async def test_browse_4_status_line_counts_books_and_queue(empty_library: Path) -> None:
    app = BookmanApp(library=empty_library)
    async with app.run_test() as pilot:
        await app.workers.wait_for_complete()
        await pilot.pause()
        assert str(app.screen.query_one("#status", Static).render()) == "0 books · 0 need review"


async def test_g_5_q_quits_from_browser(empty_library: Path) -> None:
    app = BookmanApp(library=empty_library)
    async with app.run_test() as pilot:
        await pilot.press("q")
        assert app.return_code == 0
        assert not app.is_running


async def test_browse_4_status_line_counts_the_mock_library(mock_root: Path) -> None:
    app = BookmanApp(library=mock_root)
    async with app.run_test() as pilot:
        await app.workers.wait_for_complete()
        await pilot.pause()
        assert str(app.screen.query_one("#status", Static).render()) == "31 books · 6 need review · by title"


async def test_browse_5_reload_confirms_with_a_notification(mock_root: Path, monkeypatch) -> None:
    app = BookmanApp(library=mock_root)
    notices: list[str] = []
    monkeypatch.setattr(app, "notify", lambda message, **kwargs: notices.append(message))
    async with app.run_test() as pilot:
        await app.workers.wait_for_complete()
        await pilot.pause()
        assert notices == []  # opening the library is not a reload
        await pilot.press("ctrl+r")
        await app.workers.wait_for_complete()
        await pilot.pause()
        assert notices == ["Reloaded · 31 books"]


def test_browse_5_reload_summary_names_new_and_gone_books(mock_root: Path) -> None:
    books = Library(mock_root, source=NullSource()).scan()
    before = Catalog(books[:30])
    after = Catalog(books[2:])
    assert reload_summary(before, after) == "Reloaded · 29 books (1 new, 2 gone)"
    assert reload_summary(after, after) == "Reloaded · 29 books"
    assert reload_summary(None, Catalog(books[:1])) == "Reloaded · 1 book"
