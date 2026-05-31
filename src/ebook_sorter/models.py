from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path


def _derive_author_sort(name: str) -> str:
    """Convert 'First Last' to 'Last, First'. Already-inverted names are returned as-is."""
    if not name:
        return name
    if "," in name:
        return name
    parts = name.rsplit(" ", 1)
    if len(parts) == 1:
        return name
    return f"{parts[1]}, {parts[0]}"


@dataclass
class BookMetadata:
    title: str | None = None
    authors: list[str] = field(default_factory=list)
    isbn_10: str | None = None
    isbn_13: str | None = None
    publisher: str | None = None
    year: int | None = None
    series: str | None = None
    series_index: float | None = None
    language: str | None = None
    source: str = ""
    confidence: float = 0.0
    original_path: Path | None = None
    extension: str = ""
    author_sort: str | None = None

    @property
    def isbn(self) -> str | None:
        return self.isbn_13 or self.isbn_10

    @property
    def has_isbn(self) -> bool:
        return self.isbn_10 is not None or self.isbn_13 is not None

    def merge(self, other: BookMetadata) -> BookMetadata:
        prefer_other = other.confidence > self.confidence

        def pick(self_val: object, other_val: object) -> object:
            if self_val and other_val:
                return other_val if prefer_other else self_val
            return self_val or other_val

        return BookMetadata(
            title=pick(self.title, other.title),
            authors=pick(self.authors, other.authors),
            isbn_10=self.isbn_10 or other.isbn_10,
            isbn_13=self.isbn_13 or other.isbn_13,
            publisher=pick(self.publisher, other.publisher),
            year=pick(self.year, other.year),
            series=self.series or other.series,
            series_index=self.series_index if self.series_index is not None else other.series_index,
            language=self.language or other.language,
            source=pick(self.source, other.source),
            confidence=max(self.confidence, other.confidence),
            original_path=self.original_path or other.original_path,
            extension=self.extension or other.extension,
            author_sort=self.author_sort or other.author_sort,
        )

    def template_dict(self) -> dict[str, str]:
        si = self.series_index
        if si is not None:
            series_index_str = str(int(si)) if si == int(si) else str(si)
            series_index_padded = f"{int(si):02d}" if si == int(si) else series_index_str
        else:
            series_index_str = ""
            series_index_padded = ""

        if self.author_sort:
            author_sort_str = self.author_sort
        elif self.authors:
            author_sort_str = _derive_author_sort(next((a for a in self.authors if a), ""))
        else:
            author_sort_str = ""

        return {
            "title": self.title or "",
            "authors": ", ".join(a for a in self.authors if a) if self.authors else "",
            "isbn": self.isbn or "",
            "isbn10": self.isbn_10 or "",
            "isbn13": self.isbn_13 or "",
            "publisher": self.publisher or "",
            "year": str(self.year) if self.year else "",
            "series": self.series or "",
            "series_index": series_index_str,
            "series_index_padded": series_index_padded,
            "language": self.language or "",
            "ext": self.extension,
            "author_sort": author_sort_str,
        }
