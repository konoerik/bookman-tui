"""Build a mock bookman library for visual review and tests.

Real EPUB and PDF files are written, then imported through bookman's public
API with a scripted `MetadataSource`, so bookman itself builds the library:
offline, deterministic, and never coupled to its on-disk layout. The
catalogue below is chosen to show every state the browser has to render.

    uv run python tools/mock_library.py DEST [--count N] [--force]

`--count N` adds N synthetic books on top, for checking speed at scale.
"""

from __future__ import annotations

import argparse
import hashlib
import random
import re
import shutil
import struct
import sys
import tempfile
import zipfile
import zlib
from dataclasses import dataclass
from pathlib import Path

from bookman import Book, Candidate, Library
from pypdf import PdfWriter
from pypdf.generic import DecodedStreamObject, DictionaryObject, NameObject


@dataclass(frozen=True)
class Record:
    """What the mock source knows about a book."""

    title: str
    author: str | None
    cover: bool = True
    needs_author: bool = False  # search finds it only when an author is given


@dataclass(frozen=True)
class Spec:
    """One book: its files as they arrive, and what the source says about it."""

    title: str | None
    author: str | None = None
    isbn: str | None = None
    kinds: tuple[str, ...] = ("epub",)
    record: Record | None = None
    stem: str | None = None  # file name without suffix; defaults to the title
    pdf_author: str | None = "same"  # the PDF's own author, when it differs
    epub_cover: bool = False  # embed a cover in the EPUB (ADR-28 fallback)
    password: bool = False  # a PDF bookman can't read inside (ReadIssue)
    then: str | None = None  # "review": mark reviewed; "edit:<author>": edit it


def isbn13(n: int) -> str:
    """A valid, obviously fake ISBN-13 (979-8-99…) numbered `n`."""
    body = f"97989{n:07d}"
    total = sum(int(d) * (1 if i % 2 == 0 else 3) for i, d in enumerate(body))
    return body + str((10 - total % 10) % 10)


# fmt: off
CATALOGUE: list[Spec] = [
    # --- Matched online by ISBN (✓), leading articles, record spells the author differently
    Spec("The Hobbit", "J. R. R. Tolkien", isbn13(1), record=Record("The Hobbit", "J.R.R. Tolkien")),
    Spec("Dune", "Frank Herbert", isbn13(2), kinds=("epub", "pdf"), record=Record("Dune", "Frank Herbert")),
    Spec("Deep Work", "Cal Newport", isbn13(3), record=Record("Deep work", "Cal Newport")),
    Spec("A Wizard of Earthsea", "Ursula K. Le Guin", isbn13(4), record=Record("A Wizard of Earthsea", "Ursula K. Le Guin")),
    Spec("An Absolutely Remarkable Thing", "Hank Green", isbn13(5), record=Record("An Absolutely Remarkable Thing", "Hank Green")),
    Spec("Thinking, Fast and Slow", "Daniel Kahneman", isbn13(6), record=Record("Thinking, Fast and Slow", "Daniel Kahneman", cover=False)),
    Spec("The Pragmatic Programmer: Your Journey to Mastery, 20th Anniversary Edition (2nd Edition)",
         "David Thomas, Andrew Hunt", isbn13(7),
         record=Record("The Pragmatic Programmer", "David Thomas, Andrew Hunt")),
    Spec("Cien años de soledad", "Gabriel García Márquez", isbn13(8), record=Record("Cien años de soledad", "Gabriel García Márquez")),
    Spec("ノルウェイの森", "村上春樹", isbn13(9), record=Record("ノルウェイの森", "村上春樹")),
    Spec("Project Hail Mary", "Andy Weir", isbn13(10), record=Record("Project Hail Mary", "Andy Weir")),
    Spec("Structure and Interpretation of Computer Programs", "Harold Abelson, Gerald Jay Sussman", isbn13(11),
         kinds=("pdf",), record=Record("Structure and Interpretation of Computer Programs", "Harold Abelson")),
    Spec("Sapiens: A Brief History of Humankind", "Yuval Noah Harari", isbn13(12), kinds=("epub", "pdf"),
         record=Record("Sapiens", "Yuval Noah Harari")),
    # --- Matched online by title and author (✓)
    Spec("Frankenstein", "Mary Shelley", record=Record("Frankenstein", "Mary Wollstonecraft Shelley")),
    Spec("Pride and Prejudice", "Jane Austen", record=Record("Pride and Prejudice", "Jane Austen")),
    Spec("Neuromancer", "William Gibson", record=Record("Neuromancer", "William Gibson", cover=False), epub_cover=True),
    Spec("Children of Dune", "Frank Herbert", record=Record("Children of Dune", "Frank Herbert")),
    Spec("Dune Messiah", "Frank Herbert", record=Record("Dune Messiah", "Frank Herbert")),
    Spec("The Left Hand of Darkness", "Ursula K. Le Guin", record=Record("The Left Hand of Darkness", "Ursula K. Le Guin")),
    Spec("Design Patterns: Elements of Reusable Object-Oriented Software",
         "Erich Gamma, Richard Helm, Ralph Johnson, John Vlissides",
         record=Record("Design Patterns", "Erich Gamma")),
    Spec("The Martian", "Andy Weir", record=Record("The Martian", "Andy Weir")),
    Spec("Snow Crash", "Neal Stephenson", record=Record("Snow Crash", "Neal Stephenson")),
    Spec("Anathem", "Neal Stephenson", record=Record("Anathem", "Neal Stephenson", cover=False)),
    Spec("Educated", "Tara Westover", kinds=("pdf",), record=Record("Educated", "Tara Westover")),
    # --- Needs review: matched online by title only (the file names no author)
    Spec("Meditations", None, record=Record("Meditations", "Marcus Aurelius")),
    Spec("The Art of War", None, record=Record("The Art of War", "Sun Tzu"), then="review"),
    # --- Needs review: formats grouped by title only (the PDF names no author)
    Spec("Walden", "Henry David Thoreau", kinds=("epub", "pdf"), pdf_author=None,
         record=Record("Walden", "Henry David Thoreau", needs_author=True)),
    # --- Needs review: not found online
    Spec("Notes on a Quiet Afternoon", "Priya Raman"),
    Spec("Quarterly Garden Planner", None, kinds=("pdf",)),
    Spec("Untitled", None, kinds=("pdf",), stem="field-guide-to-moths"),
    Spec("Grandmother's Recipes", None, then="edit:Rosa Lindqvist"),
    # --- Needs review: a PDF bookman can't read inside (named after its file)
    Spec(None, None, kinds=("pdf",), stem="statement-reader-locked", password=True),
]
# fmt: on


class MockSource:
    """A `MetadataSource` answering from the catalogue, never the network."""

    def __init__(self, specs: list[Spec]) -> None:
        self.by_isbn: dict[str, Record] = {}
        self.by_title: dict[str, list[Record]] = {}
        for spec in specs:
            if spec.record is None:
                continue
            if spec.isbn:
                self.by_isbn[spec.isbn] = spec.record
            self.by_title.setdefault(_key(spec.record.title), []).append(spec.record)

    def lookup_by_isbn(self, isbn: str) -> Candidate | None:
        record = self.by_isbn.get(isbn)
        return _candidate(record) if record else None

    def search(self, title: str, author: str | None = None) -> list[Candidate]:
        records = self.by_title.get(_key(title), [])
        return [_candidate(r) for r in records if author or not r.needs_author]

    def fetch_cover(self, url: str) -> bytes:
        return cover_png(url.removeprefix("mock://"))


def _key(title: str) -> str:
    """Search key: the title before any subtitle, lowercased."""
    return re.split(r"[:(]", title)[0].strip().lower()


def _candidate(record: Record) -> Candidate:
    cover = f"mock://{record.title}" if record.cover else None
    return Candidate(title=record.title, author=record.author, cover_url=cover)


def cover_png(seed: str, width: int = 120, height: int = 180) -> bytes:
    """A plain generated cover: a colour field with a lighter band, per `seed`."""
    digest = hashlib.sha256(seed.encode()).digest()
    base = digest[0] % 200 + 30, digest[1] % 200 + 30, digest[2] % 200 + 30
    band = tuple(min(255, c + 70) for c in base)
    rows = []
    for y in range(height):
        colour = band if height * 0.55 < y < height * 0.75 else base
        rows.append(b"\x00" + bytes(colour) * width)

    def chunk(kind: bytes, data: bytes) -> bytes:
        return struct.pack(">I", len(data)) + kind + data + struct.pack(">I", zlib.crc32(kind + data))

    header = struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0)
    return (
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", header)
        + chunk(b"IDAT", zlib.compress(b"".join(rows)))
        + chunk(b"IEND", b"")
    )


CONTAINER = (
    '<?xml version="1.0"?><container version="1.0" '
    'xmlns="urn:oasis:names:tc:opendocument:xmlns:container"><rootfiles>'
    '<rootfile full-path="OEBPS/content.opf" media-type="application/oebps-package+xml"/>'
    "</rootfiles></container>"
)


def _xml(text: str) -> str:
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def write_epub(path: Path, spec: Spec) -> None:
    meta = []
    if spec.title:
        meta.append(f"<dc:title>{_xml(spec.title)}</dc:title>")
    if spec.author:
        meta.append(f"<dc:creator>{_xml(spec.author)}</dc:creator>")
    if spec.isbn:
        meta.append(f"<dc:identifier>urn:isbn:{spec.isbn}</dc:identifier>")
    manifest = '<item id="text" href="text.xhtml" media-type="application/xhtml+xml"/>'
    if spec.epub_cover:
        manifest += '<item id="cover" href="cover.png" media-type="image/png" properties="cover-image"/>'
    opf = (
        '<?xml version="1.0"?><package xmlns="http://www.idpf.org/2007/opf" version="3.0">'
        f'<metadata xmlns:dc="http://purl.org/dc/elements/1.1/">{"".join(meta)}</metadata>'
        f'<manifest>{manifest}</manifest><spine><itemref idref="text"/></spine></package>'
    )
    with zipfile.ZipFile(path, "w") as zf:
        zf.writestr("mimetype", "application/epub+zip", compress_type=zipfile.ZIP_STORED)
        zf.writestr("META-INF/container.xml", CONTAINER)
        zf.writestr("OEBPS/content.opf", opf)
        zf.writestr("OEBPS/text.xhtml", f"<html><body><p>{_xml(spec.title or '')}</p></body></html>")
        if spec.epub_cover:
            zf.writestr("OEBPS/cover.png", cover_png(f"epub:{spec.title}"))


def write_pdf(path: Path, spec: Spec) -> None:
    writer = PdfWriter()
    page = writer.add_blank_page(width=200, height=200)
    text = f"ISBN {spec.isbn}" if spec.isbn else ""
    content = DecodedStreamObject()
    content.set_data(f"BT /F1 12 Tf 10 100 Td ({text}) Tj ET".encode())
    page[NameObject("/Contents")] = writer._add_object(content)
    font = DictionaryObject(
        {
            NameObject("/Type"): NameObject("/Font"),
            NameObject("/Subtype"): NameObject("/Type1"),
            NameObject("/BaseFont"): NameObject("/Helvetica"),
        }
    )
    fonts = DictionaryObject({NameObject("/F1"): writer._add_object(font)})
    page[NameObject("/Resources")] = DictionaryObject({NameObject("/Font"): fonts})
    author = spec.author if spec.pdf_author == "same" else spec.pdf_author
    metadata = {}
    if spec.title:
        metadata["/Title"] = spec.title
    if author:
        metadata["/Author"] = author
    if metadata:
        writer.add_metadata(metadata)
    if spec.password:
        writer.encrypt(user_password="secret", owner_password="owner", algorithm="RC4-128")
    with path.open("wb") as f:
        writer.write(f)


def _stem(spec: Spec) -> str:
    return spec.stem or re.sub(r"[^\w]+", "-", spec.title or "untitled").strip("-")


def synthetic(count: int) -> list[Spec]:
    """`count` filler books with a deterministic mix of states."""
    rng = random.Random(42)
    specs = []
    for n in range(count):
        title = f"Synthetic Volume {n + 1:05d}"
        author = f"Author {rng.randrange(max(count // 8, 1)):04d}"
        roll = rng.random()
        if roll < 0.5:
            spec = Spec(title, author, isbn13(100_000 + n), record=Record(title, author, cover=rng.random() < 0.7))
        elif roll < 0.8:
            spec = Spec(title, author, record=Record(title, author))
        elif roll < 0.9:
            spec = Spec(title, None, record=Record(title, author))
        else:
            spec = Spec(title, author)
        specs.append(spec)
    return specs


def build(dest: Path, count: int = 0) -> list[Book]:
    """Build the mock library at `dest`, which must not exist yet."""
    if dest.exists():
        raise FileExistsError(f"{dest} already exists; pass --force to rebuild it")
    specs = CATALOGUE + synthetic(count)
    library = Library(dest, source=MockSource(specs))
    with tempfile.TemporaryDirectory() as staging:
        for spec in specs:
            book = None
            for kind in spec.kinds:
                path = Path(staging) / f"{_stem(spec)}.{kind}"
                (write_epub if kind == "epub" else write_pdf)(path, spec)
                book = library.import_file(path)
            assert book is not None
            if spec.then == "review":
                library.mark_reviewed(book)
            elif spec.then and spec.then.startswith("edit:"):
                library.edit(book, author=spec.then.removeprefix("edit:"))
    return library.scan()


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("dest", type=Path)
    parser.add_argument("--count", type=int, default=0, help="synthetic books to add")
    parser.add_argument("--force", action="store_true", help="replace dest if it exists")
    args = parser.parse_args(argv)
    if args.force and args.dest.exists():
        shutil.rmtree(args.dest)
    books = build(args.dest, args.count)
    queue = sum(book.needs_review for book in books)
    print(f"{args.dest}: {len(books)} books, {queue} need review", file=sys.stderr)


if __name__ == "__main__":
    main()
