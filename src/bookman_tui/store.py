"""The in-memory catalog: every book from the last scan, keyed by `Book.id` (ADR-3).

M3 scope: holding, counting, ordering and replacing books. Search and the
review filter (FIND) arrive in M6, sort and grouping (BROWSE-8/9) in M7, each
stubbed on its own.
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

    def replace(self, book: Book) -> None:
        """Put `book` in place of the one with the same id, or add it if new.

        For the Book a write returns (edit, mark reviewed, re-identify, each
        import result): the catalog stays current without a rescan.
        """
        self._books[book.id] = book
        self._ordered = None
