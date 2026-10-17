"""How keys are written in hints, notifications and the footer (G-7).

A key is spelled the same everywhere (`Enter`, `Esc`, `Tab`, `Space`,
`ctrl+r`, letters as typed) and drawn as the footer draws it, so a single
letter reads as a key and not a word. Sentences say "Press `x` to …";
a line of several keys pairs each with its action, as the footer does.
"""

from __future__ import annotations

from textual.keys import format_key
from textual.markup import escape

NAMES = {"enter": "Enter", "escape": "Esc", "tab": "Tab", "space": "Space"}


def key_name(key: str) -> str:
    """A Textual key as G-7 spells it: "escape" → "Esc", "ctrl+r" stays
    "ctrl+r", "slash" → "/"."""
    *modifiers, base = key.split("+")
    return "+".join([*modifiers, NAMES.get(base, format_key(base))])


def key(name: str) -> str:
    """Markup for a key: bold, in the footer's key colour."""
    return f"[bold $footer-key-foreground]{escape(name)}[/]"


def press(name: str, action: str) -> str:
    """"Press `name` to `action`." as markup; `action` is markup too, so
    escape any path in it."""
    return f"Press {key(name)} to {action}."


def keys_line(*pairs: tuple[str, str]) -> str:
    """Several keys with their actions, footer-style, as markup:
    "Enter Import 3 files · Space Tick"."""
    return " · ".join(f"{key(name)} {escape(action)}" for name, action in pairs)
