"""Opening a book's folder in the system file manager (BROWSE-11)."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path


def folder_command(folder: Path, platform: str = sys.platform) -> list[str]:
    """The command that opens `folder` in the file manager: Finder on macOS,
    Explorer on Windows, the desktop's default elsewhere."""
    if platform == "darwin":
        return ["open", str(folder)]
    if platform == "win32":
        return ["explorer", str(folder)]
    return ["xdg-open", str(folder)]


def open_folder(folder: Path) -> None:
    """Run `folder_command`. The command hands the folder to the file
    manager and returns; its output would land on the TUI's screen, so it
    goes nowhere.

    Raises:
        OSError: If the command can't be run (e.g. no `xdg-open`).
    """
    subprocess.run(
        folder_command(folder),
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        check=False,
    )
