"""Correcting a book: a dialog over the browser (EDIT, ADR-11)."""

from __future__ import annotations

from bookman import Book, BookmanError
from textual import on
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.markup import escape
from textual.screen import ModalScreen
from textual.widgets import Button, Checkbox, Input, Label, Static

from bookman_tui.curating import edit_changes
from bookman_tui.location import sentence
from bookman_tui.widgets.book_detail import author_note, files_text, trust_text


class LookupBox(Checkbox, inherit_bindings=False):
    """"Look up after saving" (EDIT-7). Only `Space` toggles it, so `Enter`
    still saves from here (EDIT-3)."""

    BINDINGS = [Binding("space", "toggle_button", "Toggle", show=False)]


class EditDialog(ModalScreen[bool]):
    """Title, author and ISBN of one book, under what helps work out what the
    book is (EDIT-1). Dismissed with True once bookman has saved the edit,
    False when cancelled or nothing changed.

    The App runs the save (ADR-4) and calls `refused` or dismisses the
    dialog when it's done.
    """

    BINDINGS = [
        Binding("escape", "cancel", "Cancel"),
        Binding("enter", "save", "Save"),
    ]

    def __init__(self, book: Book) -> None:
        super().__init__()
        self.book = book

    def compose(self) -> ComposeResult:
        book = self.book
        with Vertical(id="edit-dialog"):
            yield Static(f"Edit “{escape(book.title)}”", id="edit-heading")
            yield Static(files_text(book), id="edit-files")
            yield Static(trust_text(book), id="edit-trust")
            yield Label("Title")
            yield Input(book.title, id="edit-title", compact=True)
            yield Label("Author")
            yield Input(book.author or "", placeholder="Unknown", id="edit-author", compact=True)
            if author_note(book) and book.record_author:
                yield Button(
                    f"Use Open Library's spelling: {escape(book.record_author)}",
                    id="edit-record-author",
                    compact=True,
                )
            yield Label("ISBN")
            yield Input(book.isbn or "", placeholder="None", id="edit-isbn", compact=True)
            yield Static("", id="edit-error")
            yield LookupBox("Look up after saving", self.app.lookup_after_edit, id="edit-lookup", compact=True)
            with Horizontal(id="edit-buttons"):
                yield Button("Cancel", id="edit-cancel", compact=True)
                yield Button("Save ⏎", variant="primary", id="edit-save", compact=True)

    def on_mount(self) -> None:
        self.query_one("#edit-error").display = False
        self.query_one("#edit-title", Input).focus()

    @on(Button.Pressed, "#edit-record-author")
    def use_record_author(self) -> None:
        """EDIT-2: the source's spelling into the author field."""
        if self.book.record_author:
            self.query_one("#edit-author", Input).value = self.book.record_author

    @on(Checkbox.Changed, "#edit-lookup")
    def remember_lookup(self, event: Checkbox.Changed) -> None:
        """The last choice holds for the next edit and session (EDIT-7)."""
        self.app.lookup_after_edit = event.value

    @on(Input.Submitted)
    @on(Button.Pressed, "#edit-save")
    def action_save(self) -> None:
        """`Enter`: save, or just close if nothing changed (EDIT-3, EDIT-4)."""
        if self.query_one("#edit-dialog").disabled:
            return
        changes = edit_changes(
            self.book,
            self.query_one("#edit-title", Input).value,
            self.query_one("#edit-author", Input).value,
            self.query_one("#edit-isbn", Input).value,
        )
        if not changes:
            self.dismiss(False)
            return
        if changes.get("title") == "":
            self._show_error("A book needs a title.", "#edit-title")
            return
        self.query_one("#edit-dialog").disabled = True
        self.app.save_edit(self, self.book, changes, self.query_one(LookupBox).value)

    @on(Button.Pressed, "#edit-cancel")
    def action_cancel(self) -> None:
        if not self.query_one("#edit-dialog").disabled:
            self.dismiss(False)

    def refused(self, error: BookmanError) -> None:
        """bookman refused the edit (EDIT-5, G-4): say why, keep what was
        typed, and put focus on the field it's about."""
        self.query_one("#edit-dialog").disabled = False
        message = str(error)
        field = "#edit-isbn" if "isbn" in message.lower() else "#edit-title"
        self._show_error(sentence(message) + ".", field)

    def _show_error(self, message: str, field: str) -> None:
        error = self.query_one("#edit-error", Static)
        error.update(escape(message))
        error.display = True
        self.query_one(field, Input).focus()
