from __future__ import annotations

import logging
import re

import httpx

from ebook_sorter.lookup.base import BaseLookup
from ebook_sorter.models import BookMetadata

logger = logging.getLogger(__name__)

_BASE = "https://www.googleapis.com/books/v1/volumes"


class GoogleBooksLookup(BaseLookup):
    def __init__(self, timeout: float = 15.0) -> None:
        self._timeout = timeout

    def lookup_isbn(self, isbn: str) -> BookMetadata | None:
        return self._query(f"isbn:{isbn}", is_isbn_lookup=True)

    def search(self, title: str, author: str = "") -> BookMetadata | None:
        query = f'intitle:"{title}"'
        if author:
            query += f' inauthor:"{author}"'
        return self._query(query, is_isbn_lookup=False)

    def _query(self, q: str, is_isbn_lookup: bool) -> BookMetadata | None:
        try:
            resp = httpx.get(
                _BASE,
                params={"q": q, "maxResults": 5},
                timeout=self._timeout,
            )
            resp.raise_for_status()
            data = resp.json()
        except (httpx.HTTPError, ValueError):
            logger.debug("Google Books query failed: %s", q, exc_info=True)
            return None

        if data.get("totalItems", 0) == 0 or "items" not in data:
            return None

        vol = data["items"][0]["volumeInfo"]
        isbn_10 = None
        isbn_13 = None
        for ident in vol.get("industryIdentifiers", []):
            if ident["type"] == "ISBN_13":
                isbn_13 = ident["identifier"]
            elif ident["type"] == "ISBN_10":
                isbn_10 = ident["identifier"]

        year = None
        pub_date = vol.get("publishedDate", "")
        year_match = re.search(r"\d{4}", pub_date)
        if year_match:
            year = int(year_match.group())

        return BookMetadata(
            title=vol.get("title"),
            authors=vol.get("authors", []),
            isbn_10=isbn_10,
            isbn_13=isbn_13,
            publisher=vol.get("publisher"),
            year=year,
            language=vol.get("language"),
            source="google_books",
            confidence=0.95 if is_isbn_lookup else 0.7,
        )
