from __future__ import annotations

import html.parser
from pathlib import Path

import ebooklib
from ebooklib import epub


class _TextExtractor(html.parser.HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self._parts: list[str] = []

    def handle_data(self, data: str) -> None:
        self._parts.append(data)

    def get_text(self) -> str:
        return " ".join(self._parts)


def _html_to_text(content: bytes) -> str:
    parser = _TextExtractor()
    parser.feed(content.decode("utf-8", errors="replace"))
    return parser.get_text()


def extract_metadata(path: Path) -> dict[str, object]:
    if not path.exists():
        raise FileNotFoundError(f"File not found: {path}")
    book = epub.read_epub(str(path), options={"ignore_ncx": True})

    title_entries = book.get_metadata("DC", "title")
    title = title_entries[0][0] if title_entries else ""

    author_entries = book.get_metadata("DC", "creator")
    authors = [a[0] for a in author_entries] if author_entries else []

    id_entries = book.get_metadata("DC", "identifier")
    identifiers = [i[0] for i in id_entries] if id_entries else []

    pub_entries = book.get_metadata("DC", "publisher")
    publisher = pub_entries[0][0] if pub_entries else ""

    lang_entries = book.get_metadata("DC", "language")
    language = lang_entries[0][0] if lang_entries else ""

    return {
        "title": title,
        "authors": authors,
        "identifiers": identifiers,
        "publisher": publisher,
        "language": language,
    }


def extract_text(path: Path) -> str:
    if not path.exists():
        raise FileNotFoundError(f"File not found: {path}")
    book = epub.read_epub(str(path), options={"ignore_ncx": True})
    parts: list[str] = []
    for item in book.get_items_of_type(ebooklib.ITEM_DOCUMENT):
        text = _html_to_text(item.get_content())
        if text.strip():
            parts.append(text)
    return "\n".join(parts)
