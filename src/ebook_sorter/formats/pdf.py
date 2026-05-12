from __future__ import annotations

from pathlib import Path

import fitz


def extract_metadata(path: Path) -> dict[str, str]:
    if not path.exists():
        raise FileNotFoundError(f"File not found: {path}")
    doc = fitz.open(str(path))
    meta = doc.metadata or {}
    doc.close()
    return {
        "title": meta.get("title", "") or "",
        "author": meta.get("author", "") or "",
        "subject": meta.get("subject", "") or "",
        "creator": meta.get("creator", "") or "",
        "producer": meta.get("producer", "") or "",
    }


def extract_text(
    path: Path,
    first_pages: int | None = None,
    last_pages: int | None = None,
) -> str:
    if not path.exists():
        raise FileNotFoundError(f"File not found: {path}")
    doc = fitz.open(str(path))
    total = len(doc)

    if first_pages is None and last_pages is None:
        page_indices = range(total)
    else:
        first_n = first_pages or 0
        last_m = last_pages or 0
        indices: list[int] = []
        indices.extend(range(min(first_n, total)))
        last_start = max(total - last_m, first_n)
        indices.extend(range(last_start, total))
        page_indices = sorted(set(indices))

    parts: list[str] = []
    for i in page_indices:
        parts.append(doc[i].get_text())
    doc.close()
    return "\n".join(parts)
