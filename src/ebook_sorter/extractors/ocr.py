from __future__ import annotations

import logging
import shutil
import subprocess
import tempfile
from pathlib import Path

import fitz

from ebook_sorter.extractors.base import BaseExtractor
from ebook_sorter.isbn import find_isbns, is_valid_isbn_13
from ebook_sorter.models import BookMetadata

logger = logging.getLogger(__name__)


class OcrExtractor(BaseExtractor):
    def __init__(self, first_pages: int = 7, last_pages: int = 3) -> None:
        self.first_pages = first_pages
        self.last_pages = last_pages

    def extract(self, path: Path) -> BookMetadata:
        ext = path.suffix.lower()
        if ext not in (".pdf", ".djvu") or not shutil.which("tesseract"):
            return BookMetadata(
                extension=ext.lstrip("."),
                source="ocr",
                original_path=path,
            )

        text = ""
        try:
            if ext == ".pdf":
                text = self._ocr_pdf(path)
        except Exception:
            logger.debug("OCR failed for %s", path, exc_info=True)

        isbns = find_isbns(text)
        isbn_10 = None
        isbn_13 = None
        for isbn in isbns:
            if len(isbn) == 13 and is_valid_isbn_13(isbn):
                isbn_13 = isbn
            elif len(isbn) == 10:
                isbn_10 = isbn

        return BookMetadata(
            isbn_10=isbn_10,
            isbn_13=isbn_13,
            extension=ext.lstrip("."),
            source="ocr",
            confidence=0.4 if (isbn_10 or isbn_13) else 0.0,
            original_path=path,
        )

    def _ocr_pdf(self, path: Path) -> str:
        doc = fitz.open(str(path))
        total = len(doc)
        indices: list[int] = []
        indices.extend(range(min(self.first_pages, total)))
        last_start = max(total - self.last_pages, self.first_pages)
        indices.extend(range(last_start, total))
        page_indices = sorted(set(indices))

        parts: list[str] = []
        for i in page_indices:
            page = doc[i]
            pix = page.get_pixmap(dpi=300)
            with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as f:
                img_path = Path(f.name)
                pix.save(str(img_path))
            try:
                result = subprocess.run(
                    ["tesseract", str(img_path), "stdout"],
                    capture_output=True,
                    text=True,
                    timeout=60,
                )
                parts.append(result.stdout)
            except subprocess.TimeoutExpired:
                pass
            finally:
                img_path.unlink(missing_ok=True)
        doc.close()
        return "\n".join(parts)
