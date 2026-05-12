from pathlib import Path

import fitz
import pytest
from ebooklib import epub

from ebook_sorter.extractors.embedded import EmbeddedExtractor
from ebook_sorter.extractors.filename import FilenameExtractor
from ebook_sorter.extractors.text_content import TextContentExtractor
from ebook_sorter.organizer import Organizer
from ebook_sorter.pipeline import Pipeline


@pytest.fixture
def sample_library(tmp_path: Path) -> Path:
    lib = tmp_path / "library"
    lib.mkdir()

    doc = fitz.open()
    doc.set_metadata({"title": "Integration Test Book", "author": "Test Author"})
    page = doc.new_page()
    page.insert_text(fitz.Point(72, 72), "Some content on page 1")
    doc.save(str(lib / "messy_filename.pdf"))
    doc.close()

    book = epub.EpubBook()
    book.set_identifier("test-id")
    book.set_title("EPUB Integration Book")
    book.set_language("en")
    book.add_author("EPUB Writer")
    ch = epub.EpubHtml(title="Ch1", file_name="ch1.xhtml", lang="en")
    ch.content = b"<html><body><p>Hello world</p></body></html>"
    book.add_item(ch)
    book.add_item(epub.EpubNcx())
    book.add_item(epub.EpubNav())
    book.spine = ["nav", ch]
    epub.write_epub(str(lib / "another_book.epub"), book)

    return lib


def test_full_pipeline_extracts_metadata(sample_library: Path):
    pipeline = Pipeline(
        extractors=[
            FilenameExtractor(),
            EmbeddedExtractor(),
            TextContentExtractor(),
        ],
        lookups=[],
    )
    pdf = sample_library / "messy_filename.pdf"
    meta = pipeline.process(pdf)
    assert meta.title == "Integration Test Book"
    assert "Test Author" in meta.authors


def test_full_pipeline_epub(sample_library: Path):
    pipeline = Pipeline(
        extractors=[
            FilenameExtractor(),
            EmbeddedExtractor(),
            TextContentExtractor(),
        ],
        lookups=[],
    )
    ep = sample_library / "another_book.epub"
    meta = pipeline.process(ep)
    assert meta.title == "EPUB Integration Book"
    assert "EPUB Writer" in meta.authors


def test_organize_end_to_end(sample_library: Path, tmp_path: Path):
    output = tmp_path / "output"
    output.mkdir()

    pipeline = Pipeline(
        extractors=[
            FilenameExtractor(),
            EmbeddedExtractor(),
            TextContentExtractor(),
        ],
        lookups=[],
    )
    organizer = Organizer(
        output_dir=output,
        filename_template="{authors} - {title}.{ext}",
        folder_template="",
    )

    pdf = sample_library / "messy_filename.pdf"
    meta = pipeline.process(pdf)
    meta.original_path = pdf
    dest = organizer.move_file(meta)

    assert dest.exists()
    assert "Test Author" in dest.name
    assert "Integration Test Book" in dest.name
    assert not pdf.exists()
