"""Home: the library browser (BROWSE/FIND): table, detail pane, counts,
search, sort and grouping."""

from __future__ import annotations

from bookmgr import Book
from rich.markup import escape
from textual import on
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.events import DescendantBlur, Resize
from textual.reactive import reactive
from textual.screen import Screen
from textual.widgets import DataTable, Footer, Header, Input, Static

from bookmgr_tui.keys import press
from bookmgr_tui.screens.details import DetailsScreen
from bookmgr_tui.screens.edit_dialog import EditDialog
from bookmgr_tui.store import NEEDS_REVIEW, BookRow, Catalog, Grouping, Sort, arrange, match_summary, status_group
from bookmgr_tui.widgets.book_detail import BookDetail
from bookmgr_tui.widgets.book_table import BookTable

NARROW = 100
"""Below this many columns the detail pane is hidden (BROWSE-7)."""


def status_text(
    catalog: Catalog,
    listed: int | None = None,
    sort: Sort = Sort.TITLE,
    grouping: Grouping = Grouping.NONE,
) -> str:
    """The status line: book count, review queue size (BROWSE-4), and the
    sort and grouping in use (BROWSE-8).

    `listed` is how many books a search left in the list, if one is active:
    "12 of 340 books · …". The sort and grouping are left out for an empty
    library, which has nothing to order: "340 books · 12 need review · by
    author · grouped by status".
    """
    noun = "book" if len(catalog) == 1 else "books"
    shown = f"{listed} of " if listed is not None else ""
    parts = [f"{shown}{len(catalog)} {noun}", f"{catalog.review_count} need review"]
    if catalog:
        parts.append(f"by {sort.value}")
        if grouping is not Grouping.NONE:
            parts.append(f"grouped by {grouping.value}")
    return " · ".join(parts)


class BrowserScreen(Screen):
    """Every book in the library, with the selected one's details beside it."""

    AUTO_FOCUS = "#book-table"
    """The search box takes focus only on `/` (FIND-1)."""

    BINDINGS = [
        Binding("q", "app.quit", "Quit"),
        Binding("slash", "search", "Search", key_display="/"),
        Binding("escape", "clear_search", "Clear search", show=False),
        Binding("ctrl+r", "app.reload", "Reload"),
        Binding("enter", "details", "Details"),
        Binding("o", "sort", "Sort"),
        Binding("g", "group", "Group"),
        Binding("i", "app.import_books", "Import"),
        Binding("e", "edit", "Edit"),
        Binding("l", "look_up", "Look up"),
        Binding("v", "toggle_reviewed", "Reviewed"),
        Binding("F", "show_folder", "Folder"),
    ]

    selected_id: reactive[str | None] = reactive(None)
    """The highlighted book, kept across reloads and searches by id (G-3).
    Not cleared when a search matches nothing, so clearing it returns there."""

    def compose(self) -> ComposeResult:
        yield Header()
        with Horizontal(id="main"):
            with Vertical(id="books"):
                with Horizontal(id="search-bar"):
                    yield Input(placeholder="Search title, author or ISBN", id="search", compact=True)
                    yield Static("", id="search-counts")
                yield BookTable(id="book-table")
                yield Static("Loading library…", id="books-message")
            yield BookDetail(id="detail")
        yield Static("", id="status")
        yield Footer()

    def on_mount(self) -> None:
        self.query_one("#books").border_title = "Library"
        self.query_one(BookDetail).border_title = "Details"
        self.watch(self.app, "catalog", self.show_catalog)
        self.watch(self.app, "search", self.show_search, init=False)
        self.watch(self.app, "sort", self.show_arrangement, init=False)
        self.watch(self.app, "grouping", self.show_arrangement, init=False)
        self.watch(self.app, "looking_up", self.show_busy, init=False)

    def show_catalog(self, catalog: Catalog | None) -> None:
        """The books changed (load, reload or a write): a book that no longer
        matches leaves and the selection moves to the next one (FIND-6)."""
        self._show_books(self.selected_id)

    def show_search(self, query: str) -> None:
        """The search changed: keep the selected book if it still matches,
        else select the first match (FIND-6)."""
        catalog = self.app.catalog
        keep = catalog is not None and any(book.id == self.selected_id for book in catalog.search(query))
        self._show_books(self.selected_id if keep else None)

    def show_arrangement(self) -> None:
        """The sort or grouping changed: same books, same selection (G-3)."""
        self._show_books(self.selected_id)

    def _show_books(self, selected_id: str | None) -> None:
        catalog: Catalog | None = self.app.catalog
        query: str = self.app.search
        table = self.query_one(BookTable)
        message = self.query_one("#books-message", Static)
        status = self.query_one("#status", Static)
        searching = bool(query.strip())
        books = catalog.search(query) if catalog else []
        if catalog is None:
            message.update("Loading library…")
        elif not catalog:
            message.update("No books yet. " + press("i", "import some"))
        elif not books:
            message.update(f'No books match "{escape(query)}"')  # FIND-5
        if catalog is not None:
            status.update(status_text(catalog, len(books) if searching else None, self.app.sort, self.app.grouping))
        else:
            status.update("")
        self.query_one("#search-counts", Static).update(match_summary(books, query) if searching else "")
        table.display = bool(books)
        message.display = not books
        self.set_class(not catalog, "empty")
        self._show_search_box()
        if books:
            table.show(arrange(books, self.app.sort, self.app.grouping), selected_id)
            if not self.query_one("#search", Input).has_focus:
                table.focus()
        else:
            self.query_one(BookDetail).book = None

    def _show_search_box(self) -> None:
        """The box and its counts show while it has focus or a search is
        active (FIND-1, FIND-7)."""
        box = self.query_one("#search", Input)
        self.query_one("#search-bar").display = bool(self.app.catalog) and (
            box.has_focus or bool(self.app.search.strip())
        )

    def select(self, book_id: str) -> None:
        """Select `book_id` (e.g. the first book an import added, IMPORT-10)."""
        self.selected_id = book_id
        self._show_books(book_id)

    def action_search(self) -> None:
        self.query_one("#search-bar").display = True
        self.query_one("#search", Input).focus()

    def action_sort(self) -> None:
        """`o` moves to the next sort (BROWSE-8)."""
        self.app.sort = self.app.sort.next()

    def action_group(self) -> None:
        """`g` moves to the next grouping (BROWSE-9)."""
        self.app.grouping = self.app.grouping.next()

    def action_clear_search(self) -> None:
        """`Esc` clears the search from the box or the list (FIND-2, G-5)."""
        box = self.query_one("#search", Input)
        box.value = ""
        self.app.search = ""
        self.query_one(BookTable).focus()
        self._show_search_box()

    @on(Input.Changed, "#search")
    def search_changed(self, event: Input.Changed) -> None:
        self.app.search = event.value

    @on(Input.Submitted, "#search")
    def search_submitted(self) -> None:
        """`Enter` goes back to the list of matches."""
        self.query_one(BookTable).focus()

    def on_descendant_blur(self, event: DescendantBlur) -> None:
        if event.widget.id == "search":
            self._show_search_box()

    def on_book_table_book_highlighted(self, message: BookTable.BookHighlighted) -> None:
        if message.book_id is not None:
            self.selected_id = message.book_id
        catalog = self.app.catalog
        self.query_one(BookDetail).book = catalog.get(message.book_id) if catalog and message.book_id else None
        self.show_busy()

    def show_busy(self) -> None:
        """"Looking up…" on the selected book while it's looked up (LOOKUP-1)."""
        self.query_one(BookDetail).busy = self.selected_id in self.app.looking_up

    @property
    def selected_book(self) -> Book | None:
        """The book the list shows as selected, current from the catalog;
        None when nothing is listed (`selected_id` outlives a search that
        matches nothing)."""
        shown = self.query_one(BookDetail).book
        catalog = self.app.catalog
        return catalog.get(shown.id) if catalog and shown else None

    def action_edit(self) -> None:
        """`e`: the edit dialog for the selected book (EDIT-1)."""
        book = self.selected_book
        if book is not None and not self.app.refuse_if_busy():
            self.app.push_screen(EditDialog(book))

    def action_look_up(self) -> None:
        """`l`: look the selected book up again (LOOKUP-1)."""
        book = self.selected_book
        if book is not None:
            self.app.look_up([book])

    def action_toggle_reviewed(self) -> None:
        """`v`: reviewed on or off (REVIEW-1); working through the Needs
        review group, the selection moves on to the next book (REVIEW-2)."""
        book = self.selected_book
        if book is not None:
            self.app.toggle_reviewed(book, then_select=self._next_in_queue(book))

    def action_show_folder(self) -> None:
        """`F`: the selected book's folder in the file manager (BROWSE-11)."""
        book = self.selected_book
        if book is not None:
            self.app.show_folder(book)

    def _next_in_queue(self, book: Book) -> str | None:
        """The book REVIEW-2 moves to when `book` leaves Needs review: the
        next one listed there, else the previous; None if it's the only one
        or the list isn't grouped by status."""
        if self.app.grouping is not Grouping.STATUS or status_group(book) != NEEDS_REVIEW:
            return None
        books = self.app.catalog.search(self.app.search)
        queue = [
            row.book.id
            for row in arrange(books, self.app.sort, self.app.grouping)
            if isinstance(row, BookRow) and row.group == NEEDS_REVIEW
        ]
        if book.id not in queue or len(queue) == 1:
            return None
        index = queue.index(book.id)
        return queue[index + 1] if index + 1 < len(queue) else queue[index - 1]

    def on_resize(self, event: Resize) -> None:
        self.set_class(event.size.width < NARROW, "narrow")
        self.refresh_bindings()

    def check_action(self, action: str, parameters: tuple[object, ...]) -> bool | None:
        if action == "details":
            # Offered only while the pane is hidden (BROWSE-7).
            return self.has_class("narrow") and self.query_one(BookDetail).book is not None
        if action in ("search", "sort", "group"):
            return bool(self.app.catalog)
        if action in ("edit", "look_up", "toggle_reviewed", "show_folder"):
            return self.selected_book is not None
        if action == "clear_search":
            return bool(self.app.search) or self.query_one("#search", Input).has_focus
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
