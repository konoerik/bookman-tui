"""The in-memory catalog: every book from the last scan, keyed by `Book.id` (ADR-3).

Holds, counts, orders and replaces books, and searches them (FIND-1), and
arranges a list of them into sorted, grouped rows (BROWSE-8/9). Filters
arrive in M8.
"""

from __future__ import annotations

from collections.abc import Callable, Iterable, Iterator
from dataclasses import dataclass
from enum import Enum
from typing import TypeVar, Union

from bookman import Book, FormatKind

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


_E = TypeVar("_E", bound=Enum)


class Sort(str, Enum):
    """The orders `o` cycles through (BROWSE-8), in cycle order.

    Recently added is left out until bookman records an import date
    (`Book.added`, planned [bookman 1.2.0 @ e080149]); it joins the cycle
    then, and `o` meanwhile toggles between these two.
    """

    TITLE = "title"
    """`title_sort_key`, ties by author (missing last), then id: BROWSE-1."""
    AUTHOR = "author"
    """The author as stored, casefolded, first name first (no surname key in
    bookman yet); books with no author last; ties in title order."""

    def next(self) -> Sort:
        """The sort `o` moves to, wrapping round."""
        return _following(self)


class Grouping(str, Enum):
    """The groupings `g` cycles through (BROWSE-9), in cycle order."""

    NONE = "none"
    AUTHOR = "author"
    """One group per author as stored (exact spelling), A–Z casefolded;
    books with no author in "Unknown author", last."""
    STATUS = "status"
    """"Needs review", "Matched online", "Checked by you", in that order. A
    book goes where its BROWSE-3 status line puts it: reviewed first, then
    the review queue, else matched online."""
    FORMAT = "format"
    """One group per `FormatKind` (EPUB, PDF, MOBI, in bookman's order); a
    book with several formats is in each of their groups."""

    def next(self) -> Grouping:
        """The grouping `g` moves to, wrapping round."""
        return _following(self)


@dataclass(frozen=True)
class GroupHeader:
    """A group's header row: `── Frank Herbert (3) ──` (BROWSE-9).

    Attributes:
        label: The group's name, e.g. "Frank Herbert", "Needs review", "EPUB".
        size: How many books are listed under it, i.e. after the search.
    """

    label: str
    size: int


@dataclass(frozen=True)
class BookRow:
    """One book's row in the list.

    Attributes:
        book: The book.
        group: The label of the group it's listed under, or "" when not
            grouped. Needed because with Format grouping one book has a row
            in each of its formats' groups.
    """

    book: Book
    group: str = ""

    @property
    def key(self) -> str:
        """The table row key: `Book.id`, prefixed with the group when grouped
        (row keys must be unique, and a book can be listed twice)."""
        return f"{self.group}/{self.book.id}" if self.group else self.book.id


Row = Union[GroupHeader, BookRow]


def arrange(books: Iterable[Book], sort: Sort, grouping: Grouping) -> list[Row]:
    """The rows the book list shows: `books` sorted, and grouped with a
    header before each group (BROWSE-8/9).

    Pure: the caller passes the books a search left (FIND-1), so search
    applies within groups and a group with no matches doesn't appear.
    Groups come in the order `Grouping` documents; within a group, books
    follow `sort`. With `Grouping.NONE` there are no headers.

    Returns:
        Rows top to bottom; empty for no books.
    """
    ordered = sorted(books, key=_SORT_KEYS[sort])
    if grouping is Grouping.NONE:
        return [BookRow(book) for book in ordered]
    groups: dict[str, list[Book]] = {}
    for book in ordered:
        for label in _GROUPS_OF[grouping](book):
            groups.setdefault(label, []).append(book)
    rows: list[Row] = []
    for label in sorted(groups, key=_GROUP_ORDER[grouping]):
        rows.append(GroupHeader(label, len(groups[label])))
        rows.extend(BookRow(book, label) for book in groups[label])
    return rows


def _following(member: _E) -> _E:
    members = list(type(member))
    return members[(members.index(member) + 1) % len(members)]


def _author_order(book: Book) -> tuple[bool, str, str, str]:
    author = (book.author or "").casefold()
    return not author, author, title_sort_key(book.title), book.id


_SORT_KEYS: dict[Sort, Callable[[Book], tuple]] = {Sort.TITLE: _order, Sort.AUTHOR: _author_order}

UNKNOWN_AUTHOR = "Unknown author"
NEEDS_REVIEW, MATCHED_ONLINE, CHECKED_BY_YOU = "Needs review", "Matched online", "Checked by you"
STATUSES = (NEEDS_REVIEW, MATCHED_ONLINE, CHECKED_BY_YOU)


def status_group(book: Book) -> str:
    """The Status group `book` belongs in: where its BROWSE-3 status line
    puts it (reviewed first, then the review queue, else matched online)."""
    if book.reviewed:
        return CHECKED_BY_YOU
    if book.needs_review:
        return NEEDS_REVIEW
    return MATCHED_ONLINE


_GROUPS_OF: dict[Grouping, Callable[[Book], Iterable[str]]] = {
    Grouping.AUTHOR: lambda book: [book.author or UNKNOWN_AUTHOR],
    Grouping.STATUS: lambda book: [status_group(book)],
    Grouping.FORMAT: lambda book: dict.fromkeys(fmt.kind.name for fmt in book.formats),
}

_KINDS = [kind.name for kind in FormatKind]

_GROUP_ORDER: dict[Grouping, Callable[[str], tuple]] = {
    Grouping.AUTHOR: lambda label: (label == UNKNOWN_AUTHOR, label.casefold(), label),
    Grouping.STATUS: lambda label: (STATUSES.index(label),),
    Grouping.FORMAT: lambda label: (_KINDS.index(label) if label in _KINDS else len(_KINDS), label),
}
