# Conventions

> Reference style — pattern-match against these before writing or editing code.
> Modify to reflect actual project choices.

## Widget

```python
from textual.app import ComposeResult
from textual.message import Message
from textual.reactive import reactive
from textual.widget import Widget
from textual.widgets import Label


class CounterWidget(Widget):
    """A simple counter with increment support."""

    count: reactive[int] = reactive(0)

    class Incremented(Message):
        """Posted when the counter is incremented."""
        def __init__(self, value: int) -> None:
            super().__init__()
            self.value = value

    def compose(self) -> ComposeResult:
        yield Label("0", id="count-label")

    def watch_count(self, value: int) -> None:
        self.query_one("#count-label", Label).update(str(value))

    def increment(self) -> None:
        self.count += 1
        self.post_message(self.Incremented(self.count))
```

## Stub (pre-implementation)

> Write this first for new public widgets and pause for review — see `## Behavior Rules` in `.claude/claudify.md`.

```python
class FilterableList(Widget):
    """A list widget that filters items as the user types.

    Messages:
        Selected: Posted when an item is chosen.

    Raises:
        ValueError: If constructed with an empty items list.
    """

    def compose(self) -> ComposeResult:
        raise NotImplementedError

    def filter_items(self, query: str) -> list[str]:
        raise NotImplementedError


# Test scenarios (names only, no bodies yet):
# test_filterable_list_empty_items_raises
# test_filter_items_matches_case_insensitive
# test_filter_items_no_match_returns_empty
# test_selecting_item_posts_selected_message
```

## Screen

```python
from textual.app import ComposeResult
from textual.screen import Screen
from textual.widgets import Footer, Header


class MainScreen(Screen):
    """Primary screen."""

    BINDINGS = [("q", "app.quit", "Quit")]

    def compose(self) -> ComposeResult:
        yield Header()
        yield CounterWidget()
        yield Footer()

    def on_counter_widget_incremented(self, event: CounterWidget.Incremented) -> None:
        self.notify(f"Count: {event.value}")
```

## Test

```python
import pytest
from textual.testing import AppTest
from app import MyApp


@pytest.mark.asyncio
async def test_counter_increments():
    async with AppTest(MyApp()) as pilot:
        await pilot.click("#increment-btn")
        label = pilot.app.query_one("#count-label")
        assert label.renderable == "1"
```
