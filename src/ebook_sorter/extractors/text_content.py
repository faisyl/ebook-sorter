from __future__ import annotations

import logging
from pathlib import Path

from ebook_sorter.extractors.base import BaseExtractor
from ebook_sorter.isbn import find_isbns, is_valid_isbn_13
from ebook_sorter.models import BookMetadata

logger = logging.getLogger(__name__)


class TextContentExtractor(BaseExtractor):
    def __init__(self, first_pages: int = 7, last_pages: int = 3) -> None:
        self.first_pages = first_pages
        self.last_pages = last_pages

    def extract(self, path: Path) -> BookMetadata:
        ext = path.suffix.lower()
        text = ""

        try:
            if ext == ".pdf":
                from ebook_sorter.formats.pdf import extract_text

                text = extract_text(path, self.first_pages, self.last_pages)
            elif ext == ".epub":
                from ebook_sorter.formats.epub import extract_text

                text = extract_text(path)
            elif ext == ".djvu":
                from ebook_sorter.formats.djvu import extract_text

                text = extract_text(path)
            elif ext in (".mobi", ".azw", ".azw3"):
                from ebook_sorter.formats.mobi import extract_text

                text = extract_text(path)
        except Exception:
            logger.debug("Text extraction failed for %s", path, exc_info=True)

        isbns = find_isbns(text)
        isbn_10 = None
        isbn_13 = None
        for isbn in isbns:
            if len(isbn) == 13 and is_valid_isbn_13(isbn):
                isbn_13 = isbn
            elif len(isbn) == 10:
                isbn_10 = isbn

        return BookMetadata(
            isbn_10=isbn_10,
            isbn_13=isbn_13,
            extension=ext.lstrip("."),
            source="text_content",
            confidence=0.5 if (isbn_10 or isbn_13) else 0.0,
            original_path=path,
        )
