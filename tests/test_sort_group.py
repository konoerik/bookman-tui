"""BROWSE-8/9/10: sort, grouping and remembered prefs (M7)."""

from __future__ import annotations

import dataclasses
import json
from pathlib import Path

import pytest
from bookmgr import Book, Library, NullSource
from textual.widgets import Static

from bookmgr_tui.app import BookmgrApp
from bookmgr_tui.prefs import Prefs, load_prefs, prefs_path, save_prefs
from bookmgr_tui.store import (
    CHECKED_BY_YOU,
    MATCHED_ONLINE,
    NEEDS_REVIEW,
    UNKNOWN_AUTHOR,
    BookRow,
    Catalog,
    GroupHeader,
    Grouping,
    Sort,
    arrange,
    matches,
)
from bookmgr_tui.widgets.book_detail import trust
from bookmgr_tui.widgets.book_table import BookTable


@pytest.fixture
def catalog(mock_root: Path) -> Catalog:
    return Catalog(Library(mock_root, source=NullSource()).scan())


def headers(rows) -> list[tuple[str, int]]:
    return [(row.label, row.size) for row in rows if isinstance(row, GroupHeader)]


def groups(rows) -> dict[str, list[Book]]:
    """Each header's label → the books listed under it, in order."""
    found: dict[str, list[Book]] = {}
    label = ""
    for row in rows:
        if isinstance(row, GroupHeader):
            label = row.label
            found[label] = []
        else:
            found[label].append(row.book)
    return found


def titles(books) -> list[str]:
    return [book.title for book in books]


# arrange() and the enums ----------------------------------------------------


def test_browse_8_o_cycles_title_author_and_wraps() -> None:
    assert Sort.TITLE.next() is Sort.AUTHOR
    assert Sort.AUTHOR.next() is Sort.TITLE


def test_browse_8_title_sort_is_the_browse_1_order(catalog: Catalog) -> None:
    assert [row.book for row in arrange(catalog, Sort.TITLE, Grouping.NONE)] == catalog.ordered()


def test_browse_8_author_sort_first_name_order_missing_last_ties_by_title(catalog: Catalog) -> None:
    books = [row.book for row in arrange(catalog, Sort.AUTHOR, Grouping.NONE)]
    authors = [book.author for book in books]
    named = [a for a in authors if a]
    assert named == sorted(named, key=str.casefold)
    assert authors[len(named) :] == [None] * (len(authors) - len(named))
    # Andy Weir's two books, then Frank Herbert's three, each in title order.
    assert titles(b for b in books if b.author == "Andy Weir") == ["The Martian", "Project Hail Mary"]
    herbert = [i for i, b in enumerate(books) if b.author == "Frank Herbert"]
    assert titles(books[i] for i in herbert) == ["Children of Dune", "Dune", "Dune Messiah"]
    assert herbert == list(range(herbert[0], herbert[0] + 3))


def test_browse_9_g_cycles_none_author_status_format_and_wraps() -> None:
    order = [Grouping.NONE]
    for _ in range(4):
        order.append(order[-1].next())
    assert order == [Grouping.NONE, Grouping.AUTHOR, Grouping.STATUS, Grouping.FORMAT, Grouping.NONE]


def test_browse_9_no_grouping_has_no_headers(catalog: Catalog) -> None:
    rows = arrange(catalog, Sort.TITLE, Grouping.NONE)
    assert all(isinstance(row, BookRow) and row.group == "" for row in rows)
    assert len(rows) == len(catalog)


def test_browse_9_author_groups_a_to_z_unknown_author_last(catalog: Catalog) -> None:
    labels = [label for label, _ in headers(arrange(catalog, Sort.TITLE, Grouping.AUTHOR))]
    assert labels[-1] == UNKNOWN_AUTHOR
    assert labels[:-1] == sorted(labels[:-1], key=str.casefold)
    assert dict(headers(arrange(catalog, Sort.TITLE, Grouping.AUTHOR)))["Frank Herbert"] == 3
    assert titles(groups(arrange(catalog, Sort.TITLE, Grouping.AUTHOR))[UNKNOWN_AUTHOR]) == [
        "field-guide-to-moths",
        "Quarterly Garden Planner",
        "statement-reader-locked",
    ]


def test_browse_9_status_groups_follow_the_detail_status_line(catalog: Catalog) -> None:
    by_status = groups(arrange(catalog, Sort.TITLE, Grouping.STATUS))
    headline = {CHECKED_BY_YOU: "Checked by you", NEEDS_REVIEW: "Needs review", MATCHED_ONLINE: "Matched online"}
    for label, books in by_status.items():
        for book in books:
            assert trust(book).headline.startswith(headline[label]), book.title


def test_browse_9_reviewed_book_in_the_queue_counts_as_checked(catalog: Catalog) -> None:
    walden = next(book for book in catalog if book.title == "Walden")
    rows = arrange([dataclasses.replace(walden, reviewed=True)], Sort.TITLE, Grouping.STATUS)
    assert headers(rows) == [(CHECKED_BY_YOU, 1)]


def test_browse_9_status_group_order_review_matched_checked(catalog: Catalog) -> None:
    assert headers(arrange(catalog, Sort.TITLE, Grouping.STATUS)) == [
        (NEEDS_REVIEW, catalog.review_count),
        (MATCHED_ONLINE, len(catalog) - catalog.review_count - 2),
        (CHECKED_BY_YOU, 2),
    ]


def test_browse_9_book_with_two_formats_is_in_both_format_groups(catalog: Catalog) -> None:
    by_format = groups(arrange(catalog, Sort.TITLE, Grouping.FORMAT))
    assert list(by_format) == ["EPUB", "PDF"]
    assert "Dune" in titles(by_format["EPUB"]) and "Dune" in titles(by_format["PDF"])


def test_browse_9_header_size_counts_books_listed_under_it(catalog: Catalog) -> None:
    for grouping in (Grouping.AUTHOR, Grouping.STATUS, Grouping.FORMAT):
        rows = arrange(catalog, Sort.TITLE, grouping)
        assert headers(rows) == [(label, len(books)) for label, books in groups(rows).items()]


def test_browse_9_books_sorted_within_each_group(catalog: Catalog) -> None:
    order = {book.id: i for i, book in enumerate(catalog.ordered())}
    for books in groups(arrange(catalog, Sort.TITLE, Grouping.FORMAT)).values():
        assert [order[b.id] for b in books] == sorted(order[b.id] for b in books)
    author_order = [row.book.id for row in arrange(catalog, Sort.AUTHOR, Grouping.NONE)]
    rank = {book_id: i for i, book_id in enumerate(author_order)}
    for books in groups(arrange(catalog, Sort.AUTHOR, Grouping.STATUS)).values():
        assert [rank[b.id] for b in books] == sorted(rank[b.id] for b in books)


def test_browse_9_search_applies_within_groups_and_drops_empty_groups(catalog: Catalog) -> None:
    rows = arrange(catalog.search("dune"), Sort.TITLE, Grouping.FORMAT)
    assert headers(rows) == [("EPUB", 3), ("PDF", 1)]
    assert all(matches(row.book, "dune") for row in rows if isinstance(row, BookRow))
    assert arrange([], Sort.TITLE, Grouping.AUTHOR) == []


def test_browse_9_row_keys_unique_when_a_book_is_listed_twice(catalog: Catalog) -> None:
    keys = [row.key for row in arrange(catalog, Sort.TITLE, Grouping.FORMAT) if isinstance(row, BookRow)]
    assert len(keys) == len(set(keys))
    assert len(keys) > len(catalog)


# The browser ----------------------------------------------------------------


async def loaded(app: BookmgrApp, pilot) -> BookTable:
    await app.workers.wait_for_complete()
    await pilot.pause()
    return app.screen.query_one(BookTable)


def status(app: BookmgrApp) -> str:
    return str(app.screen.query_one("#status", Static).render())


def cell_text(table: BookTable, row: int) -> list[str]:
    return [str(cell) for cell in table.get_row_at(row)]


def is_header(table: BookTable, row: int) -> bool:
    return cell_text(table, row)[1].startswith("── ")


def selected_title(app: BookmgrApp) -> str | None:
    table = app.screen.query_one(BookTable)
    assert app.catalog is not None
    book = app.catalog.get(table.selected_id) if table.selected_id else None
    return book.title if book else None


async def test_browse_8_o_reorders_the_list_and_keeps_the_selection(mock_root: Path) -> None:
    app = BookmgrApp(library=mock_root)
    async with app.run_test(size=(120, 40)) as pilot:
        table = await loaded(app, pilot)
        await pilot.press("j", "j", "j")
        chosen = selected_title(app)
        await pilot.press("o")
        await pilot.pause()
        assert app.sort is Sort.AUTHOR
        assert cell_text(table, 0)[2] == "Andy Weir"
        assert selected_title(app) == chosen
        assert app.screen.selected_id == table.selected_id


async def test_browse_8_status_line_names_sort_and_grouping(mock_root: Path) -> None:
    app = BookmgrApp(library=mock_root)
    async with app.run_test(size=(120, 40)) as pilot:
        await loaded(app, pilot)
        assert status(app) == "31 books · 6 need review · by title"
        await pilot.press("o", "g", "g")
        await pilot.pause()
        assert status(app) == "31 books · 6 need review · by author · grouped by status"


async def test_browse_9_header_row_shows_label_and_size(mock_root: Path) -> None:
    app = BookmgrApp(library=mock_root)
    async with app.run_test(size=(120, 40)) as pilot:
        table = await loaded(app, pilot)
        await pilot.press("g", "g")
        await pilot.pause()
        first = cell_text(table, 0)
        assert first[1].startswith(f"── {NEEDS_REVIEW} (6) ─")
        assert len(first[1]) == table.columns[table.ordered_columns[1].key].width


async def test_browse_9_j_k_skip_header_rows(mock_root: Path) -> None:
    app = BookmgrApp(library=mock_root)
    async with app.run_test(size=(120, 40)) as pilot:
        table = await loaded(app, pilot)
        await pilot.press("g", "g", "ctrl+home")  # Status: 6 in review, then a header
        await pilot.pause()
        assert table.cursor_row == 1
        await pilot.press(*"jjjjj")
        assert table.cursor_row == 6
        await pilot.press("j")
        await pilot.pause()
        assert table.cursor_row == 8 and not is_header(table, 8)
        await pilot.press("k")
        await pilot.pause()
        assert table.cursor_row == 6
        await pilot.press("k", "k", "k", "k", "k", "k")
        await pilot.pause()
        assert table.cursor_row == 1


async def test_browse_9_top_bottom_and_first_load_land_on_a_book(mock_root: Path) -> None:
    (prefs_path()).parent.mkdir(parents=True)
    save_prefs(Prefs(grouping=Grouping.AUTHOR))
    app = BookmgrApp(library=mock_root)
    async with app.run_test(size=(120, 40)) as pilot:
        table = await loaded(app, pilot)
        assert table.cursor_row == 1 and app.screen.selected_id == table.selected_id
        await pilot.press("ctrl+end")
        await pilot.pause()
        assert table.cursor_row == table.row_count - 1
        await pilot.pause()
        assert not is_header(table, table.cursor_row)
        await pilot.press("ctrl+home")
        await pilot.pause()
        assert table.cursor_row == 1


async def test_browse_9_g_keeps_the_selected_book(mock_root: Path) -> None:
    app = BookmgrApp(library=mock_root)
    async with app.run_test(size=(120, 40)) as pilot:
        await loaded(app, pilot)
        await pilot.press(*"jjjjjjj")
        chosen = selected_title(app)
        for _ in range(4):
            await pilot.press("g")
            await pilot.pause()
            assert selected_title(app) == chosen


async def test_browse_9_detail_pane_follows_book_rows_only(mock_root: Path) -> None:
    app = BookmgrApp(library=mock_root)
    async with app.run_test(size=(120, 40)) as pilot:
        table = await loaded(app, pilot)
        await pilot.press("g")
        await pilot.pause()
        seen = []
        for _ in range(8):
            await pilot.press("j")
            await pilot.pause()
            assert not is_header(table, table.cursor_row)
            seen.append(app.screen.selected_id)
            assert app.screen.selected_id == table.selected_id
        assert None not in seen


async def test_browse_9_search_within_groups_in_the_browser(mock_root: Path) -> None:
    app = BookmgrApp(library=mock_root)
    async with app.run_test(size=(120, 40)) as pilot:
        table = await loaded(app, pilot)
        await pilot.press("g", "g", "g")  # Format
        await pilot.press("slash", *"dune", "enter")
        await pilot.pause()
        assert [cell_text(table, i)[1].split(" (")[0] for i in (0, 4)] == ["── EPUB", "── PDF"]
        assert table.row_count == 6


# Prefs ----------------------------------------------------------------------


async def test_browse_10_sort_and_grouping_survive_a_restart(mock_root: Path) -> None:
    app = BookmgrApp(library=mock_root)
    async with app.run_test(size=(120, 40)) as pilot:
        await loaded(app, pilot)
        await pilot.press("o", "g", "g", "g")
        await pilot.pause()
    again = BookmgrApp(library=mock_root)
    async with again.run_test(size=(120, 40)) as pilot:
        await loaded(again, pilot)
        assert (again.sort, again.grouping) == (Sort.AUTHOR, Grouping.FORMAT)
        assert status(again).endswith("by author · grouped by format")


def test_browse_10_prefs_path_honours_the_override(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("BOOKMGR_TUI_PREFS", str(tmp_path / "p.json"))
    assert prefs_path() == tmp_path / "p.json"
    monkeypatch.delenv("BOOKMGR_TUI_PREFS")
    monkeypatch.setenv("BOOKMGR_CONFIG", str(tmp_path / "bookmgr" / "config.json"))
    assert prefs_path() == tmp_path / "bookmgr-tui" / "prefs.json"


def test_browse_10_missing_or_bad_prefs_file_gives_defaults(tmp_path: Path) -> None:
    path = tmp_path / "prefs.json"
    assert load_prefs(path) == Prefs()
    for junk in ("{not json", "[1, 2]", '"title"'):
        path.write_text(junk)
        assert load_prefs(path) == Prefs(), junk


def test_browse_10_unknown_value_falls_back_for_that_field_only(tmp_path: Path) -> None:
    path = tmp_path / "prefs.json"
    path.write_text(json.dumps({"sort": "added", "grouping": "status"}))
    assert load_prefs(path) == Prefs(sort=Sort.TITLE, grouping=Grouping.STATUS)


def test_browse_10_save_then_load_round_trips(tmp_path: Path) -> None:
    path = tmp_path / "nested" / "prefs.json"
    save_prefs(Prefs(Sort.AUTHOR, Grouping.FORMAT), path)
    assert load_prefs(path) == Prefs(Sort.AUTHOR, Grouping.FORMAT)
