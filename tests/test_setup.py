"""SETUP (choosing a library on first run)."""

from __future__ import annotations

import os
from pathlib import Path

import pytest
from bookman import Config, is_library, load_config, save_config
from textual.widgets import Input, Static

from bookman_tui.app import BookmanApp
from bookman_tui.screens.browser import BrowserScreen
from bookman_tui.screens.setup import Choice, SetupScreen, assess


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


async def test_setup_2_missing_folder_needs_a_second_enter(tmp_path: Path, isolated_config: Path) -> None:
    target = tmp_path / "Books"
    app = BookmanApp()
    async with app.run_test() as pilot:
        await enter_path(app, pilot, str(target))
        assert isinstance(app.screen, SetupScreen)
        assert "Create" in hint(app)
        assert not target.exists() and not isolated_config.exists()
        await pilot.press("enter")
        await app.workers.wait_for_complete()
        await pilot.pause()
        assert isinstance(app.screen, BrowserScreen)
    assert is_library(target)


async def test_setup_2_editing_the_path_cancels_the_question(tmp_path: Path) -> None:
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
