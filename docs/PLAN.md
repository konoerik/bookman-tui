# Plan

## Active
<!-- Current sprint items. Keep this short — 5-10 items max.
     If it grows beyond that, move lower-priority items to Backlog. -->

Skeleton first, in small milestones; each ends with a visual review by the
user before the next starts.

**M13 First push to GitHub** (`git@github.com:konoerik/bookman-tui.git`,
empty). Decided 2026-10-17: depend on bookman by git URL pinned to a tag
(PyPI's `bookman` is an unrelated bookmarks tool; rename filed to inbox);
keep all claudify and docs files tracked.
- [x] Dependency: `bookman @ git+https://github.com/konoerik/bookman.git@v1.3.0`,
  relocked. A path source can't stay (the lock keeps `../bookman`, clones
  fail), so `make … BOOKMAN=local` overlays the checkout
- [x] Verify a clean copy with no `../bookman`: `uv sync`, `uv run pytest`
  (209 passed), `uv tool install .`; recheck `uv tool install git+…` after push
- [x] README: what it is, install, dev setup beside bookman, running,
  `make try-*`
- [x] MIT LICENSE; `pyproject.toml` license and project URLs
- [x] CLAUDE.md: describe the new dependency setup
- [x] bookman `crypto` extra on (encrypted PDFs read, not filed by name)
- [x] Demo GIF: `demo/demo.tape` → `docs/demo.gif` via `make demo` (VHS),
  shown in the README; approved 2026-10-17
- [x] Add `origin`, push `main`, tag `v1.0.0` (version 1.0.0; small feature updates bump minor)


## Backlog
<!-- Accepted but not yet active. Load this section only when planning or prioritizing. -->

- **bookman as a release wheel?** (low) — from M13 (2026-10-17): bookman's
  README installs the wheel from its GitHub Release; we use the git URL +
  tag (same release, but cloned and built on install). Decide together
  with whether either project goes to PyPI, so the dependency changes once
- **CI** (low) — from M13 (2026-10-17): GitHub Actions running `uv sync`
  + `uv run pytest` on Python 3.10 and latest; also catches bookman
  git-dependency breakage
- **Import screen revisit** (low) — from M12 (2026-10-16): fine for now,
  but on short terminals (about 20 rows) the "Include subfolders" checkbox
  drops below the panel, and a merged path + live preview screen was
  floated (doable, with debounce, cancellable reads and cached hashes)
- **Key bindings review** (low) — from the M7 review: in the book list `DataTable` jumps to top/bottom only with `ctrl+home`/`ctrl+end`, while plain `home`/`end` scroll sideways (Textual 8.2.8). Fine for now; revisit with the other browser keys (e.g. bind `home`/`end`, or `G`-style jumps without chords per ADR-7)


## Done
<!-- Completed items land here temporarily.
     The stop hook archives these to .claude/archive/YYYY-MM.md and clears this section. -->
- **M1 App shell + START routing** — `--library`, `configured_library`,
  header with path and origin (SETTINGS-1), start-problem screen (START-4/5),
  placeholder Setup (START-3), empty browser (BROWSE-6) with the count
  footer (BROWSE-4), `q`/`?` (G-5/G-6). *Done, reviewed 2026-09-27*
- **M2 Setup screen** — SETUP-1..6 with a plain path `Input` (tab
  completion comes with IMPORT-1). *Done, reviewed 2026-09-27*
- **M3 Mock library + book table** — dev mock-library generator
  (approved 2026-09-27; skip encrypted PDFs if awkward), store (stub first), table (BROWSE-1/2/5), footer counts.
  *Done, reviewed 2026-10-01 (reload toast added from review)*
- **M4 Detail pane, text** — BROWSE-3 without the cover, narrow layout (BROWSE-7). *Done, reviewed 2026-10-01; bordered panels added from review*
- **M5 Cover** — `textual-image` (ADR-5). 28×21 slot chosen; generated no-cover placeholder. *Done, reviewed 2026-10-03 in Ghostty (graphics protocol works). Panel borders made static (accent 65%), one shared background*
- **M6 Search** — FIND-1, 2, 5, 6, 7 (the review filter is split out, later dropped). *Done, reviewed 2026-10-03; match counts (FIND-7) added from review*
- **M7 Sort, group, prefs** — BROWSE-8/9/10. *Done, reviewed 2026-10-03.* `o` toggles Title/Author until bookman has `Book.added`; prefs file per ADR-9. Hiding the author column when grouped by author was considered and declined
- **M7.5 Setup polish** — path pre-filled with a suggested folder
  (`Books`, `Ebooks`, `Library`, `MyBooks`: the first `Enter` would accept)
  and the full path in every hint (SETUP-1); `Esc` cancels, returns to the
  start problem, or on first run quits on a second press (SETUP-7);
  confirmations read "Press Enter/Esc again to …". *Done, reviewed
  2026-10-04*
- **M8 Import** — IMPORT-1/2/3/4/6/7/9/10 (without `l`): `PathInput` with `Tab` completion (also in Setup), path pre-filled with the current folder; preview with ticks, `Space`/`a`/`/` and already-in-library marks from `find_files` (the filter is a view: hidden ticked files are counted in the hint); progress, `x` stops; summary with a `Back to library ⏎` button, then the browser on the first imported book. App-owned `ImportJob` (ADR-10); a subset loops `import_file` (ADR-4 amendment). `make try-import`. *Done, reviewed 2026-10-05*
- **M9 Import in the foreground** — background import deferred
  2026-10-05 (ADR-10 amendment, FLOWS.md *Not yet*). `Esc` while running
  hints that `x` stops (IMPORT-5); one notice when lookups fail (IMPORT-8,
  `Book.lookup`); the import worker leaves the shared `exclusive` write
  group (ADR-10). *Done, reviewed 2026-10-06 (`Esc`/`x` mid-import; IMPORT-8
  with Wi-Fi off)*
- **M10 Edit and lookup** — designed 2026-10-12 (FLOWS.md EDIT, REVIEW,
  LOOKUP, REMOVE): an edit dialog with the book's context and a sticky
  "Look up after saving" checkbox, chosen over editing in the pane or a
  book screen (throwaway mockups). Build EDIT-1..8, LOOKUP-1..3,
  REVIEW-1/2 and the summary's `l` (IMPORT-10), all under one write guard
  (G-2). REMOVE-1..4 waits for bookman's API (inbox 2026-10-06).
  Replaces M8 Filters, dropped 2026-10-03 (Status grouping covers the
  review queue; ADR-2 amended). *Done, approved 2026-10-12 (REMOVE
  excepted, waits for bookman)*
- **M11 Open folder** — BROWSE-11, 13: `F` opens the selected book's
  folder in the file manager, also from the narrow details screen and
  while a change runs. Was "Reveal and copy": copy path (BROWSE-12) moved
  to *Not yet* 2026-10-13 with a details toolbar and a richer details
  screen to explore. *Done, approved 2026-10-14*
- **M12 UI polish** — column widths share about 2:1, formats never cut
  (BROWSE-1/7); `ctrl+s` "Include subfolders" with dot-folders left out
  (IMPORT-1/3; a preview toggle was tried and dropped); the cover shrinks
  or goes on short views and sits beside the details from 60 columns
  (BROWSE-3/7); hint voice "Press `x` to …" with footer-drawn keys (G-7);
  table look kept as it is. *Done, approved 2026-10-16*
