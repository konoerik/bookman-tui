"""BookmanApp: opens the library and routes to the first screen (START)."""

from __future__ import annotations

import os
from copy import deepcopy
from pathlib import Path
from typing import TYPE_CHECKING

from bookman import (
    Book,
    BookmanError,
    ConfigError,
    ImportEvent,
    Library,
    LibraryLocation,
    LibraryNotConfiguredError,
    LibraryNotFoundError,
    LibraryOrigin,
    config_path,
    configured_library,
    locate_library,
)
from textual import work
from textual.app import App
from textual.binding import Binding
from textual.markup import escape
from textual.reactive import reactive
from textual.screen import Screen
from textual.signal import Signal

from bookman_tui import reveal
from bookman_tui.curating import batch_summary, could_help, lookup_summary
from bookman_tui.importing import ImportJob
from bookman_tui.keys import key_name, press
from bookman_tui.location import display_path, header_text, not_found_reason, sentence
from bookman_tui.prefs import Prefs, load_prefs, save_prefs
from bookman_tui.screens.browser import BrowserScreen
from bookman_tui.screens.import_screen import ImportScreen
from bookman_tui.screens.setup import SetupScreen
from bookman_tui.screens.start_problem import StartProblemScreen
from bookman_tui.store import Catalog, Grouping, Sort

if TYPE_CHECKING:
    from bookman_tui.screens.edit_dialog import EditDialog


def reload_summary(before: Catalog | None, after: Catalog) -> str:
    """"Reloaded · 33 books (2 new, 1 gone)" (BROWSE-5)."""
    noun = "book" if len(after) == 1 else "books"
    old = {book.id for book in before} if before is not None else set()
    new = {book.id for book in after}
    changes = [
        f"{count} {label}"
        for count, label in ((len(new - old), "new"), (len(old - new), "gone"))
        if count and before is not None
    ]
    detail = f" ({', '.join(changes)})" if changes else ""
    return f"Reloaded · {len(after)} {noun}{detail}"


class BookmanApp(App):
    """The bookman TUI. Owns the `Library` and the loaded books (ADR-3)."""

    TITLE = "bookman"
    CSS_PATH = "app.tcss"
    BINDINGS = [Binding("question_mark", "toggle_help", "Keys", key_display="?")]

    catalog: reactive[Catalog | None] = reactive(None, always_update=True)
    """Every book from the last scan (ADR-3); None while loading."""

    search: reactive[str] = reactive("")
    """The search narrowing the book list (FIND-1); empty for none."""

    sort: reactive[Sort] = reactive(Sort.TITLE)
    """The book list's order (BROWSE-8); remembered (BROWSE-10)."""

    grouping: reactive[Grouping] = reactive(Grouping.NONE)
    """The book list's grouping (BROWSE-9); remembered (BROWSE-10)."""

    lookup_after_edit: reactive[bool] = reactive(True)
    """"Look up after saving" in the edit dialog (EDIT-7); remembered."""

    looking_up: reactive[frozenset[str]] = reactive(frozenset())
    """Ids of the books a lookup is running for, shown as "looking up…"
    (LOOKUP-1)."""

    def __init__(self, library: Path | None = None) -> None:
        super().__init__()
        self.library_arg = library
        self.library: Library | None = None
        self.location: LibraryLocation | None = None
        self._problem_sub_title = ""
        self.import_job: ImportJob | None = None
        """The import running or just finished (ADR-10); None when there's none."""
        self.import_signal: Signal[ImportJob] = Signal(self, "import")
        """Published on every change to `import_job`, for the screens showing it."""
        self.writing: str | None = None
        """The change to the library running other than an import, as the
        notice that refuses another (G-2): "Looking up “Dune”."."""
        prefs = load_prefs()
        self.set_reactive(BookmanApp.sort, prefs.sort)
        self.set_reactive(BookmanApp.grouping, prefs.grouping)
        self.set_reactive(BookmanApp.lookup_after_edit, prefs.lookup_after_edit)

    def watch_sort(self) -> None:
        self._save_prefs()

    def watch_grouping(self) -> None:
        self._save_prefs()

    def watch_lookup_after_edit(self) -> None:
        self._save_prefs()

    def _save_prefs(self) -> None:
        """Remember the sort, grouping and "Look up after saving" for the
        next session (BROWSE-10, EDIT-7)."""
        try:
            save_prefs(Prefs(sort=self.sort, grouping=self.grouping, lookup_after_edit=self.lookup_after_edit))
        except OSError as error:
            self.log.warning(f"prefs not saved: {error}")

    def on_mount(self) -> None:
        self.open_library()

    def open_library(self, chosen: Path | None = None) -> None:
        """Open the library named by START-1, or the one just `chosen` in
        Setup, and show the first screen."""
        try:
            library = configured_library(chosen or self.library_arg)
        except LibraryNotConfiguredError:
            self.show_setup()
            return
        except ConfigError as error:
            # bookman's message starts with the file, which is shown above it.
            reason = str(error).removeprefix(f"{config_path()}: ")
            self._show(
                StartProblemScreen(
                    "bookman's config file can't be read",
                    display_path(config_path()),
                    "Choosing a folder replaces this file with a new one.",
                    sentence(reason),
                    can_retry=False,
                )
            )
            return
        except LibraryNotFoundError as error:
            self.sub_title = header_text(error.location)
            self._show(
                StartProblemScreen(
                    "Can't open the library",
                    display_path(error.path),
                    sentence(error.location.describe()),
                    not_found_reason(error.reason),
                    can_retry=True,
                )
            )
            return
        self.library = library
        if chosen is not None:
            # Saved by Setup, even if a flag or variable named another (SETUP-6).
            self.location = LibraryLocation(chosen, LibraryOrigin.CONFIG, config_path())
        else:
            self.location = locate_library(self.library_arg)
        self.sub_title = header_text(self.location)
        self.catalog = None
        self._show(BrowserScreen())
        self.load_books()

    def show_setup(self) -> None:
        self.sub_title = ""
        self._show(SetupScreen())

    def _show(self, screen: Screen) -> None:
        """Make `screen` the base screen, replacing the previous one and any
        screen pushed over it (Setup over a start problem, SETUP-7)."""
        while len(self.screen_stack) > 2:
            self.pop_screen()
        if len(self.screen_stack) > 1:
            self.switch_screen(screen)
        else:
            self.push_screen(screen)

    @work(thread=True, exclusive=True, group="scan")
    def load_books(self, *, announce: bool = False) -> None:
        """Read every book off the UI thread (G-1); `announce` confirms a
        reload with a notification (BROWSE-5)."""
        assert self.library is not None
        catalog = Catalog(self.library.scan())
        self.call_from_thread(self._loaded, catalog, announce)

    def _loaded(self, catalog: Catalog, announce: bool) -> None:
        previous = self.catalog
        self.catalog = catalog
        if announce:
            self.notify(reload_summary(previous, catalog))

    def on_start_problem_screen_retry_requested(self) -> None:
        self.open_library()

    def on_start_problem_screen_setup_requested(self) -> None:
        """Open Setup over the problem, so `Esc` can return to it (SETUP-7)."""
        self._problem_sub_title = self.sub_title
        self.sub_title = ""
        self.push_screen(SetupScreen(can_go_back=True))

    def on_setup_screen_back_requested(self) -> None:
        self.sub_title = self._problem_sub_title
        self.pop_screen()

    def on_setup_screen_library_chosen(self, message: SetupScreen.LibraryChosen) -> None:
        self.open_library(chosen=message.path)
        if self.library_arg is not None:
            override = "--library"
        elif os.environ.get("BOOKMAN_LIBRARY"):
            override = "$BOOKMAN_LIBRARY"
        else:
            return
        self.notify(f"Saved as your library. {override} still takes precedence the next time you start.")

    def action_reload(self) -> None:
        """Re-read the library from disk (BROWSE-5)."""
        if self.library is not None:
            self.load_books(announce=True)

    @property
    def importing(self) -> bool:
        """An import is running: the one write in progress (ADR-4, G-2)."""
        return self.import_job is not None and not self.import_job.finished

    @property
    def busy(self) -> str | None:
        """What change to the library is running, as a notice (G-2), or None."""
        if self.importing:
            return "An import is running."
        return self.writing

    def refuse_if_busy(self) -> bool:
        """Refuse another change while one runs, saying which (G-2)."""
        if self.busy is None:
            return False
        self.notify(f"{self.busy} Try again when it's done.", severity="warning")
        return True

    def _begin(self, notice: str) -> None:
        self.writing = notice

    def _finish(self, book: Book | None, message: str | None = None, *, select: str | None = None) -> None:
        """A change ended: put the book it returned in the catalog, keeping
        the selection on it (G-3) unless `select` names another (REVIEW-2)."""
        self.writing = None
        self.looking_up = frozenset()
        if book is not None and self.catalog is not None:
            if select is not None and isinstance(self.screen, BrowserScreen):
                self.screen.selected_id = select
            self.catalog.replace(book)
            self.catalog = self.catalog
        if message:
            self.notify(message)

    # Edit (EDIT, ADR-11)

    def save_edit(self, dialog: EditDialog, book: Book, changes: dict[str, str | None], lookup: bool) -> None:
        """Save the dialog's `changes`, then look the book up if `lookup` and
        it could help (EDIT-7, EDIT-8), as one change to the library."""
        self._begin(f"Saving “{book.title}”.")
        self.run_edit(dialog, book, changes, lookup)

    @work(thread=True, group="write")
    def run_edit(self, dialog: EditDialog, book: Book, changes: dict[str, str | None], lookup: bool) -> None:
        assert self.library is not None
        try:
            edited = self.library.edit(deepcopy(book), **changes)
        except BookmanError as error:
            self.call_from_thread(self._edit_refused, dialog, error)
            return
        if not (lookup and could_help(edited)):
            self.call_from_thread(self._edited, dialog, edited, "Saved")
            return
        self.call_from_thread(self._edited, dialog, edited, None)
        after = self.library.reidentify(deepcopy(edited))
        self.call_from_thread(self._finish, after, f"Saved · {lookup_summary(edited, after)}")

    def _edit_refused(self, dialog: EditDialog, error: BookmanError) -> None:
        """bookman refused the edit: say why in the dialog, which keeps
        everything typed (EDIT-5, G-4)."""
        self.writing = None
        dialog.refused(error)

    def _edited(self, dialog: EditDialog, book: Book, message: str | None) -> None:
        """The edit is saved: close the dialog; a lookup may follow."""
        dialog.dismiss(True)
        if message is not None:
            self._finish(book, message)
            return
        self.writing = f"Looking up “{book.title}”."
        self.looking_up = frozenset({book.id})
        if self.catalog is not None:
            self.catalog.replace(book)
            self.catalog = self.catalog

    # Look up (LOOKUP, IMPORT-10)

    def look_up(self, books: list[Book], *, batch: bool = False) -> None:
        """Look `books` up again in the background (LOOKUP-1). One book is
        reported by what changed (LOOKUP-2); a `batch` (IMPORT-10's `l`) by
        how many were updated, however many it holds."""
        if not books or self.refuse_if_busy():
            return
        what = f"“{books[0].title}”" if len(books) == 1 else f"{len(books)} books"
        self._begin(f"Looking up {what}.")
        self.looking_up = frozenset(book.id for book in books)
        self.run_lookups(books, batch or len(books) > 1)

    @work(thread=True, group="write")
    def run_lookups(self, books: list[Book], batch: bool) -> None:
        assert self.library is not None
        results = []
        for book in books:
            after = self.library.reidentify(deepcopy(book))
            results.append((book, after))
            if batch:
                self.call_from_thread(self._looked_up, after)
        if not batch:
            before, after = results[0]
            self.call_from_thread(self._finish, after, lookup_summary(before, after))
        else:
            self.call_from_thread(self._finish, None, batch_summary(results))

    def _looked_up(self, book: Book) -> None:
        """One book of several is done: show it, the rest still running."""
        self.looking_up = self.looking_up - {book.id}
        if self.catalog is not None:
            self.catalog.replace(book)
            self.catalog = self.catalog

    # Review (REVIEW)

    def toggle_reviewed(self, book: Book, *, then_select: str | None = None) -> None:
        """Mark `book` reviewed, or put it back in the queue (REVIEW-1);
        `then_select` is where the selection goes if it leaves Needs
        review (REVIEW-2)."""
        if self.refuse_if_busy():
            return
        self._begin(f"Updating “{book.title}”.")
        self.run_review(book, then_select)

    @work(thread=True, group="write")
    def run_review(self, book: Book, then_select: str | None) -> None:
        assert self.library is not None
        after = self.library.mark_reviewed(deepcopy(book), not book.reviewed)
        self.call_from_thread(self._finish, after, None, select=then_select if after.reviewed else None)

    # Folder (BROWSE-11)

    def show_folder(self, book: Book) -> None:
        """Open `book`'s folder in the file manager (BROWSE-11). Only reads
        the library, so no guard (BROWSE-13)."""
        folder = book.directory
        if folder is None or not folder.is_dir():
            self.notify(
                f"“{escape(book.title)}”'s folder is gone. " + press("ctrl+r", "reload the library"),
                severity="warning",
            )
            return
        self.run_open_folder(folder)

    @work(thread=True, group="reveal")
    def run_open_folder(self, folder: Path) -> None:
        try:
            reveal.open_folder(folder)
        except OSError as error:
            self.call_from_thread(self.notify, f"Couldn't open the folder: {error}", severity="error")

    def action_import_books(self) -> None:
        """`i`: open the import screen (IMPORT-1)."""
        if self.library is not None and not isinstance(self.screen, ImportScreen):
            self.push_screen(ImportScreen())

    def start_import(self, job: ImportJob) -> None:
        """Run `job` (ADR-10); the import screen follows it through the signal."""
        if self.refuse_if_busy():
            return
        self.import_job = job
        self.import_signal.publish(job)
        self.run_import(job)

    # Not `exclusive`: a thread worker can't be stopped, so cancelling it
    # would leave two writers. The guard decides what runs (ADR-10).
    @work(thread=True, group="write")
    def run_import(self, job: ImportJob) -> None:
        """Pull the import's events off the UI thread (ADR-4) and stop
        after a file's result once `x` was pressed (IMPORT-6)."""
        assert self.library is not None
        events = job.events(self.library)
        try:
            for event in events:
                self.call_from_thread(self._import_event, job, event)
                if event.outcome is not None and job.stopping:
                    break
        finally:
            events.close()
            self.call_from_thread(self._import_finished, job)

    def _import_event(self, job: ImportJob, event: ImportEvent) -> None:
        reachable = not job.lookups_failed
        job.record(event)
        if reachable and job.lookups_failed:
            self.notify(
                "Open Library can't be reached. Books are added from their files only; "
                "the import carries on.",
                severity="warning",
            )
        self.import_signal.publish(job)

    def _import_finished(self, job: ImportJob) -> None:
        job.finish()
        self.import_signal.publish(job)
        self.load_books()

    def close_import(self) -> None:
        """Leave the summary for the browser, on the first imported book
        (IMPORT-10)."""
        job = self.import_job
        self.import_job = None
        if isinstance(self.screen, ImportScreen):
            self.pop_screen()
        book = job.first_book if job is not None else None
        if book is not None and isinstance(self.screen, BrowserScreen):
            self.screen.select(book.id)

    def action_quit(self) -> None:
        """Quit, unless an import is running (G-5)."""
        if self.importing:
            self.notify("An import is running. " + press("x", "stop it"), severity="warning")
            return
        self.exit()

    def get_key_display(self, binding: Binding) -> str:
        """Keys in the footer and key panel as hints write them (G-7):
        `Esc` and `ctrl+r` rather than `esc` and `^r`."""
        return binding.key_display or key_name(binding.key)

    def action_toggle_help(self) -> None:
        """Show or hide the keys for the current screen (G-6)."""
        if self.screen.query("HelpPanel"):
            self.action_hide_help_panel()
        else:
            self.action_show_help_panel()


if __name__ == "__main__":
    BookmanApp().run()
