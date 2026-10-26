# CLAUDE.md

## Project Overview
A Textual terminal front end to the **bookmgr** library (`../bookmgr`): browse,
search, import into and curate a local ebook library (review queue, metadata
edits, re-identification). All library behaviour lives in bookmgr; this app is
presentation and interaction only.

### bookmgr dependency
- Installed from **PyPI** (`bookmgr[crypto]>=X.Y` in `pyproject.toml`;
  `uv.lock` pins the exact release). bookmgr was called `bookman` before 2.0;
  PyPI's `bookman` is an unrelated bookmarks tool — never depend on `bookman`
- To pick up a new bookmgr release: raise the lower bound if the TUI needs it,
  `uv lock --upgrade-package bookmgr`, re-check stamps (see below)
- To work against unreleased changes in the `../bookmgr` checkout, run any
  make target with `BOOKMGR=local` (`uv run --with-editable ../bookmgr …`);
  never commit a path source for bookmgr
- Import **only** from bookmgr's public API — the names in `bookmgr.__all__`
  (`from bookmgr import Library, Book, ...`). Never import `bookmgr.library`,
  `bookmgr.storage`, `bookmgr.identify` etc. directly, and never shell out to or
  wrap the `bookmgr` CLI (`bookmgr.cli`)
- Missing API, bugs or friction in bookmgr → append an entry to
  `../bookmgr/inbox/REQUESTS.md` using the format in that file. That file is the
  **only** place this project writes in `../bookmgr`; never edit bookmgr's source
- One writer per library: `Library` holds no lock, so the TUI must not run
  concurrent imports/edits against the same root
- **Version-stamp bookmgr claims.** Any statement in docs, ADRs, code comments
  or inbox entries about bookmgr's API or a limitation carries the version and
  short hash it was checked against, e.g. `[bookmgr 2.0.0 @ bf61464]`. Docs
  also state their overall baseline at the top. Stamps from before the rename
  (`[bookman 1.3.0 @ 1bdad64]`) are history: leave them until the claim is
  re-checked
- **Re-checking a baseline:** compare the stamped hash with the tag of the
  release `uv.lock` pins (`git -C ../bookmgr rev-parse --short v<version>`; `HEAD` when working with
  `BOOKMGR=local`); if they differ,
  `git -C ../bookmgr diff <stamped>..<tag> -- src/bookmgr CHANGELOG.md`
  shows what moved, then re-verify the stamped claims and update their stamps

## Tech Stack
- **Language:** Python 3.10+
- **TUI framework:** [Textual](https://textual.textualize.io)
- **Package manager:** uv (see Operating Rules)
- **Testing:** pytest + pytest-asyncio, driving the app with `App.run_test()` / `Pilot`

## Key Conventions
- App entry point is `src/bookmgr_tui/app.py` (console script `bookmgr-tui` → `bookmgr_tui:main`)
- Screens live in `src/bookmgr_tui/screens/`
- Widgets live in `src/bookmgr_tui/widgets/`
- Styles live in `src/bookmgr_tui/app.tcss` — prefer TCSS over inline styles
- Use `reactive` attributes for state; avoid direct DOM mutation outside of watchers
- Message passing over direct method calls between widgets

## Development Workflow
```bash
# Run in dev mode (hot reload + Textual devtools)
uv run textual run --dev src/bookmgr_tui/app.py

# Run normally
uv run bookmgr-tui

# Open Textual devtools console
uv run textual console

# Run tests
uv run pytest

# Run a single test
uv run pytest tests/test_app.py -v
```

## Operating Rules

### Environment
- Always `uv` with the local `.venv` — never the system Python
- Every command goes through the venv: `uv run pytest`, `uv run textual ...`
- Dependencies change only via `uv add` / `uv remove` — `pyproject.toml` is the single source of truth; never bare `pip install`

### Debugging
Work this sequence — do not improvise tooling:
1. **Reproduce** — smallest command that shows the failure (one test, or one interaction in `textual run --dev`)
2. **Read the full traceback** — before forming a hypothesis
3. **Isolate** — narrow with existing tests and `git diff`/`git log`; bisect if the regression point is unknown
4. **Instrument** — the app owns stdout, so no `print()`/`breakpoint()` in a running TUI: use `self.log()` and watch it in `textual console`; remove instrumentation once fixed
5. **Never add a dependency to debug** — existing tools only
6. **Verify** — run `uv run pytest` yourself and confirm a zero exit code; a fix isn't done until the real command passes, not your read of the output

## Behavior Rules
- `docs/FLOWS.md` is the source of truth for user-facing behaviour: change a flow there first, then the code. Tests cite the rule ID they verify (`test_import_4_...`); respect each flow's key budget
- Prefer composing existing Textual built-ins over custom implementations
- When making an architectural decision (new screen, widget pattern, state model), record it with `/log`
<!-- Add project-specific rules here. Workflow rules (context loading, commits, plan hygiene) live in .claude/claudify.md. -->
