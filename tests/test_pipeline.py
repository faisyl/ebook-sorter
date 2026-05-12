from pathlib import Path

from ebook_sorter.extractors.base import BaseExtractor
from ebook_sorter.lookup.base import BaseLookup
from ebook_sorter.models import BookMetadata
from ebook_sorter.pipeline import Pipeline


class FakeExtractor(BaseExtractor):
    def __init__(self, result: BookMetadata):
        self._result = result

    def extract(self, path: Path) -> BookMetadata:
        return self._result


class FakeLookup(BaseLookup):
    def __init__(self, result: BookMetadata | None = None):
        self._result = result

    def lookup_isbn(self, isbn: str) -> BookMetadata | None:
        return self._result

    def search(self, title: str, author: str = "") -> BookMetadata | None:
        return self._result


def test_pipeline_isbn_found_and_looked_up():
    extractor = FakeExtractor(BookMetadata(isbn_13="9780765319852", confidence=0.5))
    lookup = FakeLookup(BookMetadata(
        title="Little Brother",
        authors=["Cory Doctorow"],
        isbn_13="9780765319852",
        confidence=0.95,
        source="openlibrary",
    ))
    pipeline = Pipeline(extractors=[extractor], lookups=[lookup])
    result = pipeline.process(Path("/fake/book.pdf"))
    assert result.title == "Little Brother"
    assert result.isbn_13 == "9780765319852"
    assert result.confidence == 0.95


def test_pipeline_no_isbn_searches_by_title():
    extractor = FakeExtractor(BookMetadata(
        title="Little Brother",
        authors=["Cory Doctorow"],
        confidence=0.4,
    ))
    lookup = FakeLookup(BookMetadata(
        title="Little Brother",
        authors=["Cory Doctorow"],
        isbn_13="9780765319852",
        confidence=0.7,
        source="openlibrary",
    ))
    pipeline = Pipeline(extractors=[extractor], lookups=[lookup])
    result = pipeline.process(Path("/fake/book.pdf"))
    assert result.isbn_13 == "9780765319852"
    assert result.confidence == 0.7


def test_pipeline_merges_extractor_results():
    ext1 = FakeExtractor(BookMetadata(title="Little Brother", confidence=0.3))
    ext2 = FakeExtractor(BookMetadata(authors=["Cory Doctorow"], confidence=0.4))
    pipeline = Pipeline(extractors=[ext1, ext2], lookups=[])
    result = pipeline.process(Path("/fake/book.pdf"))
    assert result.title == "Little Brother"
    assert result.authors == ["Cory Doctorow"]


def test_pipeline_no_results():
    extractor = FakeExtractor(BookMetadata())
    pipeline = Pipeline(extractors=[extractor], lookups=[])
    result = pipeline.process(Path("/fake/book.pdf"))
    assert result.title is None
    assert result.confidence == 0.0


def test_pipeline_lookup_fallback():
    extractor = FakeExtractor(BookMetadata(isbn_13="9780765319852"))
    lookup1 = FakeLookup(None)
    lookup2 = FakeLookup(BookMetadata(
        title="Little Brother",
        isbn_13="9780765319852",
        confidence=0.95,
    ))
    pipeline = Pipeline(extractors=[extractor], lookups=[lookup1, lookup2])
    result = pipeline.process(Path("/fake/book.pdf"))
    assert result.title == "Little Brother"


def test_pipeline_stops_lookup_on_first_hit():
    extractor = FakeExtractor(BookMetadata(isbn_13="9780765319852"))
    lookup1 = FakeLookup(BookMetadata(title="First Result", confidence=0.95))
    lookup2 = FakeLookup(BookMetadata(title="Second Result", confidence=0.95))
    pipeline = Pipeline(extractors=[extractor], lookups=[lookup1, lookup2])
    result = pipeline.process(Path("/fake/book.pdf"))
    assert result.title == "First Result"
