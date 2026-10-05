"""A path `Input` with shell-style `Tab` completion (IMPORT-1, SETUP-1)."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from textual.binding import Binding
from textual.message import Message
from textual.widgets import Input


@dataclass(frozen=True)
class Completion:
    """What `Tab` does to the typed text.

    Attributes:
        text: The text after completing; the same text when nothing could
            be added.
        choices: The names still matching when nothing could be added and
            there's more than one (folders end in `/`); empty otherwise.
    """

    text: str
    choices: tuple[str, ...] = ()


def complete(text: str) -> Completion:
    """Complete `text` as far as it is unambiguous (IMPORT-1).

    The part after the last `/` is a name prefix, matched against the
    entries of the folder before it (the current folder when there's no
    `/`). `~` is expanded for the lookup but kept in the text. Hidden
    entries match only when the prefix starts with a dot. Matching is
    case-sensitive, falling back to case-insensitive when nothing matches
    exactly. A single folder match gets a trailing `/`.
    """
    head, sep, prefix = text.rpartition("/")
    folder_text = head + sep
    folder = Path(os.path.expanduser(folder_text or "."))
    try:
        names = [
            entry.name + ("/" if entry.is_dir() else "")
            for entry in folder.iterdir()
            if prefix.startswith(".") or not entry.name.startswith(".")
        ]
    except OSError:
        return Completion(text)
    matches = sorted(name for name in names if name.startswith(prefix))
    if not matches:
        folded = prefix.casefold()
        matches = sorted(name for name in names if name.casefold().startswith(folded))
    if not matches:
        return Completion(text)
    if len(matches) == 1:
        return Completion(folder_text + matches[0])
    common = os.path.commonprefix(matches)
    if len(common) > len(prefix):
        return Completion(folder_text + common)
    return Completion(text, tuple(matches))


class PathInput(Input):
    """An `Input` for a file or folder path; `Tab` completes it (IMPORT-1).

    `Tab` adds the longest unambiguous part of the name being typed. When
    nothing can be added and several names match, the next `Tab` posts
    `Choices` for the screen to show. `Tab` therefore never moves focus
    out of this input.

    Messages:
        Choices: The names that match the text, for the screen to list.
    """

    class Choices(Message):
        """`Tab` couldn't add anything: these names all match."""

        def __init__(self, path_input: PathInput, choices: tuple[str, ...]) -> None:
            super().__init__()
            self.path_input = path_input
            self.choices = choices

        @property
        def control(self) -> PathInput:
            return self.path_input

    BINDINGS = [Binding("tab", "complete", "Complete", show=False)]

    def action_complete(self) -> None:
        completion = complete(self.value)
        if completion.text != self.value:
            self.value = completion.text
            self.cursor_position = len(self.value)
        elif completion.choices:
            self.post_message(self.Choices(self, completion.choices))


def format_choices(choices: tuple[str, ...], limit: int = 12) -> str:
    """The choices on one line for a hint, at most `limit` of them."""
    shown = "  ".join(choices[:limit])
    extra = len(choices) - limit
    return f"{shown}  … {extra} more" if extra > 0 else shown
