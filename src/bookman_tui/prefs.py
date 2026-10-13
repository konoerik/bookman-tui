"""The TUI's own display preferences, kept between sessions (BROWSE-10, ADR-7).

Separate from bookman's config, which holds only what bookman owns (ADR-6):
this file is the TUI's and bookman never reads it.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import TypeVar

from bookman import config_path

from bookman_tui.store import Grouping, Sort

_E = TypeVar("_E", Sort, Grouping)

ENV_PREFS = "BOOKMAN_TUI_PREFS"
"""Names the prefs file directly, like bookman's `$BOOKMAN_CONFIG`; tests and
the `make try-*` sandboxes use it so they never touch the real one."""


@dataclass(frozen=True)
class Prefs:
    """What the browser remembers. Theme joins later (ADR-7).

    Attributes:
        sort: The book list's order (BROWSE-8).
        grouping: The book list's grouping (BROWSE-9).
        lookup_after_edit: "Look up after saving" in the edit dialog
            (EDIT-7, ADR-11).
    """

    sort: Sort = Sort.TITLE
    grouping: Grouping = Grouping.NONE
    lookup_after_edit: bool = True


def prefs_path() -> Path:
    """Where the prefs file lives: `$BOOKMAN_TUI_PREFS` if set, else
    `prefs.json` in a `bookman-tui` folder beside bookman's config folder
    (same platform rules as `bookman.config_path`, its own folder). With
    `$BOOKMAN_CONFIG` set, that is beside the folder it names.

    Returns:
        The path; the file may not exist yet.
    """
    override = os.environ.get(ENV_PREFS)
    if override:
        return Path(override).expanduser()
    return config_path().parent.parent / "bookman-tui" / "prefs.json"


def load_prefs(path: Path | None = None) -> Prefs:
    """The saved prefs, or the defaults for anything missing or unreadable.

    Display prefs aren't worth an error screen: a missing file, bad JSON or
    an unknown value (e.g. a sort a later version added) falls back to the
    default for that field, silently.
    """
    try:
        saved = json.loads((path or prefs_path()).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return Prefs()
    if not isinstance(saved, dict):
        return Prefs()
    return Prefs(
        sort=_member(Sort, saved.get("sort"), Prefs.sort),
        grouping=_member(Grouping, saved.get("grouping"), Prefs.grouping),
        lookup_after_edit=_flag(saved.get("lookup_after_edit"), Prefs.lookup_after_edit),
    )


def save_prefs(prefs: Prefs, path: Path | None = None) -> None:
    """Write `prefs`, creating the folder if needed.

    Raises:
        OSError: If the file can't be written. The caller logs it and
            carries on: the choice still applies for this session.
    """
    target = path or prefs_path()
    target.parent.mkdir(parents=True, exist_ok=True)
    data = {
        "sort": prefs.sort.value,
        "grouping": prefs.grouping.value,
        "lookup_after_edit": prefs.lookup_after_edit,
    }
    target.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")


def _member(enum: type[_E], value: object, default: _E) -> _E:
    try:
        return enum(value)
    except ValueError:
        return default


def _flag(value: object, default: bool) -> bool:
    return value if isinstance(value, bool) else default
