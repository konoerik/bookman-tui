"""The book list: a `DataTable` with a row per book and group headers
(BROWSE-1/2/5/9, ADR-7)."""

from __future__ import annotations

from bookman import Book
from rich.cells import cell_len
from rich.text import Text
from textual.binding import Binding
from textual.events import Resize
from textual.message import Message
from textual.widgets import DataTable

from bookman_tui.store import BookRow, GroupHeader, Row

AUTHOR_MAX = 28
TITLE_MIN = 12


class BookTable(DataTable):
    """A row per book, keyed by `BookRow.key`, with a row cursor; when the
    list is grouped, a header row before each group (BROWSE-9).

    Columns: title, author, formats, and a review marker (BROWSE-1):
    - title: `Book.title`, taking all the width the other columns leave
      (BROWSE-7); a long one is cut with "…"
    - author: `Book.author`, or blank; capped at about 28 columns, with "…"
    - formats: the kinds in bookman's order, e.g. `EPUB PDF`
    - review: `?` (warning colour) when `Book.needs_review`, else blank

    `j`/`k` move the cursor as the arrows do (BROWSE-2). The cursor never
    rests on a header row: wherever it lands (keys, mouse, a refill) it
    moves on to the next book in the direction it was going.

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
        self._rows: list[Row] = []
        self._book_row = 0
        """Where the cursor last rested on a book; tells which way it was
        going when it lands on a header."""
        self._title_width = 0

    def show(self, rows: list[Row], selected_id: str | None = None) -> None:
        """Replace the rows with `rows` (from `store.arrange`), in that order.

        The cursor goes to `selected_id` if it's among them, on its first
        row if it's listed twice (G-3). If it isn't (the book is gone after
        a reload, BROWSE-5), the cursor stays at the same row number, moved
        up if the list got shorter: that is the "nearest book". With no
        `selected_id`, the cursor starts at the first book. Posts
        `BookHighlighted` for wherever it lands.
        """
        previous_row = self.cursor_row
        self._rows = list(rows)
        self._fill()
        if not self._books():
            self.post_message(self.BookHighlighted(None))
            return
        ids = [row.book.id if isinstance(row, BookRow) else None for row in self._rows]
        if selected_id in ids:
            target = ids.index(selected_id)
        elif selected_id is not None:
            target = self._nearest_book(min(previous_row, len(ids) - 1), step=1)
        else:
            target = self._nearest_book(0, step=1)
        self._book_row = target
        self.move_cursor(row=target, animate=False, scroll=True)
        self.post_message(self.BookHighlighted(ids[target]))

    @property
    def selected_id(self) -> str | None:
        """The id of the book under the cursor, or None if the table is empty."""
        if not self._books():
            return None
        row = self._rows[self._nearest_book(min(self.cursor_row, len(self._rows) - 1), step=1)]
        assert isinstance(row, BookRow)
        return row.book.id

    def _books(self) -> list[Book]:
        return [row.book for row in self._rows if isinstance(row, BookRow)]

    def _nearest_book(self, index: int, *, step: int) -> int:
        """The first book row from `index` on in direction `step`, else the
        nearest the other way. Needs at least one book row."""
        forward = range(index, len(self._rows)) if step > 0 else range(index, -1, -1)
        backward = range(index, -1, -1) if step > 0 else range(index, len(self._rows))
        for candidates in (forward, backward):
            for i in candidates:
                if isinstance(self._rows[i], BookRow):
                    return i
        raise ValueError("no book rows")

    def _fill(self) -> None:
        """Rebuild columns and rows; the title column takes the spare width (BROWSE-7)."""
        books = self._books()
        author_width = min(AUTHOR_MAX, max([cell_len("Author"), *(cell_len(b.author or "") for b in books)]))
        formats_width = max([cell_len("Formats"), *(cell_len(_formats(b)) for b in books)])
        self._title_width = self._spare_width(author_width + formats_width + 1)
        marker = Text("?", style=f"bold {self.app.theme_variables.get('warning', 'yellow')}")
        self.clear(columns=True)
        self.add_column("", width=1, key="review")
        self.add_column("Title", width=self._title_width, key="title")
        self.add_column("Author", width=author_width, key="author")
        self.add_column("Formats", width=formats_width, key="formats")
        header_style = f"bold {self.app.theme_variables.get('accent', 'blue')}"
        widths = (1, self._title_width, author_width, formats_width)
        for row in self._rows:
            if isinstance(row, GroupHeader):
                self.add_row(*_header_cells(row, widths, header_style), key=f"header/{row.label}")
                continue
            book = row.book
            self.add_row(
                marker if book.needs_review else "",
                _cut(book.title),
                _cut(book.author or ""),
                _formats(book),
                key=row.key,
            )

    def _spare_width(self, others: int) -> int:
        padding = 2 * self.cell_padding * 4
        scrollbar = self.styles.scrollbar_size_vertical if len(self._rows) > self.size.height - 1 else 0
        return max(TITLE_MIN, self.size.width - others - padding - scrollbar)

    def on_resize(self, event: Resize) -> None:
        if self._needs_refit():
            self.show(self._rows, self.selected_id)

    def _needs_refit(self) -> bool:
        if not self._rows:
            return False
        others = sum(self.columns[key].width for key in ("author", "formats", "review") if key in self.columns)
        return self._spare_width(others) != self._title_width

    def on_data_table_row_highlighted(self, event: DataTable.RowHighlighted) -> None:
        """Hop off a header row, else report the book (BROWSE-9).

        Goes by where the cursor is now rather than the event's row: a
        refill can leave an older event queued behind a newer move.
        """
        event.stop()
        if not self._rows:
            return
        current = min(self.cursor_row, len(self._rows) - 1)
        row = self._rows[current]
        if isinstance(row, GroupHeader):
            step = 1 if current >= self._book_row else -1
            self.move_cursor(row=self._nearest_book(current, step=step), animate=False)
            return
        self._book_row = current
        self.post_message(self.BookHighlighted(row.book.id))


def _header_cells(header: GroupHeader, widths: tuple[int, ...], style: str) -> list[Text]:
    """`── Frank Herbert (3) ─────` across the title cell; a rule under the
    other columns."""
    marker, title, *rest = widths
    label = f"── {header.label} ({header.size}) "
    if cell_len(label) > title:
        label_text = Text(label, style=style, no_wrap=True, overflow="ellipsis")
    else:
        label_text = Text(label + "─" * (title - cell_len(label)), style=style, no_wrap=True)
    return [Text("─" * marker, style=style), label_text, *(Text("─" * width, style=style) for width in rest)]


def _formats(book: Book) -> str:
    return " ".join(fmt.kind.name for fmt in book.formats)


def _cut(text: str) -> Text:
    return Text(text, no_wrap=True, overflow="ellipsis")
