from __future__ import annotations

import html.parser
import xml.etree.ElementTree as ET
import zipfile
from pathlib import Path

import ebooklib
from ebooklib import epub

_DC = "http://purl.org/dc/elements/1.1/"
_CONTAINER_PATH = "META-INF/container.xml"


def _opf_path_from_zip(zf: zipfile.ZipFile) -> str | None:
    try:
        data = zf.read(_CONTAINER_PATH)
        root = ET.fromstring(data)
        ns = {"c": "urn:oasis:names:tc:opendocument:xmlns:container"}
        rf = root.find(".//c:rootfile", ns)
        return rf.get("full-path") if rf is not None else None
    except Exception:
        return None


def _metadata_from_zip(path: Path) -> dict[str, object]:
    with zipfile.ZipFile(str(path), "r") as zf:
        opf_path = _opf_path_from_zip(zf)
        if opf_path is None:
            return {"title": "", "authors": [], "identifiers": [], "publisher": "", "language": ""}
        root = ET.fromstring(zf.read(opf_path))
        def dc(tag: str) -> list[str]:
            return [el.text or "" for el in root.iter(f"{{{_DC}}}{tag}")]
        titles = dc("title")
        authors = dc("creator")
        identifiers = dc("identifier")
        publishers = dc("publisher")
        languages = dc("language")
    return {
        "title": titles[0] if titles else "",
        "authors": authors,
        "identifiers": identifiers,
        "publisher": publishers[0] if publishers else "",
        "language": languages[0] if languages else "",
    }


def _text_from_zip(path: Path) -> str:
    parts: list[str] = []
    with zipfile.ZipFile(str(path), "r") as zf:
        for name in zf.namelist():
            if name.lower().endswith((".html", ".xhtml", ".htm")):
                try:
                    text = _html_to_text(zf.read(name))
                    if text.strip():
                        parts.append(text)
                except Exception:
                    pass
    return "\n".join(parts)


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
    try:
        book = epub.read_epub(str(path), options={"ignore_ncx": True})
    except (KeyError, AttributeError):
        return _metadata_from_zip(path)

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
    try:
        book = epub.read_epub(str(path), options={"ignore_ncx": True})
    except (KeyError, AttributeError):
        return _text_from_zip(path)
    parts: list[str] = []
    for item in book.get_items_of_type(ebooklib.ITEM_DOCUMENT):
        text = _html_to_text(item.get_content())
        if text.strip():
            parts.append(text)
    return "\n".join(parts)
