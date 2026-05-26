from __future__ import annotations

import logging
from pathlib import Path

from ebook_sorter.extractors.base import BaseExtractor
from ebook_sorter.isbn import isbn_10_to_13, isbn_13_to_10
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
            lookup_result = self._try_isbn_lookups(merged)
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

    def _try_isbn_lookups(self, meta: BookMetadata) -> BookMetadata | None:
        """Try all available ISBN candidates from metadata, return first match.

        Tries ISBN-13 first, then ISBN-10, then derived conversions.
        """
        candidates: list[str] = []

        if meta.isbn_13:
            candidates.append(meta.isbn_13)
        if meta.isbn_10:
            candidates.append(meta.isbn_10)
        if meta.isbn_10:
            converted = isbn_10_to_13(meta.isbn_10)
            if converted not in candidates:
                candidates.append(converted)
        if meta.isbn_13:
            # Derive ISBN-10 from ISBN-13 by dropping the 978/979 prefix and
            # recalculating the check digit. Only works for 978-prefixed ISBN-13s.
            derived_10 = isbn_13_to_10(meta.isbn_13)
            if derived_10 and derived_10 not in candidates:
                candidates.append(derived_10)

        for isbn in candidates:
            result = self._lookup_isbn(isbn)
            if result and result.title:
                logger.debug(
                    "ISBN lookup succeeded for %s (candidate from %s)",
                    isbn,
                    meta.source,
                )
                return result

        return None
