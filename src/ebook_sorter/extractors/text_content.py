"""Extract ISBNs from text content of ebook files."""

from __future__ import annotations

import logging
from pathlib import Path

from ebook_sorter.extractors.base import BaseExtractor
from ebook_sorter.isbn import find_isbns, find_isbns_with_context, is_valid_isbn_13
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

        # Extract ISBNs, separating high-confidence (prefixed with "ISBN")
        # from bare matches that could be false positives.
        prefixed_isbns, bare_isbns = find_isbns_with_context(text)

        isbn_10 = None
        isbn_13 = None
        confidence = 0.0

        # Prefer ISBN-prefixed matches (copyright page) — they appear first in text
        for isbn in prefixed_isbns:
            if len(isbn) == 13 and is_valid_isbn_13(isbn):
                if isbn_13 is None:
                    isbn_13 = isbn
            elif len(isbn) == 10:
                if isbn_10 is None:
                    isbn_10 = isbn
            if isbn_13 is not None and isbn_10 is not None:
                break

        if isbn_13 or isbn_10:
            confidence = 0.6
        else:
            # No prefixed ISBNs found — fall back to bare unordered matches.
            # These are likely false positives (page numbers, years, etc.)
            # but we try the FIRST few to see if any are real.
            for isbn in bare_isbns[:3]:
                if len(isbn) == 13 and is_valid_isbn_13(isbn):
                    if isbn_13 is None:
                        isbn_13 = isbn
                elif len(isbn) == 10:
                    if isbn_10 is None:
                        isbn_10 = isbn
                if isbn_13 is not None and isbn_10 is not None:
                    break

            if isbn_13 or isbn_10:
                confidence = 0.3

        return BookMetadata(
            isbn_10=isbn_10,
            isbn_13=isbn_13,
            extension=ext.lstrip("."),
            source="text_content",
            confidence=confidence,
            original_path=path,
        )
