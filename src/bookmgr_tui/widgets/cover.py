"""A book's cover in the detail pane, drawn with `textual-image` (ADR-5).

Importing this module also imports `textual_image.widget`, which asks the
terminal for its cell size; that only works before the App starts, so this
module must be imported at startup (it is, via the browser screen).
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from PIL import Image as PILImage
from PIL import ImageDraw
from textual import work
from textual.app import ComposeResult
from textual.color import Color
from textual.reactive import reactive
from textual.widget import Widget
from textual.widgets import Static
from textual.worker import get_current_worker
from textual_image.renderable import Image as AutoRenderable
from textual_image.renderable.unicode import Image as UnicodeRenderable
from textual_image.widget import HalfcellImage
from textual_image.widget import Image as AutoImage

# Outside a terminal (tests, screenshots) textual-image falls back to its
# monochrome Unicode renderer, which can't show a cover; half-block is what a
# terminal without graphics (e.g. Alacritty) gets anyway.
Image = HalfcellImage if AutoRenderable is UnicodeRenderable else AutoImage

DECODE_BOX = (480, 720)
"""Covers are shrunk to at most this many pixels before drawing: plenty for
a 20×14-cell slot under any protocol, and cheap to redraw."""


class Cover(Widget):
    """The cover slot: a fixed box in the detail pane (BROWSE-3).

    The box is the same size for every book (28 columns × 21 rows),
    so the text below it doesn't jump as the selection moves. The image is
    scaled to fit inside it keeping its proportions, centred, with the box's
    background showing around it.

    Drawing uses the best method the terminal supports, picked by
    `textual-image`: the kitty graphics protocol, then sixel, then coloured
    half-block characters (works everywhere, coarse).

    `cover.png` holds the bytes as received (often JPEG), so the format is
    read from the content, never the suffix.

    The image is decoded off the UI thread (G-1), and only the latest
    request counts: moving quickly through the list never shows a stale
    cover, and never queues up decoding work.

    Degrades quietly (ADR-5), in the box's place:
    - `path` is None: a generated placeholder (a plain book drawn in the
      theme's panel colours), so the slot looks the same as with a cover
    - the file is missing or isn't an image Pillow can read: "Cover can't
      be shown", and the reason goes to the Textual log, not the user

    Attributes:
        path: The cover file (`Book.cover_path`), or None.
    """

    path: reactive[Path | None] = reactive(None)

    showing_placeholder = False
    """True while the slot shows the no-cover placeholder."""

    def compose(self) -> ComposeResult:
        yield Image(id="cover-image")
        yield Static("No cover", id="cover-message")

    def watch_path(self, path: Path | None) -> None:
        if path is None:
            # A decode still running for the previous book must not land here.
            self.workers.cancel_group(self, "cover")
            self._show(self._placeholder(), None, placeholder=True)
        else:
            self.load(path)

    @work(thread=True, exclusive=True, group="cover")
    def load(self, path: Path) -> None:
        """Decode `path` off the UI thread; a newer request cancels this one."""
        try:
            with PILImage.open(path) as source:
                image = source.convert("RGB")
            image.thumbnail(DECODE_BOX)
        except (OSError, PILImage.DecompressionBombError) as error:
            self.log.warning(f"cover {path}: {error}")
            image, message = None, "Cover can't be shown"
        else:
            message = None
        if not get_current_worker().is_cancelled:
            self.app.call_from_thread(self._show, image, message)

    def _placeholder(self) -> PILImage.Image:
        variables = self.app.theme_variables
        return placeholder(variables.get("panel", "#2b2b2b"))

    def _show(self, image: PILImage.Image | None, message: str | None, *, placeholder: bool = False) -> None:
        self.showing_placeholder = placeholder
        picture = self.query_one("#cover-image", Image)
        text = self.query_one("#cover-message", Static)
        picture.image = image
        picture.display = image is not None
        text.display = image is None
        if message:
            text.update(message)


@lru_cache(maxsize=4)
def placeholder(background: str) -> PILImage.Image:
    """A plain 2:3 book for the no-cover slot, drawn in shades of the theme's
    panel colour so it suits light and dark themes alike.

    Coarse shapes only (cover, spine, two title bars) so it still reads as a
    book at half-block resolution (28×42 pixels).
    """
    width, height = 280, 420
    base = Color.parse(background)
    back = base.rgb
    front = base.lighten(0.22).rgb
    shade = base.lighten(0.12).rgb
    image = PILImage.new("RGB", (width, height), back)
    draw = ImageDraw.Draw(image)
    left, top, right, bottom = 50, 45, width - 50, height - 45
    draw.rectangle((left, top, right, bottom), fill=front)
    draw.rectangle((left, top, left + 22, bottom), fill=shade)  # spine
    bar_left = left + 50
    draw.rectangle((bar_left, top + 70, right - 30, top + 100), fill=back)
    draw.rectangle((bar_left, top + 125, right - 70, top + 145), fill=back)
    return image
