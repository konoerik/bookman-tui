"""SETUP (choosing a library on first run)."""

from __future__ import annotations

import os
from pathlib import Path

import pytest
from bookman import Config, Library, NullSource, is_library, load_config, save_config
from textual.widgets import Input, Static

from bookman_tui.app import BookmanApp
from bookman_tui.location import display_path
from bookman_tui.screens.browser import BrowserScreen
from bookman_tui.screens.setup import Choice, SetupScreen, assess, starting_path
from bookman_tui.screens.start_problem import StartProblemScreen


async def enter_path(app: BookmanApp, pilot, text: str) -> None:
    app.screen.query_one("#setup-path", Input).value = text
    await pilot.pause()
    await pilot.press("enter")
    await app.workers.wait_for_complete()
    await pilot.pause()


def hint(app: BookmanApp) -> str:
    return str(app.screen.query_one("#setup-hint", Static).render())


def test_setup_1_tilde_expanded_and_relative_path_made_absolute(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.chdir(tmp_path)
    assert assess("~/Books").path == tmp_path / "Books"
    assert assess("Books").path == tmp_path / "Books"
    assert assess("  ").choice is Choice.NOTHING


def test_setup_1_hint_names_the_full_path(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(tmp_path)
    assert display_path(tmp_path / "Books") in assess("Books").message


async def test_setup_1_prefilled_with_a_suggested_folder(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    (tmp_path / "notes.txt").write_text("")
    monkeypatch.chdir(tmp_path)
    app = BookmanApp()
    async with app.run_test() as pilot:
        field = app.screen.query_one("#setup-path", Input)
        assert field.value == display_path(tmp_path / "Books")
        assert field.cursor_position == len(field.value)
        assert hint(app) == f"New folder {field.value}: Enter creates it."
        await pilot.press("enter", "enter")
        await app.workers.wait_for_complete()
        await pilot.pause()
        assert isinstance(app.screen, BrowserScreen)
    assert is_library(tmp_path / "Books")


def test_setup_1_suggestion_skips_names_that_would_be_refused(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)
    (tmp_path / "Books").mkdir()
    (tmp_path / "Books" / "novel.epub").write_bytes(b"")
    (tmp_path / "Ebooks").write_text("")  # a file
    assert starting_path() == display_path(tmp_path / "Library")


def test_setup_1_suggestion_prefers_an_existing_library(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)
    Library(tmp_path / "Ebooks", source=NullSource())
    (tmp_path / "Books").mkdir()
    (tmp_path / "Books" / "novel.epub").write_bytes(b"")
    assert starting_path() == display_path(tmp_path / "Ebooks")


async def test_setup_2_missing_folder_needs_a_second_enter(tmp_path: Path, isolated_config: Path) -> None:
    target = tmp_path / "Books"
    app = BookmanApp()
    async with app.run_test() as pilot:
        await enter_path(app, pilot, str(target))
        assert isinstance(app.screen, SetupScreen)
        assert hint(app).startswith("Press Enter again to create")
        assert not target.exists() and not isolated_config.exists()
        await pilot.press("enter")
        await app.workers.wait_for_complete()
        await pilot.pause()
        assert isinstance(app.screen, BrowserScreen)
    assert is_library(target)


async def test_setup_2_editing_the_path_cancels_the_confirmation(tmp_path: Path) -> None:
    app = BookmanApp()
    async with app.run_test() as pilot:
        await enter_path(app, pilot, str(tmp_path / "Books"))
        await pilot.press("s")  # now ".../Bookss"
        assert "New folder" in hint(app)
        await pilot.press("enter")
        assert isinstance(app.screen, SetupScreen)
        assert not (tmp_path / "Bookss").exists()


async def test_setup_3_saves_the_library_keeping_other_settings(
    tmp_path: Path, empty_library: Path
) -> None:
    save_config(Config(library=tmp_path / "old", offline=True))
    app = BookmanApp()
    async with app.run_test() as pilot:
        # A saved library that's gone leads to START-5; `s` opens Setup.
        await pilot.press("s")
        await enter_path(app, pilot, str(empty_library))
        assert isinstance(app.screen, BrowserScreen)
        assert len(app.screen_stack) == 2  # Setup and the problem are gone
        assert app.sub_title.endswith("· config")
    assert load_config() == Config(library=empty_library, offline=True)


async def test_setup_4_file_is_refused_and_nothing_saved(tmp_path: Path, isolated_config: Path) -> None:
    file = tmp_path / "notes.txt"
    file.write_text("")
    app = BookmanApp()
    async with app.run_test() as pilot:
        await enter_path(app, pilot, str(file))
        assert isinstance(app.screen, SetupScreen)
        assert "file, not a folder" in hint(app)
        assert app.screen.query_one("#setup-hint").has_class("error")
    assert not isolated_config.exists()


async def test_setup_5_existing_library_opens_without_confirmation(empty_library: Path) -> None:
    app = BookmanApp()
    async with app.run_test() as pilot:
        await enter_path(app, pilot, str(empty_library))
        assert isinstance(app.screen, BrowserScreen)


async def test_setup_5_empty_folder_is_used(tmp_path: Path) -> None:
    folder = tmp_path / "empty"
    folder.mkdir()
    (folder / ".DS_Store").write_text("")
    app = BookmanApp()
    async with app.run_test() as pilot:
        await enter_path(app, pilot, str(folder))
        assert isinstance(app.screen, BrowserScreen)
    assert is_library(folder)


async def test_setup_5_folder_of_other_files_is_refused(tmp_path: Path, isolated_config: Path) -> None:
    folder = tmp_path / "Downloads"
    folder.mkdir()
    (folder / "book.epub").write_bytes(b"")
    app = BookmanApp()
    async with app.run_test() as pilot:
        await enter_path(app, pilot, str(folder))
        assert isinstance(app.screen, SetupScreen)
        assert "needs an empty folder" in hint(app)
    assert not isolated_config.exists()
    assert not is_library(folder)


async def test_setup_6_override_is_named_and_chosen_folder_opens(
    tmp_path: Path, empty_library: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("BOOKMAN_LIBRARY", str(tmp_path / "unplugged"))
    app = BookmanApp()
    notices: list[str] = []
    monkeypatch.setattr(app, "notify", lambda message, **kwargs: notices.append(message))
    async with app.run_test() as pilot:
        await pilot.press("s")
        await enter_path(app, pilot, str(empty_library))
        assert isinstance(app.screen, BrowserScreen)
        assert app.library is not None and app.library.root == empty_library
        assert app.sub_title.endswith("· config")
    assert any("$BOOKMAN_LIBRARY still takes precedence" in n for n in notices)
    assert load_config() == Config(library=empty_library)
    assert os.environ["BOOKMAN_LIBRARY"] == str(tmp_path / "unplugged")


async def test_start_4_setup_replaces_an_unreadable_config(tmp_path: Path, isolated_config: Path) -> None:
    isolated_config.parent.mkdir(parents=True)
    isolated_config.write_text("not json")
    target = tmp_path / "Books"
    app = BookmanApp()
    async with app.run_test() as pilot:
        await pilot.press("s")
        await enter_path(app, pilot, str(target))
        await pilot.press("enter")
        await app.workers.wait_for_complete()
        await pilot.pause()
        assert isinstance(app.screen, BrowserScreen)
    assert load_config() == Config(library=target)


async def test_setup_7_esc_cancels_the_create_confirmation(tmp_path: Path) -> None:
    app = BookmanApp()
    async with app.run_test() as pilot:
        await enter_path(app, pilot, str(tmp_path / "Books"))
        assert hint(app).startswith("Press Enter again to create")
        await pilot.press("escape")
        assert hint(app).startswith("New folder")
        await pilot.press("enter")  # asks again rather than creating
        assert hint(app).startswith("Press Enter again to create")
        assert not (tmp_path / "Books").exists()


async def test_setup_7_esc_esc_quits_on_first_run(
    isolated_config: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    app = BookmanApp()
    exits: list[bool] = []
    monkeypatch.setattr(app, "exit", lambda *args, **kwargs: exits.append(True))
    async with app.run_test() as pilot:
        await pilot.press("escape")
        assert "Press Esc again to quit" in hint(app)
        assert not exits
        await pilot.press("escape")
        assert exits
    assert not isolated_config.exists()


async def test_setup_7_editing_cancels_the_quit_confirmation(monkeypatch: pytest.MonkeyPatch) -> None:
    app = BookmanApp()
    exits: list[bool] = []
    monkeypatch.setattr(app, "exit", lambda *args, **kwargs: exits.append(True))
    async with app.run_test() as pilot:
        await pilot.press("escape")
        await pilot.press("x")
        assert "Press Esc again to quit" not in hint(app)
        await pilot.press("escape")
        assert not exits


async def test_setup_7_esc_returns_to_the_start_problem(tmp_path: Path) -> None:
    save_config(Config(library=tmp_path / "unplugged"))
    app = BookmanApp()
    async with app.run_test() as pilot:
        header = app.sub_title
        await pilot.press("s")
        assert isinstance(app.screen, SetupScreen)
        await pilot.press("escape")
        await pilot.pause()
        assert isinstance(app.screen, StartProblemScreen)
        assert app.sub_title == header
    assert load_config() == Config(library=tmp_path / "unplugged")
