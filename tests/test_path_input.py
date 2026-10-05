"""IMPORT-1 (path input with tab completion), also used by Setup (SETUP-1)."""

from __future__ import annotations

from pathlib import Path

import pytest
from textual.widgets import Input, Static

from bookman_tui.app import BookmanApp
from bookman_tui.widgets.path_input import Completion, complete, format_choices


@pytest.fixture
def tree(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """tmp_path holding Books/, Bookshelf.epub, Comics/, .hidden/; cwd and HOME."""
    (tmp_path / "Books").mkdir()
    (tmp_path / "Books" / "dune.epub").write_bytes(b"")
    (tmp_path / "Bookshelf.epub").write_bytes(b"")
    (tmp_path / "Comics").mkdir()
    (tmp_path / ".hidden").mkdir()
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("HOME", str(tmp_path))
    return tmp_path


def test_import_1_unique_match_completes_and_folders_get_a_slash(tree: Path) -> None:
    assert complete("Co") == Completion("Comics/")
    assert complete("Books/d") == Completion("Books/dune.epub")


def test_import_1_completes_the_longest_unambiguous_part(tree: Path) -> None:
    assert complete("B") == Completion("Books")


def test_import_1_second_tab_lists_the_choices(tree: Path) -> None:
    assert complete("Books") == Completion("Books", ("Books/", "Bookshelf.epub"))


def test_import_1_tilde_is_kept_in_the_text(tree: Path) -> None:
    assert complete("~/Co") == Completion("~/Comics/")


def test_import_1_hidden_entries_only_for_a_dot_prefix(tree: Path) -> None:
    assert complete("") == Completion("", ("Books/", "Bookshelf.epub", "Comics/"))
    assert complete(".h") == Completion(".hidden/")


def test_import_1_case_insensitive_when_nothing_matches_exactly(tree: Path) -> None:
    assert complete("co") == Completion("Comics/")


def test_import_1_no_match_or_missing_folder_changes_nothing(tree: Path) -> None:
    assert complete("Zz") == Completion("Zz")
    assert complete("nowhere/a") == Completion("nowhere/a")


def test_import_1_long_choice_lists_are_cut() -> None:
    assert format_choices(tuple("abcd"), limit=2) == "a  b  … 2 more"


async def test_setup_1_tab_completes_in_setup(tree: Path) -> None:
    app = BookmanApp()
    async with app.run_test() as pilot:
        field = app.screen.query_one("#setup-path", Input)
        field.value = "~/Co"
        await pilot.press("tab")
        assert field.value == "~/Comics/"
        assert app.focused is field
        field.value = "~/Books"
        await pilot.press("tab")
        hint = str(app.screen.query_one("#setup-hint", Static).render())
        assert hint == "Books/  Bookshelf.epub"
        await pilot.press("slash")  # editing replaces the choices with the usual hint
        hint = str(app.screen.query_one("#setup-hint", Static).render())
        assert hint.startswith("~/Books has other files in it.")  # "~/Books/"
