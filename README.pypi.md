# bookmgr-tui

A terminal front end for [bookmgr](https://pypi.org/project/bookmgr/), a
local ebook library manager. Browse, search, import into and curate your
library without leaving the terminal: work through the books bookmgr
couldn't identify, correct titles, authors and ISBNs, and look books up again
online.

![bookmgr-tui: the library browser with a book selected](https://raw.githubusercontent.com/konoerik/bookmgr-tui/main/docs/screenshot.png)

## Install

Requires Python 3.10+.

```bash
uv tool install bookmgr-tui    # or: pipx install bookmgr-tui
```

## Usage

```bash
bookmgr-tui                  # open your bookmgr library
bookmgr-tui --library DIR    # open a different one
```

Press `?` in the app for all keys.

Keys, configuration, a demo and development notes are in the
[README on GitHub](https://github.com/konoerik/bookmgr-tui#readme).
