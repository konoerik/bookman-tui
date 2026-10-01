"""The mock library still produces the states it was designed to show.

A failure here after a bookman upgrade means its matching behaviour moved
and the catalogue in tools/mock_library.py needs adjusting.
"""

from __future__ import annotations

from pathlib import Path

from bookman import Library, MatchBasis, NullSource, ReadIssue


def books_by_title(root: Path) -> dict:
    return {book.title: book for book in Library(root, source=NullSource()).scan()}


def test_mock_library_covers_every_browser_state(mock_root: Path) -> None:
    books = books_by_title(mock_root)
    assert len(books) == 31
    assert sum(b.needs_review for b in books.values()) == 6

    hobbit = books["The Hobbit"]
    assert hobbit.identified is MatchBasis.ISBN and hobbit.cover_path is not None
    assert hobbit.record_author == "J.R.R. Tolkien" != hobbit.author

    dune = books["Dune"]
    assert [f.kind.name for f in dune.formats] == ["EPUB", "PDF"]
    assert dune.grouped is MatchBasis.ISBN

    assert books["Frankenstein"].identified is MatchBasis.TITLE_AUTHOR
    assert books["Neuromancer"].cover_path is not None  # from the EPUB itself
    assert books["Anathem"].cover_path is None

    meditations = books["Meditations"]
    assert meditations.identified is MatchBasis.TITLE_ONLY and meditations.needs_review

    walden = books["Walden"]
    assert walden.identified is MatchBasis.TITLE_AUTHOR
    assert walden.grouped is MatchBasis.TITLE_ONLY and walden.needs_review

    assert books["The Art of War"].reviewed and not books["The Art of War"].needs_review
    recipes = books["Grandmother's Recipes"]
    assert recipes.reviewed and recipes.author == "Rosa Lindqvist" and recipes.identified is None

    assert books["Notes on a Quiet Afternoon"].identified is None
    assert "field-guide-to-moths" in books  # placeholder title → file name

    locked = books["statement-reader-locked"]
    assert locked.formats[0].read_issue is ReadIssue.PASSWORD
