"""Textual front end for the bookman ebook library."""

from __future__ import annotations

import argparse
from pathlib import Path


def main(argv: list[str] | None = None) -> None:
    """Run the app: `bookman-tui [--library DIR]` (START-1)."""
    parser = argparse.ArgumentParser(
        prog="bookman-tui",
        description="Browse, search, import into and curate a bookman ebook library.",
    )
    parser.add_argument(
        "--library",
        type=Path,
        metavar="DIR",
        help="open this library instead of $BOOKMAN_LIBRARY or the saved one",
    )
    args = parser.parse_args(argv)

    from bookman_tui.app import BookmanApp

    library = args.library.expanduser().absolute() if args.library else None
    BookmanApp(library=library).run()
