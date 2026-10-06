"""BookmanApp: opens the library and routes to the first screen (START)."""

from __future__ import annotations

import os
from pathlib import Path

from bookman import (
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
from textual.reactive import reactive
from textual.screen import Screen
from textual.signal import Signal

from bookman_tui.importing import ImportJob
from bookman_tui.location import display_path, header_text, not_found_reason, sentence
from bookman_tui.prefs import Prefs, load_prefs, save_prefs
from bookman_tui.screens.browser import BrowserScreen
from bookman_tui.screens.import_screen import ImportScreen
from bookman_tui.screens.setup import SetupScreen
from bookman_tui.screens.start_problem import StartProblemScreen
from bookman_tui.store import Catalog, Grouping, Sort


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
        prefs = load_prefs()
        self.set_reactive(BookmanApp.sort, prefs.sort)
        self.set_reactive(BookmanApp.grouping, prefs.grouping)

    def watch_sort(self) -> None:
        self._save_prefs()

    def watch_grouping(self) -> None:
        self._save_prefs()

    def _save_prefs(self) -> None:
        """Remember the sort and grouping for the next session (BROWSE-10)."""
        try:
            save_prefs(Prefs(sort=self.sort, grouping=self.grouping))
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

    def action_import_books(self) -> None:
        """`i`: open the import screen (IMPORT-1)."""
        if self.library is not None and not isinstance(self.screen, ImportScreen):
            self.push_screen(ImportScreen())

    def start_import(self, job: ImportJob) -> None:
        """Run `job` (ADR-10); the import screen follows it through the signal."""
        if self.importing:
            self.notify("An import is already running.", severity="warning")
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
            self.notify("An import is running. Stop it with x first.", severity="warning")
            return
        self.exit()

    def action_toggle_help(self) -> None:
        """Show or hide the keys for the current screen (G-6)."""
        if self.screen.query("HelpPanel"):
            self.action_hide_help_panel()
        else:
            self.action_show_help_panel()


if __name__ == "__main__":
    BookmanApp().run()
