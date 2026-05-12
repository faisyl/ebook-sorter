from pathlib import Path

import fitz
import pytest
from ebooklib import epub

from ebook_sorter.extractors.embedded import EmbeddedExtractor


@pytest.fixture
def pdf_with_metadata(tmp_path: Path) -> Path:
    path = tmp_path / "book.pdf"
    doc = fitz.open()
    doc.set_metadata({"title": "PDF Title", "author": "PDF Author"})
    doc.new_page()
    doc.save(str(path))
    doc.close()
    return path


@pytest.fixture
def epub_with_metadata(tmp_path: Path) -> Path:
    path = tmp_path / "book.epub"
    book = epub.EpubBook()
    book.set_identifier("9780765319852")
    book.set_title("EPUB Title")
    book.set_language("en")
    book.add_author("EPUB Author")
    book.add_metadata("DC", "publisher", "EPUB Publisher")
    book.add_item(epub.EpubNcx())
    book.add_item(epub.EpubNav())
    book.spine = ["nav"]
    epub.write_epub(str(path), book)
    return path


@pytest.fixture
def pdf_no_metadata(tmp_path: Path) -> Path:
    path = tmp_path / "empty.pdf"
    doc = fitz.open()
    doc.new_page()
    doc.save(str(path))
    doc.close()
    return path


class TestEmbeddedExtractor:
    def setup_method(self):
        self.extractor = EmbeddedExtractor()

    def test_pdf_metadata(self, pdf_with_metadata: Path):
        meta = self.extractor.extract(pdf_with_metadata)
        assert meta.title == "PDF Title"
        assert meta.authors == ["PDF Author"]

    def test_epub_metadata(self, epub_with_metadata: Path):
        meta = self.extractor.extract(epub_with_metadata)
        assert meta.title == "EPUB Title"
        assert meta.authors == ["EPUB Author"]
        assert meta.publisher == "EPUB Publisher"

    def test_epub_isbn_from_identifier(self, epub_with_metadata: Path):
        meta = self.extractor.extract(epub_with_metadata)
        assert meta.isbn_13 == "9780765319852"

    def test_no_metadata(self, pdf_no_metadata: Path):
        meta = self.extractor.extract(pdf_no_metadata)
        assert meta.title is None
        assert meta.authors == []

    def test_source(self, pdf_with_metadata: Path):
        meta = self.extractor.extract(pdf_with_metadata)
        assert meta.source == "embedded"

    def test_unsupported_format(self, tmp_path: Path):
        path = tmp_path / "file.xyz"
        path.write_text("not an ebook")
        meta = self.extractor.extract(path)
        assert meta.title is None
