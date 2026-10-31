# The PyPI readme screenshot: `make screenshot` builds .dev/demo and renders
# docs/screenshot.png (PyPI shows README.pypi.md, where a GIF is too heavy).
# Same setup as demo.tape; the frame is the browser on a selected book.

Output .dev/demo/screenshot.gif

Set Shell bash
Set FontSize 14
Set Width 1200
Set Height 700
Set Padding 16
Set WindowBar Colorful
Set Theme "Builtin Dark"

Hide
Type `export HOME=$PWD/.dev/demo/home BOOKMGR_CONFIG=$PWD/.dev/demo/config.json BOOKMGR_TUI_PREFS=$PWD/.dev/demo/prefs.json BOOKMGR_LIBRARY= PS1="$ " && source .venv/bin/activate && alias bookmgr-tui="python $PWD/demo/halfcell.py" && cd ~ && clear`
Enter
Sleep 500ms
Type "bookmgr-tui"
Enter
Sleep 3s
Type "jjjj"
Sleep 1.5s
Show
Sleep 500ms
Screenshot docs/screenshot.png
Hide
Type "q"
Sleep 1s
