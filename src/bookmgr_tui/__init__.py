"""Textual front end for the bookmgr ebook library."""

from __future__ import annotations

import argparse
from pathlib import Path


def main(argv: list[str] | None = None) -> None:
    """Run the app: `bookmgr-tui [--library DIR]` (START-1)."""
    parser = argparse.ArgumentParser(
        prog="bookmgr-tui",
        description="Browse, search, import into and curate a bookmgr ebook library.",
    )
    parser.add_argument(
        "--library",
        type=Path,
        metavar="DIR",
        help="open this library instead of $BOOKMGR_LIBRARY or the saved one",
    )
    args = parser.parse_args(argv)

    from bookmgr_tui.app import BookmgrApp

    library = args.library.expanduser().absolute() if args.library else None
    BookmgrApp(library=library).run()
