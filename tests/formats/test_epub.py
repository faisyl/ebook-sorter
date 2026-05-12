from pathlib import Path

import pytest
from ebooklib import epub

from ebook_sorter.formats.epub import extract_metadata, extract_text


@pytest.fixture
def sample_epub(tmp_path: Path) -> Path:
    path = tmp_path / "test.epub"
    book = epub.EpubBook()
    book.set_identifier("9780765319852")
    book.set_title("Test EPUB Book")
    book.set_language("en")
    book.add_author("Test Author")
    book.add_metadata("DC", "publisher", "Test Publisher")

    ch1 = epub.EpubHtml(title="Chapter 1", file_name="ch1.xhtml", lang="en")
    ch1.content = b"<html><body><p>Chapter 1 text content.</p></body></html>"
    book.add_item(ch1)

    ch2 = epub.EpubHtml(title="Chapter 2", file_name="ch2.xhtml", lang="en")
    ch2.content = b"<html><body><p>Chapter 2 text content.</p></body></html>"
    book.add_item(ch2)

    book.add_item(epub.EpubNcx())
    book.add_item(epub.EpubNav())
    book.spine = ["nav", ch1, ch2]
    epub.write_epub(str(path), book)
    return path


def test_extract_metadata(sample_epub: Path):
    meta = extract_metadata(sample_epub)
    assert meta["title"] == "Test EPUB Book"
    assert "Test Author" in meta["authors"]
    assert "9780765319852" in meta["identifiers"]


def test_extract_metadata_has_publisher(sample_epub: Path):
    meta = extract_metadata(sample_epub)
    assert meta["publisher"] == "Test Publisher"


def test_extract_text(sample_epub: Path):
    text = extract_text(sample_epub)
    assert "Chapter 1 text content" in text
    assert "Chapter 2 text content" in text


def test_extract_text_nonexistent():
    with pytest.raises(FileNotFoundError):
        extract_text(Path("/nonexistent/file.epub"))
