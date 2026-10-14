"""BROWSE (empty state, status line, quit, reload, opening a folder)."""

from __future__ import annotations

import shutil
from pathlib import Path

import pytest
from bookman import Library, NullSource
from textual.widgets import Static

from bookman_tui import reveal
from bookman_tui.app import BookmanApp, reload_summary
from bookman_tui.reveal import folder_command
from bookman_tui.screens.details import DetailsScreen
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


# BROWSE-11, 13: F opens the selected book's folder


async def open_with_folders(mock_root: Path, monkeypatch: pytest.MonkeyPatch, pilot) -> tuple[list[Path], list[str]]:
    """Record the folders opened and the notifications, opening nothing."""
    opened: list[Path] = []
    notices: list[str] = []
    monkeypatch.setattr(reveal, "open_folder", opened.append)
    monkeypatch.setattr(pilot.app, "notify", lambda message, **kwargs: notices.append(message))
    await pilot.app.workers.wait_for_complete()
    await pilot.pause()
    return opened, notices


async def press_and_settle(pilot, key: str) -> None:
    await pilot.press(key)
    await pilot.app.workers.wait_for_complete()
    await pilot.pause()


def test_browse_11_folder_command_per_platform(tmp_path: Path) -> None:
    assert folder_command(tmp_path, "darwin") == ["open", str(tmp_path)]
    assert folder_command(tmp_path, "win32") == ["explorer", str(tmp_path)]
    assert folder_command(tmp_path, "linux") == ["xdg-open", str(tmp_path)]


async def test_browse_11_f_opens_the_selected_books_folder(mock_root: Path, monkeypatch) -> None:
    app = BookmanApp(library=mock_root)
    async with app.run_test(size=(120, 30)) as pilot:
        opened, notices = await open_with_folders(mock_root, monkeypatch, pilot)
        book = app.screen.selected_book
        await press_and_settle(pilot, "F")
        assert opened == [book.directory] and notices == []
        await press_and_settle(pilot, "f")  # lower case does nothing
        assert opened == [book.directory]


async def test_browse_11_f_on_the_narrow_details_screen(mock_root: Path, monkeypatch) -> None:
    app = BookmanApp(library=mock_root)
    async with app.run_test(size=(80, 30)) as pilot:
        opened, _ = await open_with_folders(mock_root, monkeypatch, pilot)
        book = app.screen.selected_book
        await press_and_settle(pilot, "enter")
        assert isinstance(app.screen, DetailsScreen)
        await press_and_settle(pilot, "F")
        assert opened == [book.directory]


async def test_browse_11_a_folder_gone_since_loading_is_reported(mock_root: Path, monkeypatch) -> None:
    app = BookmanApp(library=mock_root)
    async with app.run_test(size=(120, 30)) as pilot:
        opened, notices = await open_with_folders(mock_root, monkeypatch, pilot)
        book = app.screen.selected_book
        shutil.rmtree(book.directory)
        await press_and_settle(pilot, "F")
        assert opened == []
        assert notices == [f"“{book.title}”'s folder is gone. ctrl+r reloads the library."]


async def test_browse_11_a_command_that_cant_run_is_reported(mock_root: Path, monkeypatch) -> None:
    def missing(folder: Path) -> None:
        raise FileNotFoundError(2, "No such file or directory", "xdg-open")

    app = BookmanApp(library=mock_root)
    async with app.run_test(size=(120, 30)) as pilot:
        _, notices = await open_with_folders(mock_root, monkeypatch, pilot)
        monkeypatch.setattr(reveal, "open_folder", missing)
        await press_and_settle(pilot, "F")
        assert len(notices) == 1 and notices[0].startswith("Couldn't open the folder:")


async def test_browse_13_f_works_while_a_change_runs(mock_root: Path, monkeypatch) -> None:
    app = BookmanApp(library=mock_root)
    async with app.run_test(size=(120, 30)) as pilot:
        opened, notices = await open_with_folders(mock_root, monkeypatch, pilot)
        app.writing = "Looking up “Dune”."
        await press_and_settle(pilot, "F")
        assert opened == [app.screen.selected_book.directory] and notices == []
        app.writing = None
