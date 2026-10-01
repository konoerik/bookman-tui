# Mirrors CLAUDE.md ## Development Workflow.
# The try-* targets run the app with its own bookman config in .dev/sandbox,
# so they never touch your real library or config.

SANDBOX := .dev/sandbox
MOCK := .dev/mock-library
BIG := .dev/mock-big
SANDBOX_ENV := BOOKMAN_CONFIG=$(CURDIR)/$(SANDBOX)/config.json BOOKMAN_LIBRARY=

.PHONY: test run dev console mock try-mock try-big try-real try-firstrun try-empty try-missing try-notlibrary try-badconfig clean-sandbox

test:
	uv run pytest

run:
	uv run bookman-tui

dev:
	uv run textual run --dev src/bookman_tui/app.py

console:
	uv run textual console

# The mock library (tools/mock_library.py): every state the browser shows.
# Rebuilt when the generator changes; `make mock` forces a rebuild.
$(MOCK): tools/mock_library.py
	uv run python tools/mock_library.py $(MOCK) --force

mock:
	uv run python tools/mock_library.py $(MOCK) --force

try-mock: $(MOCK) clean-sandbox
	env $(SANDBOX_ENV) uv run bookman-tui --library $(MOCK)

# The mock plus 2000 synthetic books, for speed. Slow to build (minutes).
$(BIG): tools/mock_library.py
	uv run python tools/mock_library.py $(BIG) --force --count 2000

try-big: $(BIG) clean-sandbox
	env $(SANDBOX_ENV) uv run bookman-tui --library $(BIG)

# A real library: make try-real LIB=path/to/a/copy (use a copy once the TUI can edit)
try-real: clean-sandbox
	@test -n "$(LIB)" || (echo "usage: make try-real LIB=path/to/library" && exit 1)
	env $(SANDBOX_ENV) uv run bookman-tui --library $(LIB)

# START-3 / SETUP: nothing configured. Try typing .dev/sandbox/new (created),
# .dev/sandbox/downloads (refused), .dev/sandbox/existing-library (opened),
# .dev/sandbox/empty (used)
try-firstrun: clean-sandbox
	mkdir -p $(SANDBOX)/downloads $(SANDBOX)/empty && touch $(SANDBOX)/downloads/book.epub
	uv run python -c "from pathlib import Path; from bookman import Library, NullSource; Library(Path('$(SANDBOX)/existing-library'), source=NullSource())"
	env $(SANDBOX_ENV) uv run bookman-tui

# START-2 / BROWSE-6: an empty library
try-empty: clean-sandbox
	mkdir -p $(SANDBOX)/empty-library
	env $(SANDBOX_ENV) uv run bookman-tui --library $(SANDBOX)/empty-library

# START-5: a library on a drive that isn't connected (`r` retries after you mkdir it)
try-missing: clean-sandbox
	env $(SANDBOX_ENV) uv run bookman-tui --library $(SANDBOX)/unplugged

# START-5: a folder of loose files
try-notlibrary: clean-sandbox
	mkdir -p $(SANDBOX)/downloads && touch $(SANDBOX)/downloads/book.epub
	env $(SANDBOX_ENV) uv run bookman-tui --library $(SANDBOX)/downloads

# START-4: an unreadable config file
try-badconfig: clean-sandbox
	echo 'not json' > $(SANDBOX)/config.json
	env $(SANDBOX_ENV) uv run bookman-tui

clean-sandbox:
	rm -rf $(SANDBOX)
	mkdir -p $(SANDBOX)
