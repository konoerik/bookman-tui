"""START (launching) and SETTINGS-1 (the header)."""

from __future__ import annotations

from pathlib import Path

import pytest
from bookmgr import Config, save_config

from bookmgr_tui.app import BookmgrApp
from bookmgr_tui.location import display_path
from bookmgr_tui.screens.browser import BrowserScreen
from bookmgr_tui.screens.setup import SetupScreen
from bookmgr_tui.screens.start_problem import StartProblemScreen


async def settle(app: BookmgrApp, pilot) -> None:
    """Let the scan worker finish and its result land."""
    await app.workers.wait_for_complete()
    await pilot.pause()


async def test_start_1_explicit_library_wins_over_environment(
    empty_library: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("BOOKMGR_LIBRARY", str(tmp_path / "elsewhere"))
    app = BookmgrApp(library=empty_library)
    async with app.run_test() as pilot:
        await settle(app, pilot)
        assert isinstance(app.screen, BrowserScreen)
        assert app.library is not None and app.library.root == empty_library
        assert app.sub_title.endswith("· --library")


async def test_start_1_environment_library(empty_library: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("BOOKMGR_LIBRARY", str(empty_library))
    app = BookmgrApp()
    async with app.run_test() as pilot:
        await settle(app, pilot)
        assert isinstance(app.screen, BrowserScreen)
        assert app.sub_title.endswith("· $BOOKMGR_LIBRARY")


async def test_start_2_saved_library_opens_browser(empty_library: Path) -> None:
    save_config(Config(library=empty_library))
    app = BookmgrApp()
    async with app.run_test() as pilot:
        await settle(app, pilot)
        assert isinstance(app.screen, BrowserScreen)
        assert app.catalog is not None and len(app.catalog) == 0
        assert app.sub_title == f"{display_path(empty_library)} · config"


async def test_start_3_no_library_shows_setup() -> None:
    app = BookmgrApp()
    async with app.run_test():
        assert isinstance(app.screen, SetupScreen)


async def test_start_4_invalid_config_shows_problem_without_retry(isolated_config: Path) -> None:
    isolated_config.parent.mkdir(parents=True)
    isolated_config.write_text("not json")
    app = BookmgrApp()
    async with app.run_test() as pilot:
        assert isinstance(app.screen, StartProblemScreen)
        assert app.screen.path == display_path(isolated_config)
        assert not app.screen.query("#retry")
        await pilot.press("s")
        assert isinstance(app.screen, SetupScreen)


async def test_start_4_invalid_config_applies_even_with_explicit_library(
    empty_library: Path, isolated_config: Path
) -> None:
    isolated_config.parent.mkdir(parents=True)
    isolated_config.write_text("not json")
    app = BookmgrApp(library=empty_library)
    async with app.run_test():
        assert isinstance(app.screen, StartProblemScreen)
        assert not app.screen.can_retry


async def test_start_5_missing_folder_is_reported_not_created(tmp_path: Path) -> None:
    missing = tmp_path / "unplugged" / "Books"
    app = BookmgrApp(library=missing)
    async with app.run_test():
        assert isinstance(app.screen, StartProblemScreen)
        assert "doesn't exist" in app.screen.reason
        assert app.screen.where == "Passed explicitly"
    assert not missing.exists()


async def test_start_5_retry_opens_library_once_it_is_back(tmp_path: Path, empty_library: Path) -> None:
    moved = tmp_path / "moved"
    empty_library.rename(moved)
    app = BookmgrApp(library=empty_library)
    async with app.run_test() as pilot:
        assert isinstance(app.screen, StartProblemScreen)
        moved.rename(empty_library)
        await pilot.press("r")
        await settle(app, pilot)
        assert isinstance(app.screen, BrowserScreen)


async def test_start_5_folder_of_other_files_is_not_a_library(tmp_path: Path) -> None:
    folder = tmp_path / "Downloads"
    folder.mkdir()
    (folder / "book.epub").write_bytes(b"")
    app = BookmgrApp(library=folder)
    async with app.run_test():
        assert isinstance(app.screen, StartProblemScreen)
        assert "isn't a bookmgr library" in app.screen.reason


async def test_start_5_path_is_a_file(tmp_path: Path) -> None:
    file = tmp_path / "library"
    file.write_text("")
    app = BookmgrApp(library=file)
    async with app.run_test():
        assert isinstance(app.screen, StartProblemScreen)
        assert "a file" in app.screen.reason


async def test_start_5_setup_key_leads_to_setup(tmp_path: Path) -> None:
    app = BookmgrApp(library=tmp_path / "missing")
    async with app.run_test() as pilot:
        await pilot.press("s")
        assert isinstance(app.screen, SetupScreen)


def test_settings_1_home_shown_as_tilde(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("HOME", str(tmp_path))
    assert display_path(tmp_path / "Books") == "~/Books"
    assert display_path(Path("/opt/Books")) == "/opt/Books"
