from __future__ import annotations

import logging
import re
from pathlib import Path

from ebook_sorter.extractors.base import BaseExtractor
from ebook_sorter.isbn import find_isbns, isbn_10_to_13, isbn_13_to_10
from ebook_sorter.lookup.base import BaseLookup
from ebook_sorter.models import BookMetadata

logger = logging.getLogger(__name__)

# Words too common in filenames to be meaningful for matching
_FILENAME_STOPWORDS: set[str] = {
    "the", "a", "an", "and", "or", "of", "in", "to", "for", "with",
    "on", "at", "by", "is", "it", "its", "book", "ebook", "pdf",
    "epub", "mobi", "azw", "azw3", "djvu", "ed", "edition",
    "vol", "volume", "part", "series", "new",
}

# Threshold for a meaningful filename-to-title match
_FILENAME_MATCH_THRESHOLD = 0.3
# Confidence boost when filename confirms the looked-up title
_FILENAME_CONFIRMATION_BOOST = 0.15

# Matches a series name with a trailing volume/book number, e.g. "The Expanse 1" or "Dune 2.5"
_SERIES_TRAILING_NUM_RE = re.compile(r"^(.*?)\s+(\d+(?:\.\d+)?)\s*$")


def _clean_stem(stem: str) -> str:
    """Remove ISBNs, years, edition markers, and brackets from a filename stem."""
    # Remove bracket contents that look like ISBNs
    cleaned = stem
    # Remove [ISBN], [978...], [0-9X{10,13}] patterns
    cleaned = re.sub(r"\[[\dXx\-]{9,17}\]", "", cleaned)
    cleaned = re.sub(r"\(\d{4}\)", "", cleaned)  # (2006)
    cleaned = re.sub(r"\b\d{4}\b", "", cleaned)  # standalone 4-digit years
    cleaned = re.sub(r"\d+(?:st|nd|rd|th)?\s*ed\w*", "", cleaned, flags=re.IGNORECASE)  # 2nd ed, 12ed
    cleaned = re.sub(r"[\[\](){}]", " ", cleaned)
    return cleaned


def _significant_words(text: str) -> set[str]:
    """Extract meaningful lowercase words of 3+ chars, excluding stopwords."""
    words = re.findall(r"[a-zA-Z]{3,}", text.lower())
    return {w for w in words if w not in _FILENAME_STOPWORDS}


def compute_filename_match_score(stem: str, title: str) -> float:
    """Return 0.0-1.0 overlap between the filename stem and the looked-up title.

    Uses Jaccard similarity on significant words after cleaning both strings.
    """
    clean_stem = _clean_stem(stem)
    stem_words = _significant_words(clean_stem)
    title_words = _significant_words(title)

    if not stem_words or not title_words:
        return 0.0

    intersection = stem_words & title_words
    union = stem_words | title_words
    return len(intersection) / len(union)


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
                # Filename confirmation: if ISBN came from text/embedded (not filename),
                # verify the looked-up title against the filename to catch false positives.
                filename_isbns = find_isbns(path.stem)
                isbn_from_filename = (
                    (merged.isbn_13 and merged.isbn_13 in filename_isbns)
                    or (merged.isbn_10 and merged.isbn_10 in filename_isbns)
                )
                if not isbn_from_filename and lookup_result.title:
                    match_score = compute_filename_match_score(path.stem, lookup_result.title)
                    if match_score >= _FILENAME_MATCH_THRESHOLD:
                        logger.debug(
                            "Filename confirms title: %r vs %r (score=%.2f), boosting confidence",
                            path.stem,
                            lookup_result.title,
                            match_score,
                        )
                        lookup_result.confidence = min(
                            lookup_result.confidence + _FILENAME_CONFIRMATION_BOOST,
                            1.0,
                        )
                    else:
                        logger.debug(
                            "Filename does NOT confirm title: %r vs %r (score=%.2f)",
                            path.stem,
                            lookup_result.title,
                            match_score,
                        )
                merged = merged.merge(lookup_result)
        elif merged.title:
            author_str = ", ".join(a for a in merged.authors if a) if merged.authors else ""
            lookup_result = self._search(merged.title, author_str)
            if lookup_result:
                merged = merged.merge(lookup_result)

        if merged.series and merged.series_index is None:
            m = _SERIES_TRAILING_NUM_RE.match(merged.series)
            if m and m.group(1).strip():
                merged.series = m.group(1).strip()
                merged.series_index = float(m.group(2))

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
