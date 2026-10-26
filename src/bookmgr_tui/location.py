"""How the open library is named on screen (SETTINGS-1, START-5)."""

from __future__ import annotations

from pathlib import Path

from bookmgr import LibraryLocation, LibraryNotFoundReason, LibraryOrigin

ORIGIN_LABELS = {
    LibraryOrigin.EXPLICIT: "--library",
    LibraryOrigin.ENVIRONMENT: "$BOOKMGR_LIBRARY",
    LibraryOrigin.CONFIG: "config",
}


def display_path(path: Path) -> str:
    """`path` with the home folder shown as `~`."""
    try:
        return f"~/{path.relative_to(Path.home())}" if path != Path.home() else "~"
    except ValueError:
        return str(path)


def folder_text(path: Path) -> str:
    """`path` as a folder to type after: `display_path` with a trailing `/`."""
    shown = display_path(path)
    return shown if shown.endswith("/") else f"{shown}/"


def header_text(location: LibraryLocation) -> str:
    """The header subtitle: the library path and where it was named."""
    return f"{display_path(location.path)} · {ORIGIN_LABELS[location.origin]}"


def sentence(text: str) -> str:
    """`text` with its first letter uppercased and the rest left alone."""
    return text[:1].upper() + text[1:]


def not_found_reason(reason: LibraryNotFoundReason) -> str:
    """Why `configured_library` refused a library, in the TUI's words, with
    the TUI's own next step (START-5) [bookman 1.3.0 @ 1bdad64]."""
    return NOT_FOUND_REASONS[reason]


NOT_FOUND_REASONS = {
    LibraryNotFoundReason.MISSING: (
        "This folder doesn't exist. If it's on a drive that isn't "
        "connected, connect it and retry."
    ),
    LibraryNotFoundReason.NOT_A_DIRECTORY: "This is a file, not a folder.",
    LibraryNotFoundReason.NOT_A_LIBRARY: (
        "This folder holds other files and isn't a bookmgr library. "
        "A library needs a folder of its own."
    ),
}
