# bookman-tui

A terminal front end for [bookman](https://github.com/konoerik/bookman), a
local ebook library manager. Browse, search, import into and curate your
library without leaving the terminal: work through the books bookman
couldn't identify, correct titles, authors and ISBNs, and look books up again
online.

Built with [Textual](https://textual.textualize.io). All library behaviour
(identifying, fetching metadata, filing) lives in bookman; this app is the
interface to it.

## Install

Requires Python 3.10+. Neither bookman-tui nor bookman is on PyPI yet;
install straight from GitHub with [uv](https://docs.astral.sh/uv/):

```bash
uv tool install git+https://github.com/konoerik/bookman-tui
```

This pulls in bookman at the release bookman-tui is pinned to.

## Usage

```bash
bookman-tui                  # open your bookman library
bookman-tui --library DIR    # open a different one
```

It opens the same library the `bookman` command uses: `--library`, then
`$BOOKMAN_LIBRARY`, then bookman's saved config. On first run, with nothing
configured, it asks where the library should go.

Main keys in the library browser (press `?` for all of them):

| Key | Action |
|---|---|
| `/` | Search; `Esc` clears it |
| `Enter` | Book details |
| `o` / `g` | Sort / group (e.g. by status, to see what needs review) |
| `i` | Import books from a file or folder |
| `e` | Edit title, author, ISBN |
| `l` | Look the book up online again |
| `v` | Mark reviewed / not reviewed |
| `F` | Open the book's folder |
| `ctrl+r` | Reload |
| `q` | Quit |

Covers use the kitty or sixel graphics protocol where the terminal supports
it (e.g. Ghostty, kitty, WezTerm, iTerm2) and fall back to block characters
elsewhere.

Sort and grouping are remembered in a `bookman-tui` folder next to bookman's
config folder (`$BOOKMAN_TUI_PREFS` names the file directly).

## Development

```bash
git clone git@github.com:konoerik/bookman-tui.git
cd bookman-tui
uv sync
make test          # uv run pytest
make dev           # run with hot reload + Textual devtools
make try-mock      # run against a generated mock library
```

The `try-*` targets (`try-mock`, `try-import`, `try-firstrun`, …; see the
`Makefile`) run the app with its own config under `.dev/sandbox`, so they
never touch your real library or settings.

### Working on bookman alongside

bookman comes from the git tag pinned in `pyproject.toml`. To run against an
unreleased bookman, clone it beside this repo and add `BOOKMAN=local` to any
make target:

```bash
git clone git@github.com:konoerik/bookman.git ../bookman
make test BOOKMAN=local                  # or BOOKMAN_DIR=path/to/bookman
```

To move to a new bookman release, change the tag in `pyproject.toml` and run
`uv lock`.

### Docs

- `docs/FLOWS.md` — what the app does, flow by flow; the spec tests cite
- `docs/ARCHITECTURE.md` — design decisions (ADRs)
- `docs/CONVENTIONS.md` — code and test conventions

## License

MIT — see [LICENSE](LICENSE).
