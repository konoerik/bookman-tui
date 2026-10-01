"""BookmanApp: opens the library and routes to the first screen (START)."""

from __future__ import annotations

import os
from pathlib import Path

from bookman import (
    ConfigError,
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

from bookman_tui.location import display_path, header_text, not_found_reason, sentence
from bookman_tui.screens.browser import BrowserScreen
from bookman_tui.screens.setup import SetupScreen
from bookman_tui.screens.start_problem import StartProblemScreen
from bookman_tui.store import Catalog


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

    def __init__(self, library: Path | None = None) -> None:
        super().__init__()
        self.library_arg = library
        self.library: Library | None = None
        self.location: LibraryLocation | None = None

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
            location = locate_library(self.library_arg)
            self.sub_title = header_text(location)
            self._show(
                StartProblemScreen(
                    "Can't open the library",
                    display_path(error.path),
                    sentence(location.describe()),
                    not_found_reason(error.path),
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
        """Make `screen` the base screen, replacing the previous one."""
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
        self.show_setup()

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

    def action_toggle_help(self) -> None:
        """Show or hide the keys for the current screen (G-6)."""
        if self.screen.query("HelpPanel"):
            self.action_hide_help_panel()
        else:
            self.action_show_help_panel()


if __name__ == "__main__":
    BookmanApp().run()
