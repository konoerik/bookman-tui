"""IMPORT (adding books), run offline against a fresh library."""

from __future__ import annotations

from pathlib import Path

import pytest
from bookmgr import Config, Library, LookupOutcome, MetadataSourceError, NullSource, save_config
from mock_library import Spec, isbn13, write_epub, write_pdf
from textual.content import Content
from textual.widgets import Checkbox, Input, Static

from bookmgr_tui.app import BookmgrApp
from bookmgr_tui.importing import ImportJob, Mark, files_in_dot_folders, folder_files, survey
from bookmgr_tui.location import display_path
from bookmgr_tui.screens.browser import BrowserScreen
from bookmgr_tui.screens.import_screen import ImportScreen, PreviewList, Stage

DUNE = Spec("Dune", "Frank Herbert", isbn13(1))
EMMA = Spec("Emma", "Jane Austen", isbn13(2))
WALDEN = Spec("Walden", "Henry David Thoreau", isbn13(3))


@pytest.fixture
def library(tmp_path: Path) -> Path:
    """An empty library, saved as the configured one, with lookups off."""
    root = tmp_path / "library"
    Library(root, source=NullSource())
    save_config(Config(library=root, offline=True))
    return root


@pytest.fixture
def downloads(tmp_path: Path) -> Path:
    """Two EPUBs, a PDF, a broken EPUB, a .mobi and a hidden file."""
    folder = tmp_path / "downloads"
    folder.mkdir()
    write_epub(folder / "dune.epub", DUNE)
    write_epub(folder / "emma.epub", EMMA)
    write_pdf(folder / "walden.pdf", WALDEN)
    (folder / "broken.epub").write_bytes(b"not a zip")
    (folder / "notes.mobi").write_bytes(b"")
    (folder / ".DS_Store").write_bytes(b"")
    return folder


async def settle(app: BookmgrApp, pilot) -> None:
    await app.workers.wait_for_complete()
    await pilot.pause()
    await app.workers.wait_for_complete()
    await pilot.pause()


async def open_import(app: BookmgrApp, pilot) -> ImportScreen:
    await settle(app, pilot)
    await pilot.press("i")
    assert isinstance(app.screen, ImportScreen)
    return app.screen


async def submit_path(app: BookmgrApp, pilot, path: Path | str) -> None:
    app.screen.query_one("#import-path", Input).value = str(path)
    await pilot.press("enter")
    await settle(app, pilot)


def text(screen, selector: str) -> str:
    return str(screen.query_one(selector, Static).render())


async def test_import_1_i_opens_the_import_screen_and_esc_closes_it(library: Path) -> None:
    app = BookmgrApp()
    async with app.run_test() as pilot:
        screen = await open_import(app, pilot)
        assert app.focused is screen.query_one("#import-path")
        await pilot.press("escape")
        assert isinstance(app.screen, BrowserScreen)


async def test_import_1_path_is_prefilled_with_the_current_folder(
    library: Path, downloads: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(downloads.parent)
    app = BookmgrApp()
    async with app.run_test() as pilot:
        screen = await open_import(app, pilot)
        field = screen.query_one("#import-path", Input)
        assert field.value == f"{display_path(downloads.parent)}/"
        assert field.cursor_position == len(field.value)
        assert text(screen, "#import-hint").startswith(f"Folder {display_path(downloads.parent)}. ")
        await pilot.press(*"downloads")
        assert text(screen, "#import-hint") == f"Folder {display_path(downloads)}. Press Enter to see what's in it."


async def test_import_2_missing_path_and_unsupported_file_are_inline_errors(
    library: Path, downloads: Path
) -> None:
    app = BookmgrApp()
    async with app.run_test() as pilot:
        screen = await open_import(app, pilot)
        await submit_path(app, pilot, downloads / "nope.epub")
        assert text(screen, "#import-hint").startswith("Nothing at")
        assert screen.query_one("#import-hint").has_class("error")
        await submit_path(app, pilot, downloads / "notes.mobi")
        assert "isn't a format bookmgr reads" in text(screen, "#import-hint")
        assert screen.stage is Stage.PATH
        assert app.import_job is None


async def test_import_2_single_file_starts_at_once(library: Path, downloads: Path) -> None:
    app = BookmgrApp()
    async with app.run_test() as pilot:
        screen = await open_import(app, pilot)
        await submit_path(app, pilot, downloads / "dune.epub")
        assert screen.stage is Stage.SUMMARY
        assert "1 imported" in text(screen, "#summary-text")


async def test_import_2_single_file_already_in_library_starts_nothing(
    library: Path, downloads: Path
) -> None:
    Library(library, source=NullSource()).import_file(downloads / "dune.epub")
    app = BookmgrApp()
    async with app.run_test() as pilot:
        screen = await open_import(app, pilot)
        await submit_path(app, pilot, downloads / "dune.epub")
        assert text(screen, "#import-hint") == "Already in library: Dune. Nothing to import."
        assert screen.stage is Stage.PATH
        assert app.import_job is None


def test_import_3_survey_marks_new_held_and_unsupported(library: Path, downloads: Path) -> None:
    lib = Library(library, source=NullSource())
    lib.import_file(downloads / "emma.epub")
    marks = {entry.path.name: entry.mark for entry in survey(lib, downloads, recursive=False)}
    assert marks == {
        "broken.epub": Mark.NEW,
        "dune.epub": Mark.NEW,
        "emma.epub": Mark.HELD,
        "notes.mobi": Mark.UNSUPPORTED,
        "walden.pdf": Mark.NEW,
    }


async def test_import_3_folder_opens_a_preview_with_new_files_ticked(
    library: Path, downloads: Path
) -> None:
    Library(library, source=NullSource()).import_file(downloads / "emma.epub")
    app = BookmgrApp()
    async with app.run_test() as pilot:
        screen = await open_import(app, pilot)
        await submit_path(app, pilot, downloads)
        assert screen.stage is Stage.PREVIEW
        assert text(screen, "#preview-counts") == (
            "5 files found · 3 new · 1 already in library · 1 unsupported"
        )
        listing = screen.query_one(PreviewList)
        assert sorted(Path(value).name for value in listing.selected) == [
            "broken.epub",
            "dune.epub",
            "walden.pdf",
        ]
        held = listing.get_option_at_index(2)  # emma.epub
        assert held.disabled
        assert text(screen, "#preview-hint").startswith("Enter Import 3 files · Space Tick")


async def test_import_3_space_unticks_and_a_toggles_all(library: Path, downloads: Path) -> None:
    app = BookmgrApp()
    async with app.run_test() as pilot:
        screen = await open_import(app, pilot)
        await submit_path(app, pilot, downloads)
        await pilot.press("space")  # broken.epub, first in the list
        assert {path.name for path in screen.ticked} == {"dune.epub", "emma.epub", "walden.pdf"}
        await pilot.press("a")
        assert len(screen.ticked) == 4
        await pilot.press("a")
        assert not screen.ticked
        assert text(screen, "#preview-hint").startswith("Nothing ticked")
        await pilot.press("enter")  # nothing ticked, nothing starts
        assert app.import_job is None


async def test_import_3_slash_filters_by_file_name(library: Path, downloads: Path) -> None:
    app = BookmgrApp()
    async with app.run_test() as pilot:
        screen = await open_import(app, pilot)
        await submit_path(app, pilot, downloads)
        await pilot.press("slash", "d", "u")
        assert screen.query_one(PreviewList).option_count == 1
        assert text(screen, "#preview-hint").startswith(
            "Enter Import 4 files (3 hidden by the filter)"
        )
        await pilot.press("escape")  # clears the filter first
        assert screen.query_one(PreviewList).option_count == 5
        assert screen.stage is Stage.PREVIEW
        await pilot.press("escape")
        assert screen.stage is Stage.PATH


async def test_import_3_a_subset_imports_only_the_ticked_files(library: Path, downloads: Path) -> None:
    app = BookmgrApp()
    async with app.run_test() as pilot:
        screen = await open_import(app, pilot)
        await submit_path(app, pilot, downloads)
        await pilot.press("space")  # untick broken.epub
        await pilot.press("enter")
        await settle(app, pilot)
        assert screen.stage is Stage.SUMMARY
        summary = text(screen, "#summary-text")
        assert summary.startswith("3 imported")
        assert "broken.epub" not in summary
        assert "notes.mobi" not in summary


@pytest.fixture
def nested(downloads: Path) -> Path:
    """`downloads` plus a subfolder with a new book, and a dot-folder with
    another that must never be listed or imported."""
    (downloads / "classics").mkdir()
    write_epub(downloads / "classics" / "persuasion.epub", Spec("Persuasion", "Jane Austen", isbn13(4)))
    (downloads / ".stash").mkdir()
    write_epub(downloads / ".stash" / "secret.epub", Spec("Secret", "Nobody", isbn13(5)))
    return downloads


async def test_import_1_ctrl_s_toggles_subfolders_while_typing(library: Path) -> None:
    app = BookmgrApp()
    async with app.run_test() as pilot:
        screen = await open_import(app, pilot)
        box = screen.query_one("#import-recursive", Checkbox)
        assert not box.value
        await pilot.press("ctrl+s")
        assert box.value and app.focused is screen.query_one("#import-path")
        await pilot.press("ctrl+s")
        assert not box.value


async def test_import_1_subfolders_checkbox_sits_under_the_hint(library: Path) -> None:
    app = BookmgrApp()
    async with app.run_test() as pilot:
        screen = await open_import(app, pilot)
        path, hint, box = (screen.query_one(s).region.y for s in ("#import-path", "#import-hint", "#import-recursive"))
        assert path < hint < box


def test_import_3_dot_files_and_dot_folders_are_left_out(nested: Path) -> None:
    names = [str(path.relative_to(nested)) for path in folder_files(nested, recursive=True)]
    assert "classics/persuasion.epub" in names
    assert not any(name.startswith(".") or "/." in name for name in names)
    assert files_in_dot_folders(nested)
    assert not files_in_dot_folders(nested / "classics")


async def test_import_3_subfolders_listed_without_dot_folders(library: Path, nested: Path) -> None:
    app = BookmgrApp()
    async with app.run_test() as pilot:
        screen = await open_import(app, pilot)
        await pilot.press("ctrl+s")
        await submit_path(app, pilot, nested)
        listed = {entry.path.name for entry in screen.entries}
        assert "persuasion.epub" in listed and "secret.epub" not in listed


async def test_import_3_everything_new_skips_dot_folder_books(library: Path, nested: Path) -> None:
    app = BookmgrApp()
    async with app.run_test() as pilot:
        screen = await open_import(app, pilot)
        await pilot.press("ctrl+s")
        await submit_path(app, pilot, nested)
        await pilot.press("enter")
        await settle(app, pilot)
        summary = text(screen, "#summary-text")
        assert "persuasion.epub → Persuasion" in summary
        assert "secret" not in summary.casefold()
        assert all(book.title != "Secret" for book in Library(library, source=NullSource()).scan())


async def test_import_7_bad_file_is_counted_and_the_rest_import(library: Path, downloads: Path) -> None:
    app = BookmgrApp()
    async with app.run_test() as pilot:
        screen = await open_import(app, pilot)
        await submit_path(app, pilot, downloads)
        await pilot.press("enter")
        await settle(app, pilot)
        summary = text(screen, "#summary-text")
        assert summary.splitlines()[0] == "3 imported · 1 skipped · 1 failed"
        assert "Failed\nbroken.epub: not a valid EPUB (zip) file" in summary
        assert "Skipped\nnotes.mobi" in summary


class Unreachable:
    """A source whose every request fails, as without a network. Not a
    `NullSource`: bookmgr takes that as offline [bookman 1.3.0 @ 1bdad64]."""

    def lookup_by_isbn(self, isbn: str):
        raise MetadataSourceError("network unreachable")

    def search(self, title: str, author: str | None = None):
        raise MetadataSourceError("network unreachable")

    def fetch_cover(self, url: str) -> bytes:
        raise MetadataSourceError("network unreachable")


async def test_import_5_esc_while_running_stays_and_hints_x(library: Path) -> None:
    app = BookmgrApp()
    async with app.run_test() as pilot:
        screen = await open_import(app, pilot)
        app.import_job = ImportJob(total=3)  # running: not finished
        screen.show_job(app.import_job)
        await pilot.pause()
        assert not screen.query_one("#run-hint").display
        await pilot.press("escape")
        assert app.screen is screen and screen.stage is Stage.RUNNING
        assert screen.query_one("#run-hint").display
        assert "Press x to stop it after the current file." in text(screen, "#run-hint")
        app.import_job = None


async def test_import_8_unreachable_lookup_notifies_once_and_carries_on(
    library: Path, downloads: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    app = BookmgrApp()
    notices: list[str] = []
    async with app.run_test() as pilot:
        await open_import(app, pilot)
        monkeypatch.setattr(app, "notify", lambda message, **kwargs: notices.append(message))
        app.library = Library(library, source=Unreachable())
        job = ImportJob(folder=downloads)
        app.start_import(job)
        await settle(app, pilot)
        assert notices == [
            "Open Library can't be reached. Books are added from their files only; the import carries on."
        ]
        assert job.counts["imported"] == 3
        assert sorted(book.title for book in job.lookups_failed) == ["Dune", "Emma", "Walden"]
        assert all(book.lookup is LookupOutcome.FAILED for book in job.lookups_failed)


async def test_import_6_x_stops_after_the_current_file(library: Path, downloads: Path) -> None:
    app = BookmgrApp()
    async with app.run_test() as pilot:
        await open_import(app, pilot)
        job = ImportJob(folder=downloads)
        job.stopping = True  # as if x was pressed during the first file
        app.start_import(job)
        await settle(app, pilot)
        assert job.stopped and job.done == 1
        summary = text(app.screen, "#summary-text")
        assert "Stopped at 1 of 5. Import the same folder again to continue." in summary
        assert str(app.screen.query_one("#summary-title", Static).render()) == "Import stopped"


async def test_import_9_conflict_explains_what_to_do(library: Path, tmp_path: Path) -> None:
    folder = tmp_path / "two-copies"
    folder.mkdir()
    write_epub(folder / "dune-a.epub", DUNE)
    write_epub(folder / "dune-b.epub", Spec("Dune", "Frank Herbert", DUNE.isbn, epub_cover=True))
    app = BookmgrApp()
    async with app.run_test() as pilot:
        screen = await open_import(app, pilot)
        await submit_path(app, pilot, folder)
        await pilot.press("enter")
        await settle(app, pilot)
        summary = text(screen, "#summary-text")
        assert summary.startswith("1 imported · 1 conflict\n")
        assert "dune-b.epub matched Dune (same ISBN)" in summary
        assert "copy it over" in summary


async def test_import_10_enter_returns_to_the_browser_on_the_first_import(
    library: Path, downloads: Path
) -> None:
    app = BookmgrApp()
    async with app.run_test() as pilot:
        screen = await open_import(app, pilot)
        await submit_path(app, pilot, downloads)
        await pilot.press("enter")
        await settle(app, pilot)
        summary = text(screen, "#summary-text")
        sections = [line for line in summary.splitlines() if line in ("Failed", "Imported", "Skipped")]
        assert sections == ["Failed", "Imported", "Skipped"]
        first = app.import_job.first_book
        await pilot.press("enter")
        await settle(app, pilot)
        assert isinstance(app.screen, BrowserScreen)
        assert app.import_job is None
        assert app.catalog is not None and len(app.catalog) == 3
        assert app.screen.selected_id == first.id


async def test_import_10_already_in_library_is_listed(library: Path, downloads: Path) -> None:
    Library(library, source=NullSource()).import_file(downloads / "emma.epub")
    app = BookmgrApp()
    async with app.run_test() as pilot:
        await open_import(app, pilot)
        app.start_import(ImportJob(folder=downloads))
        await settle(app, pilot)
        summary = text(app.screen, "#summary-text")
        assert "1 already in library" in summary.splitlines()[0]
        assert "Already in library\nemma.epub → Emma" in summary


async def test_g_5_quit_is_refused_while_importing(library: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    app = BookmgrApp()
    notices: list[str] = []
    monkeypatch.setattr(app, "notify", lambda message, **kwargs: notices.append(message))
    async with app.run_test() as pilot:
        await settle(app, pilot)
        app.import_job = ImportJob()  # running: not finished
        await pilot.press("q")
        assert app.is_running
        assert [Content.from_markup(n).plain for n in notices] == ["An import is running. Press x to stop it."]
        app.import_job = None


async def test_import_10_back_to_library_button_returns_to_the_browser(
    library: Path, downloads: Path
) -> None:
    app = BookmgrApp()
    async with app.run_test(size=(110, 34)) as pilot:
        await open_import(app, pilot)
        app.start_import(ImportJob(files=[downloads / "dune.epub"]))
        await settle(app, pilot)
        assert app.focused is app.screen.query_one("#summary-scroll")
        await pilot.click("#summary-done")
        await settle(app, pilot)
        assert isinstance(app.screen, BrowserScreen)
        assert app.catalog is not None and len(app.catalog) == 1


async def test_import_3_filter_is_a_view_enter_imports_every_ticked_file(
    library: Path, downloads: Path
) -> None:
    app = BookmgrApp()
    async with app.run_test() as pilot:
        screen = await open_import(app, pilot)
        await submit_path(app, pilot, downloads)
        await pilot.press("slash", "d", "u", "enter")  # filter to dune.epub, back to the list
        await pilot.press("enter")
        await settle(app, pilot)
        assert text(screen, "#summary-text").startswith("3 imported")
