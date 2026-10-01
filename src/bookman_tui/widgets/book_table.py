"""The book list: a `DataTable` with one row per book (BROWSE-1/2/5, ADR-7)."""

from __future__ import annotations

from bookman import Book
from rich.cells import cell_len
from rich.text import Text
from textual.binding import Binding
from textual.events import Resize
from textual.message import Message
from textual.widgets import DataTable

AUTHOR_MAX = 28
TITLE_MIN = 12


class BookTable(DataTable):
    """One row per book, keyed by `Book.id`, with a row cursor.

    Columns: title, author, formats, and a review marker (BROWSE-1):
    - title: `Book.title`, taking all the width the other columns leave
      (BROWSE-7); a long one is cut with "…"
    - author: `Book.author`, or blank; capped at about 28 columns, with "…"
    - formats: the kinds in bookman's order, e.g. `EPUB PDF`
    - review: `?` (warning colour) when `Book.needs_review`, else blank

    `j`/`k` move the cursor as the arrows do (BROWSE-2).

    Messages:
        BookHighlighted: The cursor moved to another book (or the table was
            refilled and the cursor landed on one). Carries `book_id`, or
            None when the table is empty.
    """

    class BookHighlighted(Message):
        """The highlighted book changed."""

        def __init__(self, book_id: str | None) -> None:
            super().__init__()
            self.book_id = book_id

    BINDINGS = [
        Binding("j", "cursor_down", "Down", show=False),
        Binding("k", "cursor_up", "Up", show=False),
    ]

    def __init__(self, *, id: str | None = None) -> None:
        super().__init__(id=id, cursor_type="row", zebra_stripes=False)
        self._books: list[Book] = []
        self._title_width = 0

    def show(self, books: list[Book], selected_id: str | None = None) -> None:
        """Replace the rows with `books`, in the order given.

        The cursor goes to `selected_id` if it's among them (G-3). If it
        isn't (the book is gone after a reload, BROWSE-5), the cursor stays
        at the same row number, moved up if the list got shorter: that is
        the "nearest book". With no `selected_id`, the cursor starts at the
        first row. Posts `BookHighlighted` for wherever it lands.
        """
        previous_row = self.cursor_row
        self._books = list(books)
        self._fill()
        if not self._books:
            self.post_message(self.BookHighlighted(None))
            return
        ids = [book.id for book in self._books]
        if selected_id in ids:
            row = ids.index(selected_id)
        elif selected_id is not None:
            row = min(previous_row, len(ids) - 1)
        else:
            row = 0
        self.move_cursor(row=row, animate=False, scroll=True)
        self.post_message(self.BookHighlighted(ids[row]))

    @property
    def selected_id(self) -> str | None:
        """The id of the book under the cursor, or None if the table is empty."""
        if not self._books:
            return None
        return self._books[min(self.cursor_row, len(self._books) - 1)].id

    def _fill(self) -> None:
        """Rebuild columns and rows; the title column takes the spare width (BROWSE-7)."""
        books = self._books
        author_width = min(AUTHOR_MAX, max([cell_len("Author"), *(cell_len(b.author or "") for b in books)]))
        formats_width = max([cell_len("Formats"), *(cell_len(_formats(b)) for b in books)])
        self._title_width = self._spare_width(author_width + formats_width + 1)
        marker = Text("?", style=f"bold {self.app.theme_variables.get('warning', 'yellow')}")
        self.clear(columns=True)
        self.add_column("", width=1, key="review")
        self.add_column("Title", width=self._title_width, key="title")
        self.add_column("Author", width=author_width, key="author")
        self.add_column("Formats", width=formats_width, key="formats")
        for book in books:
            self.add_row(
                marker if book.needs_review else "",
                _cut(book.title),
                _cut(book.author or ""),
                _formats(book),
                key=book.id,
            )

    def _spare_width(self, others: int) -> int:
        padding = 2 * self.cell_padding * 4
        scrollbar = self.styles.scrollbar_size_vertical if len(self._books) > self.size.height - 1 else 0
        return max(TITLE_MIN, self.size.width - others - padding - scrollbar)

    def on_resize(self, event: Resize) -> None:
        if self._needs_refit():
            self.show(self._books, self.selected_id)

    def _needs_refit(self) -> bool:
        if not self._books:
            return False
        others = sum(self.columns[key].width for key in ("author", "formats", "review") if key in self.columns)
        return self._spare_width(others) != self._title_width

    def on_data_table_row_highlighted(self, event: DataTable.RowHighlighted) -> None:
        event.stop()
        self.post_message(self.BookHighlighted(event.row_key.value))


def _formats(book: Book) -> str:
    return " ".join(fmt.kind.name for fmt in book.formats)


def _cut(text: str) -> Text:
    return Text(text, no_wrap=True, overflow="ellipsis")
