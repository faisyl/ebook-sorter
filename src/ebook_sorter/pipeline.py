from __future__ import annotations

import logging
from pathlib import Path

from ebook_sorter.extractors.base import BaseExtractor
from ebook_sorter.lookup.base import BaseLookup
from ebook_sorter.models import BookMetadata

logger = logging.getLogger(__name__)


class Pipeline:
    def __init__(
        self,
        extractors: list[BaseExtractor],
        lookups: list[BaseLookup],
    ) -> None:
        self.extractors = extractors
        self.lookups = lookups

    def process(self, path: Path) -> BookMetadata:
        merged = BookMetadata(original_path=path, extension=path.suffix.lstrip("."))

        for extractor in self.extractors:
            try:
                result = extractor.extract(path)
                merged = merged.merge(result)
            except Exception:
                logger.debug(
                    "Extractor %s failed on %s",
                    type(extractor).__name__,
                    path,
                    exc_info=True,
                )

        if merged.has_isbn:
            isbn = merged.isbn
            lookup_result = self._lookup_isbn(isbn)
            if lookup_result:
                merged = merged.merge(lookup_result)
        elif merged.title:
            author_str = ", ".join(a for a in merged.authors if a) if merged.authors else ""
            lookup_result = self._search(merged.title, author_str)
            if lookup_result:
                merged = merged.merge(lookup_result)

        return merged

    def _lookup_isbn(self, isbn: str) -> BookMetadata | None:
        for lookup in self.lookups:
            try:
                result = lookup.lookup_isbn(isbn)
                if result and result.title:
                    return result
            except Exception:
                logger.debug(
                    "Lookup %s failed for ISBN %s",
                    type(lookup).__name__,
                    isbn,
                    exc_info=True,
                )
        return None

    def _search(self, title: str, author: str) -> BookMetadata | None:
        for lookup in self.lookups:
            try:
                result = lookup.search(title, author)
                if result and result.title:
                    return result
            except Exception:
                logger.debug(
                    "Search %s failed for %s / %s",
                    type(lookup).__name__,
                    title,
                    author,
                    exc_info=True,
                )
        return None
