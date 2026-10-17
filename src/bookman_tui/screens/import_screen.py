"""Adding books: path, preview, progress and summary (IMPORT, ADR-10)."""

from __future__ import annotations

from enum import Enum
from pathlib import Path

from bookman import Book, FormatConflictError, Library, MatchBasis
from rich.markup import escape
from rich.text import Text
from textual import on, work
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical, VerticalScroll
from textual.reactive import reactive
from textual.screen import Screen
from textual.widgets import (
    Button,
    Checkbox,
    ContentSwitcher,
    Footer,
    Header,
    Input,
    ProgressBar,
    RichLog,
    SelectionList,
    Static,
)
from textual.widgets.selection_list import Selection

from bookman_tui.importing import Entry, ImportJob, Mark, files_in_dot_folders, is_supported, outcome_line, survey
from bookman_tui.keys import key, keys_line, press
from bookman_tui.location import display_path, folder_text
from bookman_tui.widgets.path_input import PathInput, format_choices

SUPPORTED = "EPUB or PDF"

BASIS_WORDS = {
    MatchBasis.ISBN: "same ISBN",
    MatchBasis.TITLE_AUTHOR: "same title and author",
    MatchBasis.TITLE_ONLY: "same title only",
}


class Stage(Enum):
    """Where the import is (the IMPORT state diagram)."""

    PATH = "stage-path"
    PREVIEW = "stage-preview"
    RUNNING = "stage-running"
    SUMMARY = "stage-summary"


def plural(count: int, noun: str) -> str:
    return f"{count} {noun}{'' if count == 1 else 's'}"


def preview_counts(entries: list[Entry]) -> str:
    """IMPORT-3's header: files found, new, already in library, unsupported."""
    marks = [entry.mark for entry in entries]
    return (
        f"{plural(len(entries), 'file')} found · {marks.count(Mark.NEW)} new · "
        f"{marks.count(Mark.HELD)} already in library · {marks.count(Mark.UNSUPPORTED)} unsupported"
    )


def conflict_text(conflict: FormatConflictError) -> str:
    """One conflict, with what to do about it (IMPORT-9)."""
    existing = conflict.existing
    advice = (
        f"To use the new file instead, copy it over {escape(existing.name)} by hand, "
        f"keeping that file name, then press {key('ctrl+r')}."
    )
    if conflict.basis is MatchBasis.TITLE_ONLY:
        advice += " If it's a different book, bookman can't keep them apart yet."
    return (
        f"[b]{escape(conflict.source.name)}[/] matched [b]{escape(conflict.book.title)}[/] "
        f"({BASIS_WORDS.get(conflict.basis, conflict.basis.value)}), which already has "
        f"{escape(existing.name)}. {advice}"
    )


def failure_reason(path: Path, error: Exception) -> str:
    """Why a file failed, without the path bookman's message starts with."""
    return str(error).removeprefix(f"{path}: ")


def summary_text(job: ImportJob) -> str:
    """IMPORT-10: counts first, then the non-empty sections in order."""
    result = job.result
    lines = [job.counts_text(skip_zero=True) or "Nothing was imported."]
    if job.stopped:
        lines.append(f"Stopped at {job.done} of {job.total}. Import the same folder again to continue.")

    def section(title: str, rows: list[str]) -> None:
        if rows:
            lines.extend(["", f"[b]{title}[/]", *rows])

    section("Conflicts", [conflict_text(conflict) for conflict in result.conflicts])
    section(
        "Failed",
        [f"{escape(path.name)}: {escape(failure_reason(path, error))}" for path, error in result.failed],
    )
    section(
        "Imported",
        [
            f"{escape(path.name)} → {escape(book.title)}"
            + (" [$warning](needs review)[/]" if book.needs_review else "")
            for path, book in result.imported
        ],
    )
    section(
        "Already in library",
        [f"{escape(held.source.name)} → {escape(held.book.title)}" for held in result.unchanged],
    )
    section("Skipped", [escape(path.name) for path in result.skipped])
    return "\n".join(lines)


class PreviewList(SelectionList[str]):
    """The folder's files, new ones tickable (IMPORT-3). `Enter` starts the
    import rather than ticking, which is `Space`."""

    BINDINGS = [
        Binding("enter", "screen.start", "Import", show=False),
        Binding("a", "screen.tick_all", "Tick all", show=False),
    ]


class ImportScreen(Screen):
    """Import a file or a folder (IMPORT-1..10).

    Shows the App's `ImportJob` once one starts; the job, not this screen,
    runs the import (ADR-10).
    """

    BINDINGS = [
        Binding("escape", "back", "Back"),
        Binding("ctrl+s", "toggle_recursive", "Subfolders"),
        Binding("escape", "hold", show=False),
        Binding("space", "noop", "Tick", show=False),  # footer hint for the list's own Space
        Binding("slash", "filter", "Filter", key_display="/", show=False),
        Binding("x", "stop", "Stop", show=False),
        Binding("l", "look_up", "Look up again"),
        Binding("enter", "done", "Done"),
    ]

    stage: reactive[Stage] = reactive(Stage.PATH)

    def __init__(self) -> None:
        super().__init__()
        self.entries: list[Entry] = []
        self.ticked: set[Path] = set()
        self.folder: Path | None = None
        self.recursive = False
        self.whole_folder = True
        """Whether `iter_import` on the folder takes exactly the listed files,
        so importing everything new can hand bookman the folder (IMPORT-3)."""
        self.logged = 0
        """Job log events already written to the RichLog."""
        self.shown: set[Path] = set()
        """The files the preview filter leaves in the list."""

    def compose(self) -> ComposeResult:
        yield Header()
        with ContentSwitcher(initial=Stage.PATH.value, id="import"):
            with Vertical(id=Stage.PATH.value):
                yield Static("Import books", classes="import-heading")
                yield Static(
                    "Give a file or a folder. Books are copied into the library; "
                    "your files are never moved or changed.",
                    classes="import-intro",
                )
                yield PathInput(folder_text(Path.cwd()), placeholder="~/Downloads", id="import-path")
                yield Static("", id="import-hint")
                yield Checkbox("Include subfolders (ctrl+s)", id="import-recursive")
            with Vertical(id=Stage.PREVIEW.value):
                yield Static("", id="preview-counts", classes="import-heading")
                yield Static(
                    "Each new book is looked up online, so a large folder can take minutes.",
                    classes="import-intro",
                )
                yield Input(placeholder="Filter by file name", id="preview-filter", compact=True)
                yield PreviewList(id="preview-list")
                yield Static("", id="preview-hint")
            with Vertical(id=Stage.RUNNING.value):
                yield Static("", id="run-title", classes="import-heading")
                yield ProgressBar(id="run-progress", show_eta=True)
                yield Static("", id="run-current")
                yield Static("", id="run-counts")
                yield RichLog(id="run-log", markup=False, wrap=True)
                yield Static("", id="run-hint")
            with Vertical(id=Stage.SUMMARY.value):
                yield Static("Import finished", id="summary-title", classes="import-heading")
                with VerticalScroll(id="summary-scroll"):
                    yield Static("", id="summary-text")
                with Horizontal(id="summary-buttons"):
                    yield Button("Back to library ⏎", variant="primary", id="summary-done")
        yield Footer()

    def on_mount(self) -> None:
        self.query_one("#preview-filter").display = False
        self.query_one("#run-hint").display = False
        self.show_path_hint(self.query_one("#import-path", Input).value)
        self.app.import_signal.subscribe(self, self.show_job)
        job: ImportJob | None = self.app.import_job
        if job is not None:
            self.show_job(job)

    @property
    def library(self) -> Library:
        return self.app.library

    def watch_stage(self, stage: Stage) -> None:
        self.query_one(ContentSwitcher).current = stage.value
        focus = {
            Stage.PATH: "#import-path",
            Stage.PREVIEW: "#preview-list",
            Stage.RUNNING: "#run-log",
            Stage.SUMMARY: "#summary-scroll",
        }[stage]
        self.query_one(focus).focus()
        self.refresh_bindings()

    def check_action(self, action: str, parameters: tuple[object, ...]) -> bool | None:
        """Show each stage's keys only (ADR-7)."""
        stage = self.stage
        if action == "back":
            return stage in (Stage.PATH, Stage.PREVIEW, Stage.SUMMARY)
        if action in ("noop", "filter"):
            return stage is Stage.PREVIEW
        if action == "toggle_recursive":
            return stage is Stage.PATH
        if action == "hold":
            return stage is Stage.RUNNING
        if action == "stop":
            job = self.app.import_job
            return stage is Stage.RUNNING and job is not None and not job.stopping
        if action == "done":
            return stage is Stage.SUMMARY
        if action == "look_up":
            job = self.app.import_job
            return stage is Stage.SUMMARY and job is not None and bool(job.lookups_failed)
        return True

    # Path (IMPORT-1, IMPORT-2)

    def action_toggle_recursive(self) -> None:
        """`ctrl+s`: include subfolders or not, without leaving the path (IMPORT-1)."""
        self.query_one("#import-recursive", Checkbox).toggle()

    def path_hint(self, text: str) -> tuple[str, bool]:
        """What `Enter` will do with `text` (markup), and whether it's an error."""
        text = text.strip()
        if not text:
            return "Type a file or folder to import. " + press("Tab", "complete the path"), False
        path = Path(text).expanduser().absolute()
        if not path.exists():
            return f"Nothing at {escape(display_path(path))}.", True
        if path.is_dir():
            return f"Folder {escape(display_path(path))}. " + press("Enter", "see what's in it"), False
        if not is_supported(path):
            return f"{escape(path.name)} isn't a format bookman reads ({SUPPORTED}).", True
        return f"File {escape(path.name)}. " + press("Enter", "import it"), False

    def show_path_hint(self, text: str, message: str | None = None, *, error: bool | None = None) -> None:
        hint = self.query_one("#import-hint", Static)
        default, is_error = self.path_hint(text)
        hint.update(escape(message) if message is not None else default)
        hint.set_class(is_error if error is None else error, "error")

    @on(Input.Changed, "#import-path")
    def path_changed(self, event: Input.Changed) -> None:
        self.show_path_hint(event.value)

    def on_path_input_choices(self, event: PathInput.Choices) -> None:
        self.show_path_hint("", format_choices(event.choices), error=False)

    @on(Input.Submitted, "#import-path")
    def path_submitted(self, event: Input.Submitted) -> None:
        message, error = self.path_hint(event.value)
        if error or not event.value.strip():
            self.show_path_hint(event.value)
            return
        path = Path(event.value.strip()).expanduser().absolute()
        self.recursive = self.query_one("#import-recursive", Checkbox).value
        self.show_path_hint("", f"Reading {display_path(path)}…", error=False)
        self.read_path(path, self.recursive)

    @work(thread=True, exclusive=True, group="survey")
    def read_path(self, path: Path, recursive: bool) -> None:
        """Survey a folder, or check a single file, off the UI thread."""
        try:
            if path.is_dir():
                entries = survey(self.library, path, recursive)
                whole_folder = not (recursive and files_in_dot_folders(path))
                self.app.call_from_thread(self.show_preview, path, entries, whole_folder)
            else:
                book = self.library.find_file(path)
                self.app.call_from_thread(self.single_file, path, book)
        except OSError as error:
            message = f"Can't read {display_path(path)}: {error.strerror or error}."
            self.app.call_from_thread(self.show_path_hint, "", message, error=True)

    def single_file(self, path: Path, book: Book | None) -> None:
        """IMPORT-2: a file starts at once, unless the library has it."""
        if book is not None:
            self.show_path_hint("", f"Already in library: {book.title}. Nothing to import.", error=True)
            return
        self.app.start_import(ImportJob(files=[path]))

    # Preview (IMPORT-3)

    def show_preview(self, folder: Path, entries: list[Entry], whole_folder: bool = True) -> None:
        self.folder = folder
        self.whole_folder = whole_folder
        self.entries = entries
        self.ticked = {entry.path for entry in entries if entry.mark is Mark.NEW}
        self.query_one("#preview-counts", Static).update(preview_counts(entries))
        filter_box = self.query_one("#preview-filter", Input)
        filter_box.value = ""
        filter_box.display = False
        self.fill_list()
        self.stage = Stage.PREVIEW

    def fill_list(self) -> None:
        """Rebuild the list for the filter, keeping ticks and the cursor."""
        listing = self.query_one(PreviewList)
        cursor = listing.highlighted
        query = self.query_one("#preview-filter", Input).value.strip().casefold()
        base = self.folder or Path()
        listing.clear_options()
        self.shown = set()
        for entry in self.entries:
            name = str(entry.path.relative_to(base))
            if query and query not in name.casefold():
                continue
            self.shown.add(entry.path)
            prompt = Text(name)
            if entry.mark is not Mark.NEW:
                prompt.append(f"  {entry.mark.value}", style="dim")
            listing.add_option(
                Selection(
                    prompt,
                    str(entry.path),
                    entry.path in self.ticked,
                    disabled=entry.mark is not Mark.NEW,
                )
            )
        if listing.option_count:
            listing.highlighted = min(cursor or 0, listing.option_count - 1)
        self.show_preview_hint()

    def show_preview_hint(self) -> None:
        count = len(self.ticked)
        hidden = len(self.ticked - self.shown)
        files = plural(count, "file") + (f" ({hidden} hidden by the filter)" if hidden else "")
        text = (
            keys_line(("Enter", f"Import {files}"), ("Space", "Tick"), ("a", "Tick all"), ("/", "Filter"))
            if count
            else f"Nothing ticked. Press {key('Space')} to tick a file, or {key('a')} to tick all new files."
        )
        self.query_one("#preview-hint", Static).update(text)

    @on(SelectionList.SelectionToggled, "#preview-list")
    def toggled(self, event: SelectionList.SelectionToggled) -> None:
        path = Path(event.selection.value)
        self.ticked ^= {path}
        self.show_preview_hint()

    def action_tick_all(self) -> None:
        """`a`: tick every new file, or untick them all if they all are."""
        new = {entry.path for entry in self.entries if entry.mark is Mark.NEW}
        self.ticked = set() if new <= self.ticked else new
        self.fill_list()

    def action_filter(self) -> None:
        box = self.query_one("#preview-filter", Input)
        box.display = True
        box.focus()

    @on(Input.Changed, "#preview-filter")
    def filter_changed(self) -> None:
        self.fill_list()

    @on(Input.Submitted, "#preview-filter")
    def filter_submitted(self) -> None:
        self.query_one(PreviewList).focus()

    def action_start(self) -> None:
        """`Enter` on the preview: import the ticked files (IMPORT-3)."""
        if not self.ticked:
            return
        new = {entry.path for entry in self.entries if entry.mark is Mark.NEW}
        if self.ticked == new and self.whole_folder:
            job = ImportJob(folder=self.folder, recursive=self.recursive)
        else:
            job = ImportJob(files=sorted(self.ticked))
        self.app.start_import(job)

    # Running and summary (IMPORT-4, 6, 10)

    def show_job(self, job: ImportJob) -> None:
        """Bring the screen up to date with the job (the App's signal)."""
        if job.finished:
            self.query_one("#summary-title", Static).update(
                "Import stopped" if job.stopped else "Import finished"
            )
            self.query_one("#summary-text", Static).update(summary_text(job))
            self.stage = Stage.SUMMARY
            return
        if self.stage is not Stage.RUNNING:
            self.query_one("#run-log", RichLog).clear()
            self.query_one("#run-hint").display = False
            self.logged = 0
            self.stage = Stage.RUNNING
        title = f"Importing {job.done} of {job.total}" if job.total else "Importing…"
        if job.stopping:
            title += " · stopping after this file"
        self.query_one("#run-title", Static).update(title)
        progress = self.query_one("#run-progress", ProgressBar)
        progress.update(total=job.total or None, progress=job.done)
        current = f"Looking up {job.current.name}…" if job.current else ""
        self.query_one("#run-current", Static).update(escape(current))
        self.query_one("#run-counts", Static).update(job.counts_text())
        log = self.query_one("#run-log", RichLog)
        for event in job.log[self.logged :]:
            log.write(outcome_line(event))
        self.logged = len(job.log)
        self.refresh_bindings()

    def action_stop(self) -> None:
        """`x`: stop after the current file (IMPORT-6)."""
        job = self.app.import_job
        if job is not None and not job.finished:
            job.stopping = True
            self.show_job(job)

    def action_done(self) -> None:
        self.app.close_import()

    def action_look_up(self) -> None:
        """`l`: back to the browser, looking up again the books imported
        without Open Library (IMPORT-10, IMPORT-8)."""
        job = self.app.import_job
        books = job.lookups_failed if job is not None else []
        self.app.close_import()
        self.app.look_up(books, batch=True)

    @on(Button.Pressed, "#summary-done")
    def done_pressed(self) -> None:
        self.app.close_import()

    def action_back(self) -> None:
        """`Esc`: one step back (G-5)."""
        if self.stage is Stage.PREVIEW:
            box = self.query_one("#preview-filter", Input)
            if box.has_focus or box.value:
                box.value = ""
                box.display = False
                self.query_one(PreviewList).focus()
                return
            self.stage = Stage.PATH
        elif self.stage is Stage.SUMMARY:
            self.app.close_import()
        elif self.stage is Stage.PATH:
            self.dismiss()

    def action_hold(self) -> None:
        """`Esc` while running: the import holds the screen (IMPORT-5)."""
        job = self.app.import_job
        hint = self.query_one("#run-hint", Static)
        if job is not None and job.stopping:
            hint.update("The import stops after the current file.")
        else:
            hint.update("The import holds this screen until it ends. " + press("x", "stop it after the current file"))
        hint.display = True

    def action_noop(self) -> None:
        pass
