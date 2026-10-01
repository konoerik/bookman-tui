"""How the open library is named on screen (SETTINGS-1, START-5)."""

from __future__ import annotations

from pathlib import Path

from bookman import LibraryLocation, LibraryOrigin

ORIGIN_LABELS = {
    LibraryOrigin.EXPLICIT: "--library",
    LibraryOrigin.ENVIRONMENT: "$BOOKMAN_LIBRARY",
    LibraryOrigin.CONFIG: "config",
}


def display_path(path: Path) -> str:
    """`path` with the home folder shown as `~`."""
    try:
        return f"~/{path.relative_to(Path.home())}" if path != Path.home() else "~"
    except ValueError:
        return str(path)


def header_text(location: LibraryLocation) -> str:
    """The header subtitle: the library path and where it was named."""
    return f"{display_path(location.path)} · {ORIGIN_LABELS[location.origin]}"


def sentence(text: str) -> str:
    """`text` with its first letter uppercased and the rest left alone."""
    return text[:1].upper() + text[1:]


def not_found_reason(path: Path) -> str:
    """Why `configured_library` refused `path`, in the TUI's words.

    bookman gives the reason only inside its message, worded for the CLI,
    so it is re-derived here from the path (FLOWS *Open questions*,
    START-5 wording) [bookman 1.2.0 @ e080149].
    """
    if not path.exists():
        return (
            "This folder doesn't exist. If it's on a drive that isn't "
            "connected, connect it and retry."
        )
    if not path.is_dir():
        return "This is a file, not a folder."
    return (
        "This folder holds other files and isn't a bookman library. "
        "A library needs a folder of its own."
    )
