from __future__ import annotations

import re
from pathlib import Path

from ebook_sorter.extractors.base import BaseExtractor
from ebook_sorter.isbn import find_isbns, is_valid_isbn_13
from ebook_sorter.models import BookMetadata

_YEAR_RE = re.compile(r"\((\d{4})(?:\b[^)]*)?\)")
_SERIES_RE = re.compile(r"\[([^\]]+?)(?:\s*#?\s*(\d+(?:\.\d+)?))?\s*\]")


class FilenameExtractor(BaseExtractor):
    def extract(self, path: Path) -> BookMetadata:
        stem = path.stem
        ext = path.suffix.lstrip(".")

        isbns = find_isbns(stem)
        isbn_10 = None
        isbn_13 = None
        for isbn in isbns:
            if len(isbn) == 13 and is_valid_isbn_13(isbn):
                isbn_13 = isbn
            elif len(isbn) == 10:
                isbn_10 = isbn

        year = None
        year_match = _YEAR_RE.search(stem)
        if year_match:
            year = int(year_match.group(1))

        series = None
        series_index = None
        series_match = _SERIES_RE.search(stem)
        if series_match:
            series = series_match.group(1).strip()
            if series_match.group(2):
                series_index = float(series_match.group(2))

        clean = stem
        for pattern in [_YEAR_RE, _SERIES_RE]:
            clean = pattern.sub("", clean)
        for isbn in isbns:
            clean = clean.replace(isbn, "")
        clean = re.sub(r"\[[\s]*\]", "", clean).strip()

        authors: list[str] = []
        title: str | None = None

        if " - " in clean:
            parts = [p.strip() for p in clean.split(" - ")]
            parts = [p for p in parts if p]
            if len(parts) >= 2:
                authors = [parts[0]]
                title = parts[-1] if parts[-1] else None
            elif len(parts) == 1:
                title = parts[0]
        else:
            title = clean.strip() if clean.strip() else None

        return BookMetadata(
            title=title,
            authors=authors,
            isbn_10=isbn_10,
            isbn_13=isbn_13,
            year=year,
            series=series,
            series_index=series_index,
            extension=ext,
            source="filename",
            confidence=0.4,
            original_path=path,
        )
