# bookmgr-tui

A terminal front end for [bookmgr](https://github.com/konoerik/bookmgr), a
local ebook library manager. Browse, search, import into and curate your
library without leaving the terminal: work through the books bookmgr
couldn't identify, correct titles, authors and ISBNs, and look books up again
online.

![bookmgr-tui: browsing, searching, grouping by status and fixing a book that needs review](docs/demo.gif)

Built with [Textual](https://textual.textualize.io). All library behaviour
(identifying, fetching metadata, filing) lives in bookmgr; this app is the
interface to it.

## Install

Requires Python 3.10+. Install it from PyPI with
[uv](https://docs.astral.sh/uv/):

```bash
uv tool install bookmgr-tui
```

(`pipx install bookmgr-tui` works too.)

This pulls in [bookmgr](https://pypi.org/project/bookmgr/) from PyPI.

## Usage

```bash
bookmgr-tui                  # open your bookmgr library
bookmgr-tui --library DIR    # open a different one
```

It opens the same library the `bookmgr` command uses: `--library`, then
`$BOOKMGR_LIBRARY`, then bookmgr's saved config. On first run, with nothing
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

Sort and grouping are remembered in a `bookmgr-tui` folder next to bookmgr's
config folder (`$BOOKMGR_TUI_PREFS` names the file directly).

## Development

```bash
git clone git@github.com:konoerik/bookmgr-tui.git
cd bookmgr-tui
uv sync
make test          # uv run pytest
make dev           # run with hot reload + Textual devtools
make try-mock      # run against a generated mock library
```

The `try-*` targets (`try-mock`, `try-import`, `try-firstrun`, …; see the
`Makefile`) run the app with its own config under `.dev/sandbox`, so they
never touch your real library or settings.

`make demo` re-records `docs/demo.gif` from `demo/demo.tape`, and
`make screenshot` re-renders `docs/screenshot.png` (the image on PyPI,
whose page shows `README.pypi.md`) from `demo/screenshot.tape`. Both need
[VHS](https://github.com/charmbracelet/vhs).

### Working on bookmgr alongside

bookmgr comes from PyPI, at the release `uv.lock` pins. To run against an
unreleased bookmgr, clone it beside this repo and add `BOOKMGR=local` to any
make target:

```bash
git clone git@github.com:konoerik/bookmgr.git ../bookmgr
make test BOOKMGR=local                  # or BOOKMGR_DIR=path/to/bookmgr
```

To move to a new bookmgr release, run `uv lock --upgrade-package bookmgr`.

### Docs

- `docs/FLOWS.md` — what the app does, flow by flow; the spec tests cite
- `docs/ARCHITECTURE.md` — design decisions (ADRs)
- `docs/CONVENTIONS.md` — code and test conventions

## License

MIT — see [LICENSE](LICENSE).
