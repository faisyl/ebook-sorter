from __future__ import annotations

import json
import logging
from pathlib import Path

from ebook_sorter.models import BookMetadata

logger = logging.getLogger(__name__)

_SIDECAR_SUFFIX = ".metadata.json"

_SERIALIZED_FIELDS = (
    "title", "authors", "isbn_10", "isbn_13", "publisher",
    "year", "series", "series_index", "language", "source", "confidence",
    "author_sort",
)


def sidecar_path(ebook_path: Path) -> Path:
    return ebook_path.parent / (ebook_path.name + _SIDECAR_SUFFIX)


def write_sidecar(meta: BookMetadata, ebook_path: Path) -> Path:
    data: dict = {}
    for field in _SERIALIZED_FIELDS:
        value = getattr(meta, field)
        if value is not None and value != "" and value != []:
            data[field] = value

    path = sidecar_path(ebook_path)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n")
    logger.debug("Wrote sidecar: %s", path)
    return path


def read_sidecar(ebook_path: Path) -> BookMetadata | None:
    path = sidecar_path(ebook_path)
    if not path.exists():
        return None

    try:
        data = json.loads(path.read_text())
    except (json.JSONDecodeError, OSError):
        logger.debug("Failed to read sidecar: %s", path, exc_info=True)
        return None

    return BookMetadata(
        title=data.get("title"),
        authors=data.get("authors", []),
        isbn_10=data.get("isbn_10"),
        isbn_13=data.get("isbn_13"),
        publisher=data.get("publisher"),
        year=data.get("year"),
        series=data.get("series"),
        series_index=data.get("series_index"),
        language=data.get("language"),
        source=data.get("source", "sidecar"),
        confidence=data.get("confidence", 0.0),
        author_sort=data.get("author_sort"),
    )
