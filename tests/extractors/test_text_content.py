from pathlib import Path

import fitz
import pytest

from ebook_sorter.extractors.text_content import TextContentExtractor


@pytest.fixture
def pdf_with_isbn(tmp_path: Path) -> Path:
    path = tmp_path / "book.pdf"
    doc = fitz.open()
    page = doc.new_page()
    page.insert_text(fitz.Point(72, 72), "ISBN 978-0-7653-1985-2")
    for i in range(4):
        p = doc.new_page()
        p.insert_text(fitz.Point(72, 72), f"Page {i + 2} content")
    doc.save(str(path))
    doc.close()
    return path


@pytest.fixture
def pdf_without_isbn(tmp_path: Path) -> Path:
    path = tmp_path / "no_isbn.pdf"
    doc = fitz.open()
    page = doc.new_page()
    page.insert_text(fitz.Point(72, 72), "Just some regular text")
    doc.save(str(path))
    doc.close()
    return path


class TestTextContentExtractor:
    def setup_method(self):
        self.extractor = TextContentExtractor()

    def test_finds_isbn_in_pdf(self, pdf_with_isbn: Path):
        meta = self.extractor.extract(pdf_with_isbn)
        assert meta.isbn_13 == "9780765319852"

    def test_no_isbn_found(self, pdf_without_isbn: Path):
        meta = self.extractor.extract(pdf_without_isbn)
        assert meta.has_isbn is False

    def test_source(self, pdf_with_isbn: Path):
        meta = self.extractor.extract(pdf_with_isbn)
        assert meta.source == "text_content"

    def test_confidence_with_isbn(self, pdf_with_isbn: Path):
        meta = self.extractor.extract(pdf_with_isbn)
        assert meta.confidence > 0.0

    def test_unsupported_format(self, tmp_path: Path):
        path = tmp_path / "file.xyz"
        path.write_text("some text with ISBN 9780765319852")
        meta = self.extractor.extract(path)
        assert meta.has_isbn is False
