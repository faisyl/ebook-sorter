from pathlib import Path

import fitz
import pytest

from ebook_sorter.formats.pdf import extract_metadata, extract_text


@pytest.fixture
def sample_pdf(tmp_path: Path) -> Path:
    path = tmp_path / "test.pdf"
    doc = fitz.open()
    doc.set_metadata({
        "title": "Test Book",
        "author": "Test Author",
        "subject": "Testing",
    })
    for i in range(5):
        page = doc.new_page()
        text_point = fitz.Point(72, 72)
        page.insert_text(text_point, f"Page {i + 1} content. ISBN 978-0-7653-1985-2")
    doc.save(str(path))
    doc.close()
    return path


@pytest.fixture
def empty_pdf(tmp_path: Path) -> Path:
    path = tmp_path / "empty.pdf"
    doc = fitz.open()
    doc.new_page()
    doc.save(str(path))
    doc.close()
    return path


def test_extract_metadata(sample_pdf: Path):
    meta = extract_metadata(sample_pdf)
    assert meta["title"] == "Test Book"
    assert meta["author"] == "Test Author"


def test_extract_metadata_empty(empty_pdf: Path):
    meta = extract_metadata(empty_pdf)
    assert meta["title"] == ""


def test_extract_text(sample_pdf: Path):
    text = extract_text(sample_pdf)
    assert "Page 1 content" in text
    assert "ISBN" in text


def test_extract_text_first_last_pages(sample_pdf: Path):
    text = extract_text(sample_pdf, first_pages=2, last_pages=1)
    assert "Page 1 content" in text
    assert "Page 2 content" in text
    assert "Page 5 content" in text


def test_extract_text_empty(empty_pdf: Path):
    text = extract_text(empty_pdf)
    assert text.strip() == ""


def test_extract_text_nonexistent():
    with pytest.raises(FileNotFoundError):
        extract_text(Path("/nonexistent/file.pdf"))
