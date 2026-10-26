# The README demo: `make demo` builds .dev/demo and renders docs/demo.gif.
# Needs VHS (https://github.com/charmbracelet/vhs). Runs offline against a
# fresh mock library, so every run records the same thing.

Output docs/demo.gif

Set Shell bash
Set FontSize 14
Set Width 1200
Set Height 700
Set Padding 16
Set WindowBar Colorful
Set TypingSpeed 90ms
Set Theme "Builtin Dark"

Hide
Type `export HOME=$PWD/.dev/demo/home BOOKMGR_CONFIG=$PWD/.dev/demo/config.json BOOKMGR_TUI_PREFS=$PWD/.dev/demo/prefs.json BOOKMGR_LIBRARY= PS1="$ " && source .venv/bin/activate && alias bookmgr-tui="python $PWD/demo/halfcell.py" && cd ~ && clear`
Enter
Sleep 500ms
Show

# Launch and browse
Type "bookmgr-tui"
Sleep 400ms
Enter
Sleep 3s
Type@600ms "jjjj"
Sleep 1s

# Search
Type "/"
Sleep 300ms
Type@200ms "dune"
Sleep 2s
Escape
Sleep 1s

# Group by status: the review queue first
Type@800ms "gg"
Sleep 2s

# Fix a book bookmgr couldn't identify: it leaves the review queue
# (8 up from "Children of Dune" to "field-guide-to-moths": recount if
# tools/mock_library.py changes)
Type@250ms "kkkkkkkk"
Sleep 1s
Type "e"
Sleep 1.5s
Ctrl+U
Type "A Field Guide to Moths"
Tab
Type "Edith Hartley"
Sleep 1s
Enter
Sleep 3s
Type "q"
Sleep 1s
