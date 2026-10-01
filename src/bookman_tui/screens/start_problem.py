"""Shown instead of the browser when the library can't be opened (START-4/5)."""

from __future__ import annotations

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.message import Message
from textual.screen import Screen
from textual.widgets import Button, Footer, Header, Static


class StartProblemScreen(Screen):
    """What went wrong opening the library, and the ways out.

    Messages:
        RetryRequested: Try opening the library again (START-5 only).
        SetupRequested: Choose another folder (START-3's Setup).
    """

    class RetryRequested(Message):
        """The user asked to try opening the library again."""

    class SetupRequested(Message):
        """The user asked to choose another folder."""

    def __init__(self, heading: str, path: str, where: str, reason: str, *, can_retry: bool) -> None:
        super().__init__()
        self.heading = heading
        self.path = path
        self.where = where
        self.reason = reason
        self.can_retry = can_retry

    BINDINGS = [
        Binding("r", "retry", "Retry"),
        Binding("s", "setup", "Choose another folder"),
        Binding("q", "app.quit", "Quit"),
    ]

    def check_action(self, action: str, parameters: tuple[object, ...]) -> bool | None:
        # A bad config file can't be retried away (START-4): hide `r` there.
        return self.can_retry if action == "retry" else True

    def compose(self) -> ComposeResult:
        yield Header()
        with Vertical(id="problem"):
            yield Static(self.heading, id="problem-heading")
            yield Static(self.path, id="problem-path")
            yield Static(self.where, id="problem-where")
            yield Static(self.reason, id="problem-reason")
            with Horizontal(id="problem-buttons"):
                if self.can_retry:
                    yield Button("Retry  r", id="retry", variant="primary", action="screen.retry", compact=True)
                yield Button(
                    "Choose another folder  s",
                    variant="default" if self.can_retry else "primary",
                    action="screen.setup",
                    compact=True,
                )
                yield Button("Quit  q", action="app.quit", compact=True)
        yield Footer()

    def action_retry(self) -> None:
        self.post_message(self.RetryRequested())

    def action_setup(self) -> None:
        self.post_message(self.SetupRequested())
