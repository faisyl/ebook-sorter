from __future__ import annotations

import logging
import re

from ebook_sorter.isbn import find_isbns, is_valid_isbn_13
from ebook_sorter.lookup.base import BaseLookup
from ebook_sorter.lookup.http import RateLimitedClient
from ebook_sorter.models import BookMetadata

logger = logging.getLogger(__name__)

_BASE = "https://openlibrary.org"


class OpenLibraryLookup(BaseLookup):
    def __init__(self, timeout: float = 30.0) -> None:
        self._client = RateLimitedClient(min_interval=1.0, timeout=timeout)

    def lookup_isbn(self, isbn: str) -> BookMetadata | None:
        try:
            resp = self._client.get(
                f"{_BASE}/api/books",
                params={
                    "bibkeys": f"ISBN:{isbn}",
                    "format": "json",
                    "jscmd": "data",
                },
            )
            if resp.status_code == 429:
                logger.warning("Open Library rate limited for ISBN: %s", isbn)
                return None
            resp.raise_for_status()
            data = resp.json()
        except Exception:
            logger.debug("Open Library ISBN lookup failed for %s", isbn, exc_info=True)
            return None

        key = f"ISBN:{isbn}"
        if key not in data:
            return None

        book = data[key]
        return self._parse_book(book, isbn)

    def search(self, title: str, author: str = "") -> BookMetadata | None:
        query = title
        if author:
            query = f"{title} {author}"
        try:
            resp = self._client.get(
                f"{_BASE}/search.json",
                params={"q": query, "limit": 1},
            )
            if resp.status_code == 429:
                logger.warning("Open Library rate limited for search: %s", query)
                return None
            resp.raise_for_status()
            data = resp.json()
        except Exception:
            logger.debug("Open Library search failed for %s", query, exc_info=True)
            return None

        docs = data.get("docs", [])
        if not docs:
            return None

        doc = docs[0]
        isbn_13 = None
        isbn_10 = None
        for raw_isbn in doc.get("isbn", []):
            for found in find_isbns(raw_isbn):
                if len(found) == 13 and is_valid_isbn_13(found):
                    isbn_13 = isbn_13 or found
                elif len(found) == 10:
                    isbn_10 = isbn_10 or found

        year = doc.get("first_publish_year")

        return BookMetadata(
            title=doc.get("title"),
            authors=doc.get("author_name", []),
            isbn_13=isbn_13,
            isbn_10=isbn_10,
            publisher=(doc.get("publisher") or [None])[0],
            year=year,
            source="openlibrary",
            confidence=0.7,
        )

    def _parse_book(self, book: dict, isbn: str) -> BookMetadata:
        authors = [a["name"] for a in book.get("authors", [])]
        publishers = [p["name"] for p in book.get("publishers", [])]
        year = None
        pub_date = book.get("publish_date", "")
        year_match = re.search(r"\d{4}", pub_date)
        if year_match:
            year = int(year_match.group())

        isbn_13 = isbn if len(isbn) == 13 else None
        isbn_10 = isbn if len(isbn) == 10 else None

        return BookMetadata(
            title=book.get("title"),
            authors=authors,
            isbn_13=isbn_13,
            isbn_10=isbn_10,
            publisher=publishers[0] if publishers else None,
            year=year,
            source="openlibrary",
            confidence=0.95,
        )
