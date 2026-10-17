"""How keys are written in hints, notifications and the footer (G-7)."""

from __future__ import annotations

from pathlib import Path

from textual.binding import Binding
from textual.content import Content
from textual.widgets import Static

from bookman_tui.app import BookmanApp
from bookman_tui.keys import key, key_name, keys_line, press
from bookman_tui.screens.setup import assess


def test_g_7_keys_spelled_one_way() -> None:
    assert [key_name(k) for k in ("enter", "escape", "tab", "space", "ctrl+r", "slash", "x", "F")] == [
        "Enter", "Esc", "Tab", "Space", "ctrl+r", "/", "x", "F",
    ]


def test_g_7_sentences_press_a_key_and_lists_pair_key_with_action() -> None:
    assert Content.from_markup(press("x", "stop it")).plain == "Press x to stop it."
    line = keys_line(("Enter", "Import 3 files"), ("a", "Tick all"))
    assert Content.from_markup(line).plain == "Enter Import 3 files · a Tick all"


def test_g_7_a_key_is_drawn_bold() -> None:
    content = Content.from_markup(press("x", "stop it"))
    styled = [content.plain[span.start:span.end] for span in content.spans if "bold" in str(span.style)]
    assert styled == ["x"]
    assert key("[x]") != "[x]"  # escaped, so it can't be taken as markup


def test_g_7_footer_says_esc_and_ctrl_r() -> None:
    app = BookmanApp()
    assert app.get_key_display(Binding("escape", "back", "Back")) == "Esc"
    assert app.get_key_display(Binding("ctrl+r", "reload", "Reload")) == "ctrl+r"
    assert app.get_key_display(Binding("question_mark", "help", "Keys", key_display="?")) == "?"


def test_g_7_a_path_with_brackets_shows_as_typed(tmp_path: Path) -> None:
    folder = tmp_path / "[old] books"
    message = assess(str(folder)).message
    shown = str(Static(message).render())
    assert "[old] books. Press Enter to create it." in shown
