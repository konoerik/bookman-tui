"""The book table (BROWSE-1/2/5/7, G-3), driven through the browser."""

from __future__ import annotations

import dataclasses
from pathlib import Path


from bookman_tui.app import BookmanApp
from bookman_tui.widgets.book_table import AUTHOR_MAX, BookTable


async def open_mock(mock_root: Path, size=(120, 30)):
    app = BookmanApp(library=mock_root)
    return app, app.run_test(size=size)


async def loaded(app: BookmanApp, pilot) -> BookTable:
    await app.workers.wait_for_complete()
    await pilot.pause()
    return app.screen.query_one(BookTable)


def row_of(table: BookTable, title: str) -> list:
    for key in table.rows:
        cells = table.get_row(key)
        if str(cells[1]) == title:
            return cells
    raise AssertionError(f"no row titled {title!r}")


def title_of(app: BookmanApp, book_id: str | None) -> str | None:
    assert app.catalog is not None
    book = app.catalog.get(book_id) if book_id else None
    return book.title if book else None


async def test_browse_1_row_shows_title_author_formats_and_review_marker(mock_root: Path) -> None:
    app, run = await open_mock(mock_root)
    async with run as pilot:
        table = await loaded(app, pilot)
        marker, title, author, formats = row_of(table, "Dune")
        assert (str(title), str(author), formats) == ("Dune", "Frank Herbert", "EPUB PDF")
        assert str(marker) == ""
        assert [str(c) for c in row_of(table, "Walden")][0] == "?"


async def test_browse_1_needs_review_marker_only_on_queue_books(mock_root: Path) -> None:
    app, run = await open_mock(mock_root)
    async with run as pilot:
        table = await loaded(app, pilot)
        marked = {str(table.get_row(key)[1]) for key in table.rows if str(table.get_row(key)[0]) == "?"}
        assert app.catalog is not None
        assert marked == {book.title for book in app.catalog if book.needs_review}


async def test_browse_2_j_and_k_move_the_cursor(mock_root: Path) -> None:
    app, run = await open_mock(mock_root)
    async with run as pilot:
        table = await loaded(app, pilot)
        assert table.cursor_row == 0
        await pilot.press("j", "j", "down")
        assert table.cursor_row == 3
        await pilot.press("k", "up")
        assert table.cursor_row == 1


async def test_browse_2_moving_posts_book_highlighted(mock_root: Path) -> None:
    app, run = await open_mock(mock_root)
    async with run as pilot:
        table = await loaded(app, pilot)
        await pilot.press("j")
        await pilot.pause()
        assert app.screen.selected_id == table.selected_id
        assert app.catalog is not None
        assert app.screen.selected_id == app.catalog.ordered()[1].id


async def test_g_3_show_keeps_selection_by_id(mock_root: Path) -> None:
    app, run = await open_mock(mock_root)
    async with run as pilot:
        table = await loaded(app, pilot)
        await pilot.press("j", "j", "j", "j")
        chosen = table.selected_id
        assert app.catalog is not None
        book = app.catalog.get(chosen)
        # The title moves the book to the top of the list; the cursor follows it.
        app.catalog.replace(dataclasses.replace(book, title="Aardvark Days"))
        table.show(app.catalog.ordered(), chosen)
        await pilot.pause()
        assert table.cursor_row == 0 and table.selected_id == chosen


async def test_browse_5_selection_moves_to_nearest_when_book_is_gone(mock_root: Path) -> None:
    app, run = await open_mock(mock_root)
    async with run as pilot:
        table = await loaded(app, pilot)
        await pilot.press("j", "j", "j")
        gone = table.selected_id
        assert app.catalog is not None
        remaining = [b for b in app.catalog.ordered() if b.id != gone]
        table.show(remaining, gone)
        await pilot.pause()
        assert table.cursor_row == 3
        assert table.selected_id == remaining[3].id


async def test_browse_5_selection_clamps_when_list_shrinks(mock_root: Path) -> None:
    app, run = await open_mock(mock_root)
    async with run as pilot:
        table = await loaded(app, pilot)
        table.move_cursor(row=30)
        await pilot.pause()
        gone = table.selected_id
        assert app.catalog is not None
        table.show(app.catalog.ordered()[:5], gone)
        await pilot.pause()
        assert table.cursor_row == 4


async def test_browse_5_reload_keeps_the_selection(mock_root: Path) -> None:
    app, run = await open_mock(mock_root)
    async with run as pilot:
        table = await loaded(app, pilot)
        await pilot.press("j", "j")
        chosen = title_of(app, table.selected_id)
        await pilot.press("ctrl+r")
        table = await loaded(app, pilot)
        assert title_of(app, table.selected_id) == chosen


async def test_browse_7_title_column_takes_the_spare_width(mock_root: Path) -> None:
    app, run = await open_mock(mock_root, size=(120, 30))
    async with run as pilot:
        table = await loaded(app, pilot)
        def fills() -> bool:
            used = sum(c.get_render_width(table) for c in table.columns.values())
            return table.size.width - 2 <= used <= table.size.width

        assert fills()
        await pilot.resize_terminal(160, 30)
        await pilot.pause()
        assert fills()
        # Under 100 columns the detail pane goes and the table takes its room.
        await pilot.resize_terminal(90, 30)
        await pilot.pause()
        assert fills() and table.size.width >= 88


async def test_browse_1_long_title_and_author_are_cut_with_ellipsis(mock_root: Path) -> None:
    app, run = await open_mock(mock_root, size=(80, 30))
    async with run as pilot:
        table = await loaded(app, pilot)
        assert table.columns["author"].width == AUTHOR_MAX
        cells = row_of(table, "Design Patterns: Elements of Reusable Object-Oriented Software")
        assert cells[1].overflow == "ellipsis" and cells[1].no_wrap
