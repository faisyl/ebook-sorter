from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path


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

    @property
    def isbn(self) -> str | None:
        return self.isbn_13 or self.isbn_10

    @property
    def has_isbn(self) -> bool:
        return self.isbn_10 is not None or self.isbn_13 is not None

    def merge(self, other: BookMetadata) -> BookMetadata:
        return BookMetadata(
            title=self.title or other.title,
            authors=self.authors or other.authors,
            isbn_10=self.isbn_10 or other.isbn_10,
            isbn_13=self.isbn_13 or other.isbn_13,
            publisher=self.publisher or other.publisher,
            year=self.year or other.year,
            series=self.series or other.series,
            series_index=self.series_index if self.series_index is not None else other.series_index,
            language=self.language or other.language,
            source=self.source or other.source,
            confidence=max(self.confidence, other.confidence),
            original_path=self.original_path or other.original_path,
            extension=self.extension or other.extension,
        )

    def template_dict(self) -> dict[str, str]:
        si = self.series_index
        if si is not None:
            series_index_str = str(int(si)) if si == int(si) else str(si)
        else:
            series_index_str = ""

        return {
            "title": self.title or "",
            "authors": ", ".join(self.authors) if self.authors else "",
            "isbn": self.isbn or "",
            "isbn10": self.isbn_10 or "",
            "isbn13": self.isbn_13 or "",
            "publisher": self.publisher or "",
            "year": str(self.year) if self.year else "",
            "series": self.series or "",
            "series_index": series_index_str,
            "language": self.language or "",
            "ext": self.extension,
        }
