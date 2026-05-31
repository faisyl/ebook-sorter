import json
from pathlib import Path

import pytest

from ebook_sorter.models import BookMetadata
from ebook_sorter.sidecar import read_sidecar, sidecar_path, write_sidecar


class TestSidecarPath:
    def test_pdf(self):
        assert sidecar_path(Path("/books/test.pdf")) == Path("/books/test.pdf.metadata.json")

    def test_epub(self):
        assert sidecar_path(Path("book.epub")) == Path("book.epub.metadata.json")


class TestWriteSidecar:
    def test_writes_json(self, tmp_path: Path):
        ebook = tmp_path / "book.pdf"
        ebook.write_text("fake")
        meta = BookMetadata(
            title="Little Brother",
            authors=["Cory Doctorow"],
            isbn_13="9780765319852",
            year=2008,
            publisher="Tor Books",
            source="openlibrary",
            confidence=0.95,
        )
        result = write_sidecar(meta, ebook)
        assert result.exists()
        assert result.name == "book.pdf.metadata.json"

        data = json.loads(result.read_text())
        assert data["title"] == "Little Brother"
        assert data["authors"] == ["Cory Doctorow"]
        assert data["isbn_13"] == "9780765319852"
        assert data["year"] == 2008
        assert data["confidence"] == 0.95

    def test_omits_none_fields(self, tmp_path: Path):
        ebook = tmp_path / "book.pdf"
        ebook.write_text("fake")
        meta = BookMetadata(title="Test", confidence=0.5)
        result = write_sidecar(meta, ebook)
        data = json.loads(result.read_text())
        assert "isbn_10" not in data
        assert "isbn_13" not in data
        assert "publisher" not in data
        assert "year" not in data

    def test_does_not_include_original_path(self, tmp_path: Path):
        ebook = tmp_path / "book.pdf"
        ebook.write_text("fake")
        meta = BookMetadata(title="Test", original_path=ebook, extension="pdf")
        result = write_sidecar(meta, ebook)
        data = json.loads(result.read_text())
        assert "original_path" not in data
        assert "extension" not in data


class TestReadSidecar:
    def test_reads_existing(self, tmp_path: Path):
        ebook = tmp_path / "book.pdf"
        ebook.write_text("fake")
        meta = BookMetadata(
            title="Little Brother",
            authors=["Cory Doctorow"],
            isbn_13="9780765319852",
            year=2008,
            confidence=0.95,
            source="openlibrary",
        )
        write_sidecar(meta, ebook)

        loaded = read_sidecar(ebook)
        assert loaded is not None
        assert loaded.title == "Little Brother"
        assert loaded.authors == ["Cory Doctorow"]
        assert loaded.isbn_13 == "9780765319852"
        assert loaded.year == 2008
        assert loaded.confidence == 0.95

    def test_returns_none_when_missing(self, tmp_path: Path):
        ebook = tmp_path / "book.pdf"
        assert read_sidecar(ebook) is None

    def test_returns_none_on_invalid_json(self, tmp_path: Path):
        ebook = tmp_path / "book.pdf"
        ebook.write_text("fake")
        sc = tmp_path / "book.pdf.metadata.json"
        sc.write_text("not valid json{{{")
        assert read_sidecar(ebook) is None

    def test_round_trip_with_series(self, tmp_path: Path):
        ebook = tmp_path / "book.epub"
        ebook.write_text("fake")
        meta = BookMetadata(
            title="Homeland",
            authors=["Cory Doctorow"],
            series="Little Brother",
            series_index=2,
            language="en",
            confidence=0.85,
        )
        write_sidecar(meta, ebook)
        loaded = read_sidecar(ebook)
        assert loaded is not None
        assert loaded.series == "Little Brother"
        assert loaded.series_index == 2.0
        assert loaded.language == "en"

    def test_round_trip_with_author_sort(self, tmp_path: Path):
        ebook = tmp_path / "book.epub"
        ebook.write_text("fake")
        meta = BookMetadata(
            title="Leviathan Wakes",
            authors=["James S.A. Corey"],
            author_sort="Corey, James S.A.",
            series="The Expanse",
            series_index=1,
            confidence=0.9,
        )
        write_sidecar(meta, ebook)
        loaded = read_sidecar(ebook)
        assert loaded is not None
        assert loaded.author_sort == "Corey, James S.A."

    def test_round_trip_author_sort_none_is_omitted(self, tmp_path: Path):
        ebook = tmp_path / "book.epub"
        ebook.write_text("fake")
        meta = BookMetadata(title="Test", authors=["Author"], confidence=0.8)
        write_sidecar(meta, ebook)
        import json
        data = json.loads((tmp_path / "book.epub.metadata.json").read_text())
        assert "author_sort" not in data  # not written when None

    def test_old_sidecar_without_author_sort_reads_as_none(self, tmp_path: Path):
        ebook = tmp_path / "book.epub"
        ebook.write_text("fake")
        import json
        (tmp_path / "book.epub.metadata.json").write_text(
            json.dumps({"title": "Old Book", "authors": ["Author"], "confidence": 0.8})
        )
        loaded = read_sidecar(ebook)
        assert loaded is not None
        assert loaded.author_sort is None
