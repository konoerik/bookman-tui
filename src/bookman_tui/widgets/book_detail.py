"""The detail pane: everything about the selected book (BROWSE-3).

M4 scope: the text, with a fixed-size slot where the cover goes; M5 draws the
cover into it (ADR-5).
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from bookman import Book, MatchBasis
from textual.app import ComposeResult
from textual.containers import VerticalScroll
from textual.markup import escape
from textual.reactive import reactive
from textual.widget import Widget
from textual.widgets import Static

from bookman_tui.location import sentence
from bookman_tui.widgets.cover import Cover

MATCHED = {
    MatchBasis.ISBN: "matched online by ISBN",
    MatchBasis.TITLE_AUTHOR: "matched online by title and author",
    MatchBasis.TITLE_ONLY: "matched online by title only",
}
UNREADABLE = "couldn't read inside the file"


@dataclass(frozen=True)
class Trust:
    """The pane's answer to "can I trust these details?" (BROWSE-3).

    Attributes:
        mark: "✓" or "?".
        headline: The status in a few words.
        reasons: Why it needs review, most important first; empty unless the
            headline is "Needs review".
        detail: For a reviewed book, how bookman had matched it, shown muted
            under the headline; otherwise None.
    """

    mark: str
    headline: str
    reasons: tuple[str, ...] = ()
    detail: str | None = None


def trust(book: Book) -> Trust:
    """The status line, first match wins (BROWSE-3):

    1. `reviewed` → ✓ "Checked by you", with `detail` saying how bookman
       had matched it: "matched online by ISBN", "matched online by title
       and author", "matched online by title only", "not found online", or
       "couldn't read inside the file" (every format has a `read_issue`).
    2. `needs_review` → ? "Needs review", with every reason that applies,
       in this order:
       - `identified is None`, and every format has a `read_issue`:
         "couldn't read inside the file, so it wasn't looked up online"
       - otherwise `identified is None`: "not found online"
       - `identified is TITLE_ONLY`: "matched online by title only"
       - `grouped is TITLE_ONLY`: "formats grouped by title only"
    3. `identified is ISBN` → ✓ "Matched online by ISBN".
    4. `identified is TITLE_AUTHOR` → ✓ "Matched online by title and author".

    "Not found online" also covers a lookup that failed (offline): bookman
    can't tell them apart yet (FLOWS *Open questions*, LOOKUP-2).

    Raises:
        ValueError: For a combination bookman's `needs_review` rule rules
            out (not reviewed, not in the queue, and not identified by ISBN
            or title and author); that would be a bug, not user data.
    """
    unreadable = bool(book.formats) and all(fmt.read_issue for fmt in book.formats)
    if book.reviewed:
        if book.identified is not None:
            detail = MATCHED[book.identified]
        else:
            detail = UNREADABLE if unreadable else "not found online"
        return Trust("✓", "Checked by you", detail=detail)
    if book.needs_review:
        reasons = []
        if book.identified is None:
            reasons.append(f"{UNREADABLE}, so it wasn't looked up online" if unreadable else "not found online")
        elif book.identified is MatchBasis.TITLE_ONLY:
            reasons.append(MATCHED[MatchBasis.TITLE_ONLY])
        if book.grouped is MatchBasis.TITLE_ONLY:
            reasons.append("formats grouped by title only")
        return Trust("?", "Needs review", tuple(reasons))
    if book.identified in (MatchBasis.ISBN, MatchBasis.TITLE_AUTHOR):
        return Trust("✓", sentence(MATCHED[book.identified]))
    raise ValueError(f"book {book.id} is neither reviewed, queued nor matched online")


def author_note(book: Book) -> str | None:
    """"Open Library lists the author as …" when the record spelled the
    author differently (`record_author`), else None (BROWSE-3).

    Different means different after ignoring case, spacing and the
    punctuation between initials: "J. R. R. Tolkien" and "J.R.R. Tolkien"
    are the same spelling, so no note. A book with no `author` but a
    `record_author` gets no note either: bookman already filled the author
    from the record (IDENT-6).
    """
    if not book.author or not book.record_author:
        return None
    if _spelling(book.author) == _spelling(book.record_author):
        return None
    return f"Open Library lists the author as {book.record_author}"


def files_text(book: Book) -> str:
    """One line per format, `EPUB  Dune.epub`, with bookman's advice in amber
    under a format it couldn't read (BROWSE-3); markup."""
    lines = []
    for fmt in book.formats:
        lines.append(f"{fmt.kind.name}  {escape(fmt.path.name)}")
        if fmt.read_issue:
            lines.append(f"[$warning]{escape(sentence(fmt.read_issue.advice))}.[/]")
    return "\n".join(lines)


def trust_text(book: Book) -> str:
    """The trust line (`trust`) as markup: the mark and headline in green or
    amber, then each reason, then the muted detail."""
    status = trust(book)
    colour = "$success" if status.mark == "✓" else "$warning"
    lines = [f"[bold {colour}]{status.mark} {status.headline}[/]"]
    lines += [f"· {reason}" for reason in status.reasons]
    if status.detail:
        lines.append(f"[dim]{status.detail}[/]")
    return "\n".join(lines)


def _spelling(name: str) -> str:
    return " ".join(re.sub(r"[.\s]+", " ", name.casefold()).split())


class BookDetail(Widget):
    """The selected book, top to bottom:

    - cover slot: fixed size (about 20×14 cells); "No cover" when
      `cover_path` is None. M5 draws the image here.
    - title (bold, wraps), author, `ISBN 979…` (each line omitted when blank)
    - the trust line (`trust`): mark and headline coloured green for ✓ and
      amber for ?, then each reason on its own line
    - `author_note`, muted, when there is one
    - "Files": one line per format, `EPUB  Dune.epub`; a format with a
      `read_issue` gets its advice under it, sentence-cased, in amber
      (until bookman's short `ReadIssue.summary` lands)

    While `busy`, "Looking up…" shows under the trust line (LOOKUP-1).

    Shows nothing when `book` is None (empty library or no selection).
    """

    book: reactive[Book | None] = reactive(None)
    busy: reactive[bool] = reactive(False)

    def compose(self) -> ComposeResult:
        with VerticalScroll():
            yield Cover(id="detail-cover")
            yield Static("", id="detail-title")
            yield Static("", id="detail-author")
            yield Static("", id="detail-isbn")
            yield Static("", id="detail-trust")
            yield Static("Looking up…", id="detail-busy")
            yield Static("", id="detail-note")
            yield Static("Files", id="detail-files-heading")
            yield Static("", id="detail-files")

    def watch_book(self, book: Book | None) -> None:
        self.query_one(VerticalScroll).display = book is not None
        if book is None:
            return
        self.query_one(Cover).path = book.cover_path
        self._set("#detail-title", book.title)
        self._set("#detail-author", book.author)
        self._set("#detail-isbn", f"ISBN {book.isbn}" if book.isbn else None)
        self._set("#detail-trust", trust_text(book), markup=True)
        self._set("#detail-note", author_note(book))
        self._set("#detail-files", files_text(book), markup=True)

    def watch_busy(self, busy: bool) -> None:
        self.query_one("#detail-busy").display = busy

    def _set(self, selector: str, text: str | None, *, markup: bool = False) -> None:
        static = self.query_one(selector, Static)
        static.display = bool(text)
        if text:
            static.update(text if markup else escape(text))

