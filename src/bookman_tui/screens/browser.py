"""Home: the library browser (BROWSE/FIND). M4: table, detail pane, counts."""

from __future__ import annotations

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.events import Resize
from textual.reactive import reactive
from textual.screen import Screen
from textual.widgets import DataTable, Footer, Header, Static

from bookman_tui.screens.details import DetailsScreen
from bookman_tui.store import Catalog
from bookman_tui.widgets.book_detail import BookDetail
from bookman_tui.widgets.book_table import BookTable

NARROW = 100
"""Below this many columns the detail pane is hidden (BROWSE-7)."""


def status_text(catalog: Catalog) -> str:
    """The status line: book count and review queue size (BROWSE-4)."""
    noun = "book" if len(catalog) == 1 else "books"
    return f"{len(catalog)} {noun} · {catalog.review_count} need review"


class BrowserScreen(Screen):
    """Every book in the library, with the selected one's details beside it."""

    BINDINGS = [
        Binding("q", "app.quit", "Quit"),
        Binding("ctrl+r", "app.reload", "Reload"),
        Binding("enter", "details", "Details"),
    ]

    selected_id: reactive[str | None] = reactive(None)
    """The highlighted book, kept across reloads by id (G-3)."""

    def compose(self) -> ComposeResult:
        yield Header()
        with Horizontal(id="main"):
            with Vertical(id="books"):
                yield BookTable(id="book-table")
                yield Static("Loading library…", id="books-message")
            yield BookDetail(id="detail")
        yield Static("", id="status")
        yield Footer()

    def on_mount(self) -> None:
        self.query_one("#books").border_title = "Library"
        self.query_one(BookDetail).border_title = "Details"
        self.watch(self.app, "catalog", self.show_catalog)

    def show_catalog(self, catalog: Catalog | None) -> None:
        table = self.query_one(BookTable)
        message = self.query_one("#books-message", Static)
        status = self.query_one("#status", Static)
        if catalog is None:
            message.update("Loading library…")
            status.update("")
        elif not catalog:
            message.update("No books yet — press [bold]i[/] to import")
        status.update(status_text(catalog) if catalog is not None else "")
        has_books = bool(catalog)
        table.display = has_books
        message.display = not has_books
        self.set_class(not has_books, "empty")
        if catalog:
            table.show(catalog.ordered(), self.selected_id)
            table.focus()

    def on_book_table_book_highlighted(self, message: BookTable.BookHighlighted) -> None:
        self.selected_id = message.book_id
        catalog = self.app.catalog
        self.query_one(BookDetail).book = catalog.get(message.book_id) if catalog and message.book_id else None

    def on_resize(self, event: Resize) -> None:
        self.set_class(event.size.width < NARROW, "narrow")
        self.refresh_bindings()

    def check_action(self, action: str, parameters: tuple[object, ...]) -> bool | None:
        if action == "details":
            # Offered only while the pane is hidden (BROWSE-7).
            return self.has_class("narrow") and self.selected_id is not None
        return True

    def on_data_table_row_selected(self, event: DataTable.RowSelected) -> None:
        # The table takes Enter itself; route it to the same action.
        event.stop()
        if self.check_action("details", ()):
            self.action_details()

    def action_details(self) -> None:
        book = self.query_one(BookDetail).book
        if book is not None:
            self.app.push_screen(DetailsScreen(book))
