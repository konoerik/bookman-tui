# Architecture

## Quick Reference
**Stack:** Python 3.10+, Textual, bookman (editable path dependency, `../bookman`)
**bookman baseline:** 1.2.0 @ `e080149` — bookman API claims below were checked against this; see CLAUDE.md for re-checking
**Entry point:** `src/bookman_tui/app.py` (`BookmanApp`); console script `bookman-tui` → `bookman_tui:main`
**Key paths:** `src/bookman_tui/screens/`, `src/bookman_tui/widgets/`, `src/bookman_tui/app.tcss`; `tools/mock_library.py` (dev only: builds a mock library through bookman's public API with a scripted `MetadataSource`, used by `make try-mock` and the test fixtures)
**Key constraints:**
- bookman through its public API only (`bookman.__all__`); never the `bookman` CLI (ADR-1)
- Nothing that blocks runs on the event loop: imports, re-identify and any other network call go to thread workers (ADR-4)
- One write operation at a time per library; bookman has no lock [bookman 1.2.0 @ e080149] (ADR-4)
- The library is opened only through `configured_library` [bookman 1.2.0 @ e080149], never `Library(root)`, which creates and marks any folder it is given
- The TUI keeps no settings bookman owns and never switches the library; sources config waits on bookman (ADR-6, ADR-8)
- User-facing behaviour is specified in `docs/FLOWS.md`; interaction conventions in ADR-7
**Patterns:** Reactive state, message passing, screen composition


## Decisions (ADRs)

### ADR-1: Consume bookman only through its public API
**Date:** 2026-09-26
**Context:** bookman is a standalone library with a small CLI; this TUI is a separate front end developed alongside it.
**Decision:** Depend on bookman as an editable path dependency (`[tool.uv.sources]` → `../bookman`) and import only names in `bookman.__all__`. Never wrap or shell out to the CLI. Missing API, bugs and friction go to `../bookman/inbox/REQUESTS.md`, the only file this project writes in `../bookman`.
**Alternatives considered:** Wrapping the CLI (fragile text parsing, loses typed errors and progress events); importing internal modules (couples the TUI to bookman internals that may change without notice).
**Consequences:** Anything the TUI needs that bookman doesn't export is an inbox request, not a workaround. Library changes show up immediately, with no reinstall.

### ADR-2: Browser-first screen map; the review queue is a filter
**Date:** 2026-09-26
**Context:** Expected use is mostly browsing, occasional import bursts (e.g. a new Humble Bundle) and a few hand fixes for hard-to-identify books.
**Decision:** The library browser is the home screen: a book table and a detail pane. "Needs review" is a filter toggle on that table, not its own screen. Import, edit and settings are pushed on top of it and return to it.
**Alternatives considered:** Separate screens for the review queue and the library (duplicates the table and detail view, and costs a context switch for what is the same list).
**Consequences:** The browser's table and filter logic are the core widgets; everything else is a modal or a short-lived screen.

### ADR-3: In-memory catalog from `scan()`, filtered client-side, keyed by `Book.id`
**Date:** 2026-09-26
**Context:** Expected size is hundreds of books, low thousands at most. `Library.search()` goes to SQLite and re-reads each match's `metadata.json`, which is too slow to run on every keystroke [bookman 1.2.0 @ e080149].
**Decision:** Load everything with `Library.scan()` at startup and after writes, hold the books in an app-level store keyed by `Book.id`, and do search-as-you-type as an in-memory substring filter over title and author. Keep selection and all book references by `id`, never by `directory`, which changes when a title edit renames the folder.
**Alternatives considered:** `Library.search()` per keystroke (disk-bound, and its results would need merging with the loaded state); lazy paging (not needed at this size).
**Consequences:** Edits done outside the TUI (the CLI, hand-edited `metadata.json`) show up only on a rescan, so there should be a manual refresh key. Revisit if libraries grow well past a few thousand.
**Amendment (2026-10-03):** search also matches the ISBN, ignoring hyphens and spaces (FIND-1). The review filter was split out of search and is being redesigned (FLOWS.md *Open questions*).

### ADR-4: Blocking bookman calls run in thread workers under a single-writer guard
**Date:** 2026-09-26
**Context:** `import_file`, `iter_import` and `reidentify` do network lookups and file I/O that block. bookman assumes one writer per library and holds no lock [bookman 1.2.0 @ e080149].
**Decision:** Run these in `@work(thread=True, exclusive=True)` workers and send results back with `post_message` or `call_from_thread`. The App holds a single "write in progress" state. While it's set, write actions (import, edit, mark reviewed, re-identify) are disabled and the UI says why. Imports consume `iter_import` so each file's start and result drive the progress display, and the summary is rebuilt with `ImportBatchResult.record`.
**Alternatives considered:** Async wrappers (bookman is sync, so a thread would be needed anyway); `import_directory` (no progress until the whole batch is done).
**Consequences:** Every write path goes through the guard. Cancelling an import stops pulling events; files already imported stay imported, as bookman documents.

### ADR-5: Covers rendered with `textual-image`
**Date:** 2026-09-26
**Context:** Covers are wanted in the detail pane. Heavier dependencies are acceptable in a front end, but the package should stay a reasonable size.
**Decision:** Use `textual-image`, which draws with the kitty or sixel graphics protocols where the terminal supports them and falls back to half-block characters. It adds Pillow; rich already comes with Textual. Add it when the cover widget is built.
**Alternatives considered:** `rich-pixels` (half-block only, no terminal graphics protocols); writing graphics-protocol output by hand (reinventing a maintained library).
**Consequences:** Pillow becomes a runtime dependency. Cover rendering must degrade quietly when `cover_path` is None or the image fails to load.

### ADR-6: Settings owns only what bookman persists; sources config waits on bookman
**Date:** 2026-09-26
**Status:** Library-location part superseded by ADR-8; the sources part stands.
**Amendment (2026-09-27):** bookman 1.2.0 answered the request with `Config.offline` and `configured_library()`, which builds the `Library` with the source the config chooses (bookman ADR-38), and deferred the source registry until it has a second source [bookman 1.2.0 @ e080149]. The TUI therefore never picks a source itself; the only source setting today is online/offline, and whether the TUI exposes it is an open question in FLOWS.md.
**Context:** More metadata sources may be added beyond Open Library, and the TUI should be able to configure them. Today bookman's `Config` stores only the library path, and a source is chosen solely by passing one `MetadataSource` to `Library(...)` [bookman 1.1.0 @ fe2c525].
**Decision:** The Settings screen ships with the library location (shown with where it came from via `resolve_library`, changed with `save_config`) and any TUI-only display preferences. A Sources section is added once bookman exposes a way to list and configure sources. The request was filed as "configurable metadata sources" in bookman's inbox on 2026-09-26.
**Alternatives considered:** A TUI-side sources config (the CLI and TUI would build differently configured libraries, which defeats bookman's single shared config).
**Consequences:** Imports use bookman's default source until then. The Settings screen is built in sections so Sources can slot in.

### ADR-7: Interaction conventions and built-in widget choices
**Date:** 2026-09-27
**Context:** With the flows reviewed (docs/FLOWS.md), the app needs one consistent feel for keys, mouse, dialogs and feedback before screens are built. CLAUDE.md prefers composing Textual built-ins over custom widgets; Textual is 8.2.8.
**Decision:**
- **Keys:** single-letter actions on the browser (`/ n i e v l o g f c`, `j`/`k` beside the arrows); in dialogs and inputs, where letters type, only `Enter`/`Esc`/`Tab` and `ctrl+` keys. No multi-key sequences (`gg`, `dd`). `Esc` always means back/close; stopping an import is `x`.
- **Discoverability:** `Footer` shows only the everyday bindings (the rest `show=False`); `?` opens Textual's built-in help panel (G-6); every action is also registered in the `ctrl+p` command palette.
- **Mouse:** keyboard first; mouse works wherever Textual provides it (rows, buttons, checkboxes, scroll). No mouse-only features.
- **Dialogs:** `ModalScreen` with real `Button`s labelled with their key (`Save ⏎`, `Cancel esc`), the default action in the primary variant. Confirmations only for what can't be undone (today: creating the library folder).
- **Widgets:** `DataTable` (row cursor) for the book list, with group headers (BROWSE-9) as rows the cursor skips; `Static` blocks plus the cover widget (ADR-5) for the detail pane; `SelectionList` for the import preview; `ProgressBar` (built-in ETA) for import progress; `RichLog` for the import log; `notify()` toasts by severity for messages (G-4); `Header` with the library path as subtitle (SETTINGS-1).
- **Path input:** `Input` with our own shell-style `Tab` completion (the one custom widget, `widgets/path_input.py`), plus `ctrl+o` to pick with a `DirectoryTree` instead.
- **Theme:** Textual's default dark theme, switchable from the command palette and remembered with the other TUI-only preferences (sort, grouping: BROWSE-10).
**Alternatives considered:** Vim-style chords (powerful but undiscoverable for an app used in bursts); `OptionList` for the book list (native separators for group headers, but no columns); a `DirectoryTree`-only path picker (slower than typing for terminal users); confirm dialogs on every write (friction with nothing destructive to guard); following the terminal's palette with `textual-ansi` by default (kept available via the palette instead).
**Consequences:** Group-header skipping in `DataTable` and `Tab` path completion are the custom code to write and test. Taking `Tab` in the path field means focus moves with `shift+tab`/arrows there. The TUI needs a small store of its own display preferences (theme, sort, grouping), separate from bookman's config (ADR-6).

### ADR-8: The TUI never switches or changes the library; its path lives in the header
**Date:** 2026-09-27
**Context:** ADR-6 put "change library" on the Settings screen. Reviewing SETTINGS showed it mixes two intents ("look at another library" vs "change my default for bookman too"), and one read-only line doesn't justify a screen.
**Decision:** The open library comes only from `--library`, `$BOOKMAN_LIBRARY` or bookman's config (START-1), plus first-run Setup. The header shows its path and origin on every screen (SETTINGS-1). There is no Settings screen or `s` key until metadata sources exist (ADR-6). Switching libraries, if built, is a first-class feature with its own flow (FLOWS *Not yet*).
**Alternatives considered:** Switch-and-save in Settings with an override warning (the ADR-6 design); switch with an "also make default" checkbox.
**Consequences:** Supersedes ADR-6's library-location part. `screens/settings.py` isn't built yet. The origin comes from `locate_library()` [bookman 1.2.0 @ e080149], so the header shows it from the start.


## Detail

### App structure
```
src/bookman_tui/
├── __init__.py       # main(): parse args (--library), run BookmanApp
├── app.py            # BookmanApp: owns Library, catalog store, write guard
├── app.tcss          # Global styles
├── store.py          # In-memory catalog keyed by Book.id; filtering (ADR-3)
├── screens/
│   ├── browser.py    # Home: book table + detail pane, search
│   ├── import_.py    # Path entry, preview, live progress (can run in background), summary
│   ├── edit.py       # Modal: title / author / ISBN edit
│   ├── details.py    # Book details as a screen on narrow terminals (BROWSE-7)
│   ├── settings.py   # Not built until metadata sources exist (ADR-6, ADR-8)
│   ├── setup.py      # First run: no library configured
│   └── start_problem.py # START-4/5: bad config or a library that can't be opened
└── widgets/
    ├── book_table.py
    ├── book_detail.py
    ├── cover.py      # textual-image wrapper (ADR-5)
    └── path_input.py # Input with filesystem tab-completion
```

### State model
- **App-level:** the `Library` instance (built by `configured_library(--library)`) and its `LibraryLocation` (`locate_library`, for the header), the catalog store (all `Book`s by `id`), the current search text (filters are being redesigned, see FLOWS.md *Open questions*), and the write-in-progress flag. Filter changes and the write flag are `reactive`; watchers push updates to the screens.
- **Store updates:** after any write, the returned `Book` replaces the entry with the same `id` (edit, mark reviewed, re-identify, and each import result). A full `scan()` happens at startup and on manual refresh.
- **Screens and widgets:** keep only view state (selected `id`, scroll position). They request changes by posting messages to the App and never call `Library` directly.
- **Errors:** anything raised as `BookmanError` is shown to the user, e.g. an invalid ISBN from `edit` (`CatalogError`). At startup `LibraryNotConfiguredError` routes to the setup screen, and `ConfigError` or `LibraryNotFoundError` to the start-problem screen (START-4, START-5). Anything else is a bug and propagates.

### Screen map
What each screen shows and which keys it takes is specified in `docs/FLOWS.md` (the source of truth; not repeated here). Structurally:
- **Setup** (START/SETUP): shown instead of Browser when no library resolves.
- **Start problem** (START-4/5): shown instead of Browser when the config is invalid or the library can't be opened; routes to retry, Setup or quit.
- **Browser** (home; BROWSE/FIND): table + detail pane; the header carries the library path (SETTINGS-1).
- **Details** (pushed): the detail pane as its own screen on narrow terminals (BROWSE-7).
- **Import** (pushed; IMPORT): path → preview → running → summary. While running it can be dismissed to the Browser and reopened; the worker belongs to the App, not the screen (ADR-4).
- **Edit** (modal; EDIT).
- **Settings:** not built until metadata sources exist (ADR-8).
