# Plan

## Active
<!-- Current sprint items. Keep this short — 5-10 items max.
     If it grows beyond that, move lower-priority items to Backlog. -->

Skeleton first, in small milestones; each ends with a visual review by the
user before the next starts.

- **M8 Edit and lookup** — design first (FLOWS.md Open questions): edit,
  look up and mark reviewed as one path for any book, judged against the
  hardest case, an imported book with little or no metadata; then build
  EDIT-1..6, LOOKUP-1..3 and REVIEW-1. Replaces M8 Filters, dropped
  2026-10-03 (Status grouping covers the review queue; ADR-2 amended)
- **M9 Reveal and copy** — BROWSE-11..13
- **M10 UI polish** — from the M3 review: the title column takes too much
  width next to author and formats (rebalance, e.g. cap the title or share
  spare width); the plain table look (stripes, header, colours) once the
  browser is complete; the narrow details screen (BROWSE-7) leaves the right
  side empty with everything left-aligned (centre it, or use the width),
  and it shows a scrollbar on short terminals


## Backlog
<!-- Accepted but not yet active. Load this section only when planning or prioritizing. -->

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
