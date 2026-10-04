"""The in-memory catalog: every book from the last scan, keyed by `Book.id` (ADR-3).

Holds, counts, orders and replaces books, and searches them (FIND-1). Sort
and grouping (BROWSE-8/9) arrive in M7, filters in M8.
"""

from __future__ import annotations

from collections.abc import Iterable, Iterator

from bookman import Book

ARTICLES = ("the ", "a ", "an ")


def title_sort_key(title: str) -> str:
    """The key BROWSE-1 orders titles by.

    Case-insensitive (`casefold`), and a leading English article ("The",
    "A", "An", followed by a space) is ignored, so *The Hobbit* sorts under
    H. Only a whole leading word counts: "Anathem" and "Theory of Games"
    keep their first letters. A title that is only an article ("The") keeps
    it. Leading/trailing whitespace is ignored.

    Returns:
        A string to sort by; never shown to the user.
    """
    key = title.strip().casefold()
    for article in ARTICLES:
        if key.startswith(article):
            return key[len(article) :].lstrip()
    return key


def _digits(text: str) -> str:
    """`text` without hyphens and spaces, so ISBNs compare however they're written."""
    return text.replace("-", "").replace(" ", "")


FIELDS = ("title", "author", "ISBN")
"""The fields search looks in (FIND-1), in the order FIND-7 names them."""


def matched_fields(book: Book, query: str) -> tuple[str, ...]:
    """The `FIELDS` that `book` matches the search `query` on (FIND-1).

    A case-insensitive (`casefold`) substring of the title or author, or of
    the ISBN with hyphens and spaces ignored on both sides. Empty when the
    book doesn't match. A blank query matches nothing here; `matches`
    treats it as matching every book.
    """
    needle = query.casefold()
    if not needle.strip():
        return ()
    isbn_needle = _digits(needle)
    found = (
        needle in book.title.casefold(),
        needle in (book.author or "").casefold(),
        bool(isbn_needle) and book.isbn is not None and isbn_needle in _digits(book.isbn.casefold()),
    )
    return tuple(field for field, hit in zip(FIELDS, found) if hit)


def matches(book: Book, query: str) -> bool:
    """Whether `book` matches the search `query` (FIND-1); a blank query
    matches every book."""
    return not query.strip() or bool(matched_fields(book, query))


def match_summary(books: Iterable[Book], query: str) -> str:
    """"3 books · 3 title · 0 author · 0 ISBN" (FIND-7).

    Each field counts every book that matched on it, so the field counts
    can add up to more than the book total.
    """
    total = 0
    counts = dict.fromkeys(FIELDS, 0)
    for book in books:
        fields = matched_fields(book, query)
        total += bool(fields)
        for field in fields:
            counts[field] += 1
    noun = "book" if total == 1 else "books"
    return " · ".join([f"{total} {noun}", *(f"{count} {field}" for field, count in counts.items())])


def _order(book: Book) -> tuple[str, bool, str, str]:
    author = (book.author or "").casefold()
    return title_sort_key(book.title), not author, author, book.id


class Catalog:
    """Every book from the last `Library.scan()`, keyed by `Book.id`.

    Selection and all references to books go by `id`, never by `directory`,
    which changes when a title edit renames the folder (G-3, ADR-3).

    Raises:
        ValueError: If constructed with two books sharing an `id` (bookman
            guarantees ids are unique, so this is a bug, not user data).
    """

    def __init__(self, books: Iterable[Book] = ()) -> None:
        self._books: dict[str, Book] = {}
        for book in books:
            if book.id in self._books:
                raise ValueError(f"two books share the id {book.id}")
            self._books[book.id] = book
        self._ordered: list[Book] | None = None

    def __len__(self) -> int:
        return len(self._books)

    def __iter__(self) -> Iterator[Book]:
        """Books in BROWSE-1 order (see `ordered`)."""
        return iter(self.ordered())

    def get(self, book_id: str) -> Book | None:
        """The book with this id, or None if it isn't in the catalog."""
        return self._books.get(book_id)

    @property
    def review_count(self) -> int:
        """How many books need review (`Book.needs_review`), for BROWSE-4."""
        return sum(book.needs_review for book in self._books.values())

    def ordered(self) -> list[Book]:
        """Every book by `title_sort_key`, ties broken by author (missing
        last), then by id, so the order is the same on every run."""
        if self._ordered is None:
            self._ordered = sorted(self._books.values(), key=_order)
        return list(self._ordered)

    def search(self, query: str) -> list[Book]:
        """The books matching `query` (FIND-1), in `ordered` order."""
        return [book for book in self.ordered() if matches(book, query)]

    def replace(self, book: Book) -> None:
        """Put `book` in place of the one with the same id, or add it if new.

        For the Book a write returns (edit, mark reviewed, re-identify, each
        import result): the catalog stays current without a rescan.
        """
        self._books[book.id] = book
        self._ordered = None
