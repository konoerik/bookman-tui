# Mirrors CLAUDE.md ## Development Workflow.
# The try-* targets run the app with its own bookman config in .dev/sandbox,
# so they never touch your real library or config.
#
# bookman comes from the git tag pinned in pyproject.toml. BOOKMAN=local
# runs any target against the editable checkout at BOOKMAN_DIR instead,
# e.g. `make test BOOKMAN=local`.

BOOKMAN ?= pinned
BOOKMAN_DIR ?= ../bookman
ifeq ($(BOOKMAN),local)
UV_RUN := uv run --with-editable $(abspath $(BOOKMAN_DIR))
else
UV_RUN := uv run
endif

SANDBOX := .dev/sandbox
MOCK := .dev/mock-library
BIG := .dev/mock-big
SANDBOX_ENV := BOOKMAN_CONFIG=$(CURDIR)/$(SANDBOX)/config.json BOOKMAN_TUI_PREFS=$(CURDIR)/$(SANDBOX)/prefs.json BOOKMAN_LIBRARY=

.PHONY: test run dev console mock try-mock try-big try-real try-firstrun try-empty try-import try-missing try-notlibrary try-badconfig clean-sandbox

test:
	$(UV_RUN) pytest

run:
	$(UV_RUN) bookman-tui

dev:
	$(UV_RUN) textual run --dev src/bookman_tui/app.py

console:
	$(UV_RUN) textual console

# The mock library (tools/mock_library.py): every state the browser shows.
# Rebuilt when the generator changes; `make mock` forces a rebuild.
$(MOCK): tools/mock_library.py
	$(UV_RUN) python tools/mock_library.py $(MOCK) --force

mock:
	$(UV_RUN) python tools/mock_library.py $(MOCK) --force

try-mock: $(MOCK) clean-sandbox
	env $(SANDBOX_ENV) $(UV_RUN) bookman-tui --library $(MOCK)

# The mock plus 2000 synthetic books, for speed. Slow to build (minutes).
$(BIG): tools/mock_library.py
	$(UV_RUN) python tools/mock_library.py $(BIG) --force --count 2000

try-big: $(BIG) clean-sandbox
	env $(SANDBOX_ENV) $(UV_RUN) bookman-tui --library $(BIG)

# A real library: make try-real LIB=path/to/a/copy (use a copy once the TUI can edit)
try-real: clean-sandbox
	@test -n "$(LIB)" || (echo "usage: make try-real LIB=path/to/library" && exit 1)
	env $(SANDBOX_ENV) $(UV_RUN) bookman-tui --library $(LIB)

# START-3 / SETUP: nothing configured. Try typing .dev/sandbox/new (created),
# .dev/sandbox/downloads (refused), .dev/sandbox/existing-library (opened),
# .dev/sandbox/empty (used)
try-firstrun: clean-sandbox
	mkdir -p $(SANDBOX)/downloads $(SANDBOX)/empty && touch $(SANDBOX)/downloads/book.epub
	$(UV_RUN) python -c "from pathlib import Path; from bookman import Library, NullSource; Library(Path('$(SANDBOX)/existing-library'), source=NullSource())"
	env $(SANDBOX_ENV) $(UV_RUN) bookman-tui

# START-2 / BROWSE-6: an empty library
try-empty: clean-sandbox
	mkdir -p $(SANDBOX)/empty-library
	env $(SANDBOX_ENV) $(UV_RUN) bookman-tui --library $(SANDBOX)/empty-library

# IMPORT: an empty library with lookups off, and $(SANDBOX)/downloads to
# import from (Tab completes; try a single file, the folder, subfolders)
try-import: clean-sandbox
	$(UV_RUN) python tools/mock_library.py $(SANDBOX)/downloads --downloads
	$(UV_RUN) python -c "from pathlib import Path; from bookman import Config, Library, NullSource, save_config; Library(Path('$(SANDBOX)/library'), source=NullSource()); save_config(Config(library=Path('$(CURDIR)/$(SANDBOX)/library'), offline=True), Path('$(SANDBOX)/config.json'))"
	cd $(SANDBOX) && env $(SANDBOX_ENV) $(UV_RUN) bookman-tui

# START-5: a library on a drive that isn't connected (`r` retries after you mkdir it)
try-missing: clean-sandbox
	env $(SANDBOX_ENV) $(UV_RUN) bookman-tui --library $(SANDBOX)/unplugged

# START-5: a folder of loose files
try-notlibrary: clean-sandbox
	mkdir -p $(SANDBOX)/downloads && touch $(SANDBOX)/downloads/book.epub
	env $(SANDBOX_ENV) $(UV_RUN) bookman-tui --library $(SANDBOX)/downloads

# START-4: an unreadable config file
try-badconfig: clean-sandbox
	echo 'not json' > $(SANDBOX)/config.json
	env $(SANDBOX_ENV) $(UV_RUN) bookman-tui

clean-sandbox:
	rm -rf $(SANDBOX)
	mkdir -p $(SANDBOX)
