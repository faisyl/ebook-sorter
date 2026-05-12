from __future__ import annotations

import logging
import re
import shutil
import subprocess

from ebook_sorter.lookup.base import BaseLookup
from ebook_sorter.models import BookMetadata

logger = logging.getLogger(__name__)


def _parse_fetch_output(output: str) -> dict[str, str]:
    result: dict[str, str] = {}
    for line in output.splitlines():
        if ":" in line:
            key, _, value = line.partition(":")
            key = key.strip().lower()
            value = value.strip()
            if key and value:
                result[key] = value
    return result


class CalibreLookup(BaseLookup):
    def __init__(self, timeout: float = 60.0) -> None:
        self._timeout = timeout

    def _is_available(self) -> bool:
        return shutil.which("fetch-ebook-metadata") is not None

    def lookup_isbn(self, isbn: str) -> BookMetadata | None:
        if not self._is_available():
            return None
        return self._fetch(["--isbn", isbn])

    def search(self, title: str, author: str = "") -> BookMetadata | None:
        if not self._is_available():
            return None
        args = ["--title", title]
        if author:
            args.extend(["--author", author])
        return self._fetch(args)

    def _fetch(self, extra_args: list[str]) -> BookMetadata | None:
        cmd = ["fetch-ebook-metadata"] + extra_args
        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=self._timeout,
            )
        except subprocess.TimeoutExpired:
            logger.debug("Calibre fetch timed out: %s", cmd)
            return None

        if result.returncode != 0 or not result.stdout.strip():
            return None

        parsed = _parse_fetch_output(result.stdout)
        if not parsed.get("title"):
            return None

        author_str = parsed.get("author(s)", "")
        authors = [a.strip() for a in re.split(r"[,&]", author_str)] if author_str else []
        authors = [a for a in authors if a]

        year = None
        pub_date = parsed.get("published", "")
        year_match = re.search(r"\d{4}", pub_date)
        if year_match:
            year = int(year_match.group())

        isbn = parsed.get("isbn")
        isbn_10 = None
        isbn_13 = None
        if isbn:
            if len(isbn) == 13:
                isbn_13 = isbn
            elif len(isbn) == 10:
                isbn_10 = isbn

        return BookMetadata(
            title=parsed.get("title"),
            authors=authors,
            isbn_10=isbn_10,
            isbn_13=isbn_13,
            publisher=parsed.get("publisher"),
            year=year,
            source="calibre",
            confidence=0.9,
        )
