from __future__ import annotations

import logging
import re

from ebook_sorter.lookup.base import BaseLookup
from ebook_sorter.lookup.http import RateLimitedClient
from ebook_sorter.models import BookMetadata

logger = logging.getLogger(__name__)

_BASE = "https://www.googleapis.com/books/v1/volumes"


class GoogleBooksLookup(BaseLookup):
    def __init__(self, timeout: float = 15.0, api_key: str | None = None) -> None:
        interval = 1.0 if api_key else 3.0
        self._client = RateLimitedClient(min_interval=interval, timeout=timeout)
        self._api_key = api_key

    def lookup_isbn(self, isbn: str) -> BookMetadata | None:
        return self._query(f"isbn:{isbn}", is_isbn_lookup=True)

    def search(self, title: str, author: str = "") -> BookMetadata | None:
        query = f'intitle:"{title}"'
        if author:
            query += f' inauthor:"{author}"'
        return self._query(query, is_isbn_lookup=False)

    def _query(self, q: str, is_isbn_lookup: bool) -> BookMetadata | None:
        try:
            params: dict[str, str | int] = {"q": q, "maxResults": 1}
            if self._api_key:
                params["key"] = self._api_key
            resp = self._client.get(_BASE, params=params)
            if resp.status_code == 429:
                logger.warning("Google Books rate limited for query: %s", q)
                return None
            resp.raise_for_status()
            data = resp.json()
        except Exception:
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
