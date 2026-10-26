"""The detail pane as its own screen, for narrow terminals (BROWSE-7)."""

from __future__ import annotations

from bookman import Book
from textual.app import ComposeResult
from textual.binding import Binding
from textual.screen import Screen
from textual.widgets import Footer, Header

from bookman_tui.widgets.book_detail import BookDetail


class DetailsScreen(Screen):
    """One book's `BookDetail`, full width, with Header and Footer.

    Pushed by the browser's `Enter` when the terminal is too narrow for the
    pane (under 100 columns). `Esc` pops back to the list with the same book
    selected. If the terminal is widened while it's open, it stays open
    until `Esc`: no screen changes under the user.
    """

    BINDINGS = [
        Binding("escape", "app.pop_screen", "Back"),
        Binding("F", "show_folder", "Folder"),
    ]

    def __init__(self, book: Book) -> None:
        super().__init__()
        self.book = book

    def compose(self) -> ComposeResult:
        yield Header()
        yield BookDetail(id="detail-screen")
        yield Footer()

    def on_mount(self) -> None:
        detail = self.query_one(BookDetail)
        detail.border_title = "Details"
        detail.book = self.book

    def action_show_folder(self) -> None:
        """`F`: this book's folder in the file manager (BROWSE-11)."""
        self.app.show_folder(self.book)
