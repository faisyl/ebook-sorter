from __future__ import annotations

import logging
from pathlib import Path

from ebook_sorter.extractors.base import BaseExtractor
from ebook_sorter.isbn import find_isbns, is_valid_isbn_13
from ebook_sorter.models import BookMetadata

logger = logging.getLogger(__name__)

_SUPPORTED_FORMATS: dict[str, str] = {
    ".pdf": "pdf",
    ".epub": "epub",
    ".mobi": "mobi",
    ".azw": "mobi",
    ".azw3": "mobi",
    ".djvu": "djvu",
    ".cbr": "comic",
    ".cbz": "comic",
}


class EmbeddedExtractor(BaseExtractor):
    def extract(self, path: Path) -> BookMetadata:
        ext = path.suffix.lower()
        fmt = _SUPPORTED_FORMATS.get(ext)
        if fmt is None:
            return BookMetadata(
                original_path=path,
                extension=ext.lstrip("."),
                source="embedded",
            )

        try:
            if fmt == "pdf":
                return self._extract_pdf(path)
            elif fmt == "epub":
                return self._extract_epub(path)
            elif fmt == "mobi":
                return self._extract_mobi(path)
            elif fmt == "djvu":
                return self._extract_djvu(path)
            elif fmt == "comic":
                return self._extract_comic(path)
        except Exception:
            logger.debug("Failed to extract embedded metadata from %s", path, exc_info=True)

        return BookMetadata(
            original_path=path,
            extension=ext.lstrip("."),
            source="embedded",
        )

    def _extract_pdf(self, path: Path) -> BookMetadata:
        from ebook_sorter.formats.pdf import extract_metadata

        raw = extract_metadata(path)
        title = raw.get("title") or None
        author_str = raw.get("author", "")
        authors = [a.strip() for a in author_str.split(",")] if author_str else []
        authors = [a for a in authors if a]

        return BookMetadata(
            title=title,
            authors=authors,
            extension="pdf",
            source="embedded",
            confidence=0.5 if title else 0.0,
            original_path=path,
        )

    def _extract_epub(self, path: Path) -> BookMetadata:
        from ebook_sorter.formats.epub import extract_metadata

        raw = extract_metadata(path)
        title = raw.get("title") or None
        authors = raw.get("authors", [])
        publisher = raw.get("publisher") or None
        language = raw.get("language") or None

        isbn_10 = None
        isbn_13 = None
        for ident in raw.get("identifiers", []):
            for found in find_isbns(str(ident)):
                if len(found) == 13 and is_valid_isbn_13(found):
                    isbn_13 = found
                elif len(found) == 10:
                    isbn_10 = found

        return BookMetadata(
            title=title,
            authors=authors,
            isbn_10=isbn_10,
            isbn_13=isbn_13,
            publisher=publisher,
            language=language,
            extension="epub",
            source="embedded",
            confidence=0.6 if title else 0.0,
            original_path=path,
        )

    def _extract_mobi(self, path: Path) -> BookMetadata:
        from ebook_sorter.formats.mobi import extract_metadata

        raw = extract_metadata(path)
        title = raw.get("title") or None
        author_str = raw.get("author(s)", "")
        authors = [a.strip() for a in author_str.split("&")] if author_str else []
        authors = [a for a in authors if a]

        return BookMetadata(
            title=title,
            authors=authors,
            extension=path.suffix.lstrip("."),
            source="embedded",
            confidence=0.5 if title else 0.0,
            original_path=path,
        )

    def _extract_djvu(self, path: Path) -> BookMetadata:
        from ebook_sorter.formats.djvu import extract_metadata

        raw = extract_metadata(path)
        title = raw.get("title") or None
        author_str = raw.get("author", "")
        authors = [a.strip() for a in author_str.split(",")] if author_str else []
        authors = [a for a in authors if a]

        return BookMetadata(
            title=title,
            authors=authors,
            extension="djvu",
            source="embedded",
            confidence=0.5 if title else 0.0,
            original_path=path,
        )

    def _extract_comic(self, path: Path) -> BookMetadata:
        from ebook_sorter.formats.comic import extract_metadata

        raw = extract_metadata(path)
        title = raw.get("title") or None
        series = raw.get("series") or None
        writer = raw.get("writer", "")
        authors = [a.strip() for a in writer.split(",")] if writer else []
        authors = [a for a in authors if a]
        year = None
        if raw.get("year"):
            try:
                year = int(raw["year"])
            except ValueError:
                pass
        series_index = None
        if raw.get("number"):
            try:
                series_index = float(raw["number"])
            except ValueError:
                pass

        return BookMetadata(
            title=title,
            authors=authors,
            series=series,
            series_index=series_index,
            year=year,
            extension=path.suffix.lstrip("."),
            source="embedded",
            confidence=0.5 if title else 0.0,
            original_path=path,
        )
