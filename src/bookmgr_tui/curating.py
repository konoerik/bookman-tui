"""Correcting books: what an edit sends, when a lookup could help, and how a
lookup's result is worded (EDIT, LOOKUP, ADR-11)."""

from __future__ import annotations

from collections.abc import Iterable

from bookmgr import Book, LookupOutcome, MatchBasis

IDENTIFIED = {
    MatchBasis.ISBN: "Identified by ISBN",
    MatchBasis.TITLE_AUTHOR: "Identified by title and author",
    MatchBasis.TITLE_ONLY: "Matched by title only",
}


def edit_changes(book: Book, title: str, author: str, isbn: str) -> dict[str, str | None]:
    """The fields the edit dialog changed, as `Library.edit` keyword
    arguments (EDIT-4).

    Values are stripped; an emptied author or ISBN becomes None, which
    clears it. The title is passed through even when blank, so the caller
    can refuse it inline. Empty when nothing changed (EDIT-3).
    """
    typed = {"title": title.strip(), "author": author.strip() or None, "isbn": isbn.strip() or None}
    return {field: value for field, value in typed.items() if value != getattr(book, field)}


def could_help(book: Book) -> bool:
    """Whether looking `book` up could change anything (EDIT-8): it wasn't
    matched online, or it has no cover, author or ISBN."""
    return book.identified is None or book.cover_path is None or not book.author or not book.isbn


def lookup_summary(before: Book, after: Book) -> str:
    """What a lookup changed, for its notification (LOOKUP-2): "Found a
    cover · Identified by ISBN", or why nothing did."""
    changes = []
    if after.cover_path is not None and before.cover_path is None:
        changes.append("Found a cover")
    if after.identified is not None and after.identified is not before.identified:
        changes.append(IDENTIFIED[after.identified])
    for field, label in (("author", "Author"), ("isbn", "ISBN")):
        old, new = getattr(before, field), getattr(after, field)
        if new and not old:
            changes.append(f"{label} filled in")
        elif new != old:
            changes.append(f"{label} updated")
    if changes:
        return " · ".join(changes)
    return unchanged_reason(after)


def unchanged_reason(book: Book) -> str:
    """Why a lookup left `book` as it was (LOOKUP-2)."""
    if book.lookup is LookupOutcome.FAILED:
        return "Open Library can't be reached"
    if book.lookup is LookupOutcome.NOT_ATTEMPTED:
        return "Lookups are off"
    return "No better match found"


def batch_summary(results: Iterable[tuple[Book, Book]]) -> str:
    """One notification for looking up several books (IMPORT-10's `l`):
    "Looked up 3 books · 2 updated", or why none could be."""
    pairs = list(results)
    updated = sum(lookup_summary(before, after) not in _UNCHANGED for before, after in pairs)
    noun = "book" if len(pairs) == 1 else "books"
    if not updated and pairs and all(after.lookup is LookupOutcome.FAILED for _, after in pairs):
        return "Open Library still can't be reached"
    if not updated and pairs and all(after.lookup is LookupOutcome.NOT_ATTEMPTED for _, after in pairs):
        return "Lookups are off"
    return f"Looked up {len(pairs)} {noun} · {updated} updated"


_UNCHANGED = ("Open Library can't be reached", "Lookups are off", "No better match found")
