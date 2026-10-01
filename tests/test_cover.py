"""The cover slot (BROWSE-3, ADR-5)."""

from __future__ import annotations

import io
from pathlib import Path

from PIL import Image as PILImage
from textual.app import App, ComposeResult
from textual.widgets import Static

from bookman_tui.widgets.cover import Cover, Image


class CoverApp(App):
    CSS = "Cover { width: 28; height: 21; }"

    def compose(self) -> ComposeResult:
        yield Cover()


def write_image(path: Path, fmt: str, size=(120, 180)) -> Path:
    buffer = io.BytesIO()
    PILImage.new("RGB", size, (200, 40, 40)).save(buffer, format=fmt)
    path.write_bytes(buffer.getvalue())
    return path


async def show(app: CoverApp, pilot, path: Path | None) -> Cover:
    cover = app.query_one(Cover)
    cover.path = path
    await pilot.pause()
    await app.workers.wait_for_complete()
    await pilot.pause()
    return cover


def state(cover: Cover) -> tuple[bool, str | None]:
    """(image showing, message showing or None)."""
    picture = cover.query_one("#cover-image", Image)
    message = cover.query_one("#cover-message", Static)
    text = str(message.render()) if message.display else None
    return bool(picture.display and picture.image is not None), text


async def test_browse_3_cover_drawn_when_book_has_one(tmp_path: Path) -> None:
    app = CoverApp()
    async with app.run_test() as pilot:
        cover = await show(app, pilot, write_image(tmp_path / "cover.png", "PNG"))
        assert state(cover) == (True, None)
        assert not cover.showing_placeholder


async def test_browse_3_cover_placeholder_when_none() -> None:
    app = CoverApp()
    async with app.run_test() as pilot:
        cover = await show(app, pilot, None)
        assert state(cover) == (True, None)
        assert cover.showing_placeholder


async def test_browse_3_cover_unreadable_file_degrades_quietly(tmp_path: Path) -> None:
    broken = tmp_path / "cover.png"
    broken.write_bytes(b"not an image at all")
    app = CoverApp()
    async with app.run_test() as pilot:
        cover = await show(app, pilot, broken)
        assert state(cover) == (False, "Cover can't be shown")
        cover = await show(app, pilot, tmp_path / "missing.png")
        assert state(cover) == (False, "Cover can't be shown")


async def test_browse_3_cover_jpeg_bytes_in_png_name_are_read(tmp_path: Path) -> None:
    app = CoverApp()
    async with app.run_test() as pilot:
        cover = await show(app, pilot, write_image(tmp_path / "cover.png", "JPEG"))
        assert state(cover) == (True, None)


async def test_browse_3_cover_latest_selection_wins(tmp_path: Path) -> None:
    first = write_image(tmp_path / "a.png", "PNG", size=(120, 180))
    second = write_image(tmp_path / "b.png", "PNG", size=(180, 120))
    app = CoverApp()
    async with app.run_test() as pilot:
        cover = app.query_one(Cover)
        cover.path = first
        cover.path = second
        cover = await show(app, pilot, second)
        assert cover.query_one("#cover-image", Image).image.size == (180, 120)
        cover.path = first
        cover = await show(app, pilot, None)  # no cover after one was loading
        assert cover.showing_placeholder


async def test_browse_3_cover_slot_size_is_fixed(tmp_path: Path) -> None:
    app = CoverApp()
    async with app.run_test() as pilot:
        sizes = []
        for path in (write_image(tmp_path / "tall.png", "PNG", (100, 300)),
                     write_image(tmp_path / "wide.png", "PNG", (300, 100)),
                     None):
            cover = await show(app, pilot, path)
            sizes.append(cover.size)
        assert len(set(sizes)) == 1
