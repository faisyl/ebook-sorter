from pathlib import Path

from ebook_sorter.extractors.filename import FilenameExtractor


def make_path(name: str) -> Path:
    return Path(f"/fake/{name}")


class TestFilenameExtractor:
    def setup_method(self):
        self.extractor = FilenameExtractor()

    def test_extracts_isbn13_from_filename(self):
        path = make_path("Some Book [9780765319852].pdf")
        meta = self.extractor.extract(path)
        assert meta.isbn_13 == "9780765319852"

    def test_extracts_isbn10_from_filename(self):
        path = make_path("Some Book [0765319853].pdf")
        meta = self.extractor.extract(path)
        assert meta.isbn_10 == "0765319853"

    def test_extracts_extension(self):
        path = make_path("book.epub")
        meta = self.extractor.extract(path)
        assert meta.extension == "epub"

    def test_extracts_author_title_dash_pattern(self):
        path = make_path("Cory Doctorow - Little Brother.pdf")
        meta = self.extractor.extract(path)
        assert meta.authors == ["Cory Doctorow"]
        assert meta.title == "Little Brother"

    def test_extracts_title_only(self):
        path = make_path("Little Brother.pdf")
        meta = self.extractor.extract(path)
        assert meta.title == "Little Brother"
        assert meta.authors == []

    def test_extracts_author_title_with_year(self):
        path = make_path("Cory Doctorow - Little Brother (2008).pdf")
        meta = self.extractor.extract(path)
        assert meta.authors == ["Cory Doctorow"]
        assert meta.title == "Little Brother"
        assert meta.year == 2008

    def test_extracts_series_in_brackets(self):
        path = make_path("Author - [Series #1] - Title.epub")
        meta = self.extractor.extract(path)
        assert meta.series == "Series"
        assert meta.series_index == 1.0
        assert meta.title == "Title"

    def test_source_is_filename(self):
        path = make_path("book.pdf")
        meta = self.extractor.extract(path)
        assert meta.source == "filename"

    def test_confidence(self):
        path = make_path("Author - Title.pdf")
        meta = self.extractor.extract(path)
        assert meta.confidence == 0.4
