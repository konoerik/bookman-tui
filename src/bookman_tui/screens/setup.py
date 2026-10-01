"""First run: choose the folder for the library (START-3, SETUP)."""

from __future__ import annotations

import dataclasses
import os
from dataclasses import dataclass
from enum import Enum
from pathlib import Path

from bookman import (
    BookmanError,
    Config,
    ConfigError,
    configured_library,
    is_library,
    load_config,
    save_config,
)
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Vertical
from textual.message import Message
from textual.reactive import reactive
from textual.screen import Screen
from textual.widgets import Footer, Header, Input, Static

from bookman_tui.location import display_path

NOT_EMPTY = (
    "A library needs an empty folder: bookman fills it with its own copies of "
    "your books. Choose a new or empty folder, then import from this one."
)


class Choice(Enum):
    """What `Enter` does with the typed path."""

    NOTHING = "nothing"  # no path typed yet
    CREATE = "create"  # SETUP-2: missing, create it after a confirmation
    OPEN = "open"  # SETUP-5: an existing library
    ADOPT = "adopt"  # SETUP-5: an existing empty folder
    REFUSE = "refuse"  # SETUP-4/5: a file, or a folder of other things


@dataclass(frozen=True)
class Assessment:
    """The typed path, what `Enter` would do with it, and the line saying so."""

    choice: Choice
    path: Path | None
    message: str


def assess(text: str) -> Assessment:
    """Judge a typed path without touching anything (SETUP-1..5)."""
    text = text.strip()
    if not text:
        return Assessment(Choice.NOTHING, None, "Type the folder your library should live in.")
    path = Path(os.path.abspath(Path(text).expanduser()))
    try:
        if not path.exists():
            return Assessment(Choice.CREATE, path, "New folder: Enter creates it.")
        if not path.is_dir():
            return Assessment(Choice.REFUSE, path, "This is a file, not a folder.")
        if is_library(path):
            return Assessment(Choice.OPEN, path, "Existing library: Enter opens it.")
        if all(entry.name.startswith(".") for entry in path.iterdir()):
            return Assessment(Choice.ADOPT, path, "Empty folder: Enter makes it your library.")
    except OSError as error:
        return Assessment(Choice.REFUSE, path, f"Can't use this folder: {error.strerror or error}.")
    return Assessment(Choice.REFUSE, path, NOT_EMPTY)


class SetupScreen(Screen):
    """Where the library should go.

    Messages:
        LibraryChosen: The library at `path` is ready and saved to the config.
    """

    class LibraryChosen(Message):
        """A library was opened (or created) at `path` and saved."""

        def __init__(self, path: Path) -> None:
            super().__init__()
            self.path = path

    BINDINGS = [Binding("ctrl+q", "app.quit", "Quit", priority=True)]

    confirming: reactive[bool] = reactive(False)
    """The first `Enter` on a missing folder asked; the next one creates it (SETUP-2)."""

    def compose(self) -> ComposeResult:
        yield Header()
        with Vertical(id="setup"):
            yield Static("Choose a folder for your library", id="setup-heading")
            yield Static(
                "bookman keeps its own copies of your books there. "
                "It's remembered for both bookman-tui and bookman.",
                id="setup-intro",
            )
            yield Input(placeholder="~/Books", id="setup-path")
            yield Static("", id="setup-hint")
        yield Footer()

    def on_mount(self) -> None:
        self.show(assess(""))

    def show(self, assessment: Assessment, *, error: bool | None = None) -> None:
        hint = self.query_one("#setup-hint", Static)
        hint.update(assessment.message)
        hint.set_class(assessment.choice is Choice.REFUSE if error is None else error, "error")
        hint.remove_class("confirm")

    def on_input_changed(self, event: Input.Changed) -> None:
        self.confirming = False
        self.show(assess(event.value))

    def on_input_submitted(self, event: Input.Submitted) -> None:
        assessment = assess(event.value)
        if assessment.choice in (Choice.NOTHING, Choice.REFUSE):
            self.show(assessment)
            return
        assert assessment.path is not None
        if assessment.choice is Choice.CREATE and not self.confirming:
            self.confirming = True
            self.show(
                Assessment(
                    Choice.CREATE,
                    assessment.path,
                    f"Create {display_path(assessment.path)}? Enter creates it.",
                )
            )
            self.query_one("#setup-hint").add_class("confirm")
            return
        self.choose(assessment.path, create=assessment.choice is Choice.CREATE)

    def choose(self, path: Path, *, create: bool) -> None:
        """Open or create the library at `path`, then save it (SETUP-3)."""
        try:
            try:
                current = load_config()
            except ConfigError:
                # START-4: bookman reads the config to open any library, so
                # an unreadable one is replaced before opening.
                save_config(Config(library=path))
                current = None
            configured_library(path, create=create)
            saved = dataclasses.replace(current, library=path) if current else Config(library=path)
            save_config(saved)
        except (BookmanError, OSError) as error:
            self.confirming = False
            self.show(Assessment(Choice.REFUSE, path, f"Can't use this folder: {error}"), error=True)
            return
        self.post_message(self.LibraryChosen(path))
