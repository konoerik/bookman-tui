"""What an import is made of, apart from the screen showing it (ADR-10).

`survey` reads a folder for the preview (IMPORT-3); an `ImportJob` runs
the chosen files and keeps the progress and the summary (IMPORT-4/6/10).
Neither touches Textual: the App runs the job in a thread worker (ADR-4)
and the import screen only displays it.
"""

from __future__ import annotations

import time
from collections.abc import Iterator
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path

from bookman import (
    AlreadyInLibrary,
    Book,
    FormatConflictError,
    ImportBatchResult,
    ImportEvent,
    Library,
    UnsupportedFormatError,
    supported_suffixes,
)


class Mark(Enum):
    """What the preview says about a file (IMPORT-3)."""

    NEW = "new"
    HELD = "already in library"
    UNSUPPORTED = "unsupported"


@dataclass(frozen=True)
class Entry:
    """One file in the preview.

    Attributes:
        path: The file.
        mark: New, already in the library, or unsupported.
        book: The book holding the file, when it's already in the library.
    """

    path: Path
    mark: Mark
    book: Book | None = None


def is_supported(path: Path) -> bool:
    """Whether bookman has a parser for `path`'s suffix [bookman 1.3.0 @ 1bdad64]."""
    return path.suffix.lower() in supported_suffixes()


def folder_files(folder: Path, recursive: bool) -> list[Path]:
    """The files `iter_import` would consider, in its order: non-hidden
    files directly in `folder` (or under it, if `recursive`), sorted
    [bookman 1.3.0 @ 1bdad64]."""
    candidates = folder.rglob("*") if recursive else folder.iterdir()
    return sorted(path for path in candidates if path.is_file() and not path.name.startswith("."))


def survey(library: Library, folder: Path, recursive: bool) -> list[Entry]:
    """Every file the import would consider, marked for the preview
    (IMPORT-3). Reads each supported file once to hash it (`find_files`),
    so run it off the UI thread."""
    files = folder_files(folder, recursive)
    supported = [path for path in files if is_supported(path)]
    held = library.find_files(supported)
    entries = []
    for path in files:
        if not is_supported(path):
            entries.append(Entry(path, Mark.UNSUPPORTED))
        elif path in held:
            entries.append(Entry(path, Mark.HELD, held[path]))
        else:
            entries.append(Entry(path, Mark.NEW))
    return entries


@dataclass
class ImportJob:
    """One import: what to import, how far it has got, and its summary.

    `folder` set means the whole folder through `iter_import`; otherwise
    `files` are imported one by one (ADR-4 amendment). The App's worker
    pulls `events()` and hands each to `record` on the UI thread.

    Attributes:
        files: The files chosen, for a subset or a single file.
        folder: The folder, when everything new in it was chosen.
        recursive: Include subfolders (with `folder`).
        total: Files in the batch, known from the first event.
        done: Files with a result so far.
        current: The file being imported, between its two events.
        result: The summary so far (`ImportBatchResult.record`).
        log: Every result event, in order (IMPORT-4's log).
        stopping: `x` was pressed; the worker stops after this file (IMPORT-6).
        stopped: The import ended because of `stopping`.
        finished: The import has ended, all done or stopped.
    """

    files: list[Path] = field(default_factory=list)
    folder: Path | None = None
    recursive: bool = False
    total: int = 0
    done: int = 0
    current: Path | None = None
    result: ImportBatchResult = field(default_factory=ImportBatchResult)
    log: list[ImportEvent] = field(default_factory=list)
    stopping: bool = False
    stopped: bool = False
    finished: bool = False
    started: float = field(default_factory=time.monotonic)

    def events(self, library: Library) -> Iterator[ImportEvent]:
        """The import's events, as `iter_import` yields them. Blocking:
        call from a thread worker."""
        if self.folder is not None:
            yield from library.iter_import(self.folder, recursive=self.recursive)
            return
        # A chosen subset: bookman imports a whole folder only, so the
        # batch loop is mirrored here (ADR-4 amendment, inbox 2026-10-04).
        total = len(self.files)
        for index, path in enumerate(self.files, start=1):
            if not is_supported(path):
                unsupported = UnsupportedFormatError(f"no parser registered for {path.suffix!r}")
                yield ImportEvent(path, index, total, unsupported)
                continue
            yield ImportEvent(path, index, total)
            outcome: Book | Exception
            try:
                outcome = library.import_file(path)
            except Exception as error:  # one bad file never stops the batch (IMPORT-7)
                outcome = error
            yield ImportEvent(path, index, total, outcome)

    def record(self, event: ImportEvent) -> None:
        """Take one event into the progress and summary. UI thread only."""
        self.total = event.total
        if event.outcome is None:
            self.current = event.path
            return
        self.current = None
        self.done = event.index
        self.result.record(event)
        self.log.append(event)

    def finish(self) -> None:
        self.current = None
        self.finished = True
        self.stopped = self.stopping and self.done < self.total

    @property
    def seconds_left(self) -> float | None:
        """Time left at the pace so far, or None before the first result."""
        if not self.done:
            return None
        elapsed = time.monotonic() - self.started
        return elapsed / self.done * (self.total - self.done)

    @property
    def counts(self) -> dict[str, int]:
        """IMPORT-4's running counts."""
        result = self.result
        return {
            "imported": len(result.imported),
            "already in library": len(result.unchanged),
            "skipped": len(result.skipped),
            "failed": len(result.failed),
            "conflicts": len(result.conflicts),
        }

    def counts_text(self, *, skip_zero: bool = False) -> str:
        """The counts on one line: "3 imported · 1 conflict · …"."""
        parts = [
            f"{count} {'conflict' if name == 'conflicts' and count == 1 else name}"
            for name, count in self.counts.items()
            if count or not skip_zero
        ]
        return " · ".join(parts)

    @property
    def first_book(self) -> Book | None:
        """The first book imported, for the browser to select (IMPORT-10)."""
        return self.result.imported[0][1] if self.result.imported else None


def outcome_line(event: ImportEvent) -> str:
    """One line of the import log for a result event (IMPORT-4)."""
    name = event.path.name
    outcome = event.outcome
    if isinstance(outcome, Book):
        review = " (needs review)" if outcome.needs_review else ""
        return f"imported  {name} → {outcome.title}{review}"
    if isinstance(outcome, AlreadyInLibrary):
        return f"already   {name} → {outcome.book.title}"
    if isinstance(outcome, UnsupportedFormatError):
        return f"skipped   {name} (unsupported)"
    if isinstance(outcome, FormatConflictError):
        return f"conflict  {name}"
    return f"failed    {name}: {str(outcome).removeprefix(f'{event.path}: ')}"
