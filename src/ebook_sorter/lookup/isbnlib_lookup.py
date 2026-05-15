from __future__ import annotations

import logging

from ebook_sorter.lookup.base import BaseLookup
from ebook_sorter.models import BookMetadata

logger = logging.getLogger(__name__)

try:
    import isbnlib
    _AVAILABLE = True
except Exception:
    _AVAILABLE = False


class IsbnlibLookup(BaseLookup):
    def lookup_isbn(self, isbn: str) -> BookMetadata | None:
        if not _AVAILABLE:
            return None
        try:
            data = isbnlib.meta(isbn)
        except Exception:
            logger.debug("isbnlib meta failed for %s", isbn, exc_info=True)
            return None

        if not data or not data.get("Title"):
            return None

        authors = data.get("Authors", [])
        if isinstance(authors, str):
            authors = [authors]

        year = None
        pub_date = data.get("Year", "")
        if pub_date and pub_date.isdigit():
            year = int(pub_date)

        isbn_13 = None
        isbn_10 = None
        if len(isbn) == 13:
            isbn_13 = isbn
        elif len(isbn) == 10:
            isbn_10 = isbn

        return BookMetadata(
            title=data.get("Title"),
            authors=authors,
            isbn_10=isbn_10,
            isbn_13=isbn_13,
            publisher=data.get("Publisher"),
            year=year,
            language=data.get("Language"),
            source="isbnlib",
            confidence=0.95,
        )

    def search(self, title: str, author: str = "") -> BookMetadata | None:
        return None
