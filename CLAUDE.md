# CLAUDE.md

## Project Overview
A Textual terminal front end to the **bookman** library (`../bookman`): browse,
search, import into and curate a local ebook library (review queue, metadata
edits, re-identification). All library behaviour lives in bookman; this app is
presentation and interaction only.

### bookman dependency
- Installed from **git, pinned to a release tag**
  (`bookman @ git+https://github.com/konoerik/bookman.git@vX.Y.Z` in
  `pyproject.toml`; `uv.lock` pins the commit). Not on PyPI, and PyPI's
  `bookman` is an unrelated package — never depend on a bare `bookman`
- To pick up a new bookman release: bump the tag, `uv lock`, re-check stamps
  (see below)
- To work against unreleased changes in the `../bookman` checkout, run any
  make target with `BOOKMAN=local` (`uv run --with-editable ../bookman …`);
  never commit a path source for bookman
- Import **only** from bookman's public API — the names in `bookman.__all__`
  (`from bookman import Library, Book, ...`). Never import `bookman.library`,
  `bookman.storage`, `bookman.identify` etc. directly, and never shell out to or
  wrap the `bookman` CLI (`bookman.cli`)
- Missing API, bugs or friction in bookman → append an entry to
  `../bookman/inbox/REQUESTS.md` using the format in that file. That file is the
  **only** place this project writes in `../bookman`; never edit bookman's source
- One writer per library: `Library` holds no lock, so the TUI must not run
  concurrent imports/edits against the same root
- **Version-stamp bookman claims.** Any statement in docs, ADRs, code comments
  or inbox entries about bookman's API or a limitation carries the version and
  short hash it was checked against, e.g. `[bookman 1.1.0 @ fe2c525]`. Docs
  also state their overall baseline at the top
- **Re-checking a baseline:** compare the stamped hash with the pinned tag
  (`git -C ../bookman rev-parse --short <tag>`; `HEAD` when working with
  `BOOKMAN=local`); if they differ,
  `git -C ../bookman diff <stamped>..<tag> -- src/bookman CHANGELOG.md`
  shows what moved, then re-verify the stamped claims and update their stamps

## Tech Stack
- **Language:** Python 3.10+
- **TUI framework:** [Textual](https://textual.textualize.io)
- **Package manager:** uv (see Operating Rules)
- **Testing:** pytest + pytest-asyncio, driving the app with `App.run_test()` / `Pilot`

## Key Conventions
- App entry point is `src/bookman_tui/app.py` (console script `bookman-tui` → `bookman_tui:main`)
- Screens live in `src/bookman_tui/screens/`
- Widgets live in `src/bookman_tui/widgets/`
- Styles live in `src/bookman_tui/app.tcss` — prefer TCSS over inline styles
- Use `reactive` attributes for state; avoid direct DOM mutation outside of watchers
- Message passing over direct method calls between widgets

## Development Workflow
```bash
# Run in dev mode (hot reload + Textual devtools)
uv run textual run --dev src/bookman_tui/app.py

# Run normally
uv run bookman-tui

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
