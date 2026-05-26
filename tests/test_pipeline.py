from pathlib import Path

from ebook_sorter.extractors.base import BaseExtractor
from ebook_sorter.lookup.base import BaseLookup
from ebook_sorter.models import BookMetadata
from ebook_sorter.pipeline import (
    Pipeline,
    _clean_stem,
    _significant_words,
    compute_filename_match_score,
    _FILENAME_MATCH_THRESHOLD,
    _FILENAME_CONFIRMATION_BOOST,
)


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


# ── Filename matching helpers ──────────────────────────────────────────


class TestCleanStem:
    def test_removes_isbn_in_brackets(self):
        cleaned = _clean_stem("Book Title [0387310738]")
        assert "0387310738" not in cleaned

    def test_removes_isbn_in_brackets_13(self):
        cleaned = _clean_stem("Book Title [9780387310732]")
        assert "9780387310732" not in cleaned

    def test_removes_year_in_parens(self):
        assert "2006" not in _clean_stem("Book Title (2006)")

    def test_removes_edition_markers(self):
        cleaned = _clean_stem("Book Title 2nd Edition")
        assert "2nd" not in cleaned
        assert "Book Title" in cleaned
        assert _clean_stem("Book Title 12ed") == "Book Title "

    def test_preserves_normal_words(self):
        assert "Basic" in _clean_stem("Basic College Mathematics")

    def test_removes_brackets(self):
        cleaned = _clean_stem("Author - Title [Series]")
        assert "[Series]" not in cleaned


class TestSignificantWords:
    def test_extracts_meaningful_words(self):
        words = _significant_words("Basic College Mathematics")
        assert "basic" in words
        assert "college" in words
        assert "mathematics" in words

    def test_excludes_stopwords(self):
        words = _significant_words("The Book of Life")
        assert "the" not in words
        assert "book" not in words
        assert "life" in words

    def test_skips_short_words(self):
        words = _significant_words("A to Z Guide")
        assert "a" not in words
        assert "to" not in words
        assert "z" not in words
        assert "guide" in words


class TestComputeFilenameMatchScore:
    def test_perfect_match(self):
        score = compute_filename_match_score(
            "Basic College Mathematics",
            "Basic College Mathematics",
        )
        assert score >= 0.9

    def test_partial_match(self):
        score = compute_filename_match_score(
            "Bittinger M. Basic College Mathematics 12ed 2015",
            "Basic College Mathematics",
        )
        # "basic", "college", "mathematics" are in both
        assert score >= _FILENAME_MATCH_THRESHOLD

    def test_no_match(self):
        score = compute_filename_match_score(
            "Python Machine Learning",
            "Basic College Mathematics",
        )
        assert score < _FILENAME_MATCH_THRESHOLD

    def test_ignores_isbn_in_filename(self):
        score = compute_filename_match_score(
            "Pattern Recognition and Machine Learning [0387310738]",
            "Pattern Recognition and Machine Learning",
        )
        assert score >= _FILENAME_MATCH_THRESHOLD

    def test_author_title_dash_format(self):
        score = compute_filename_match_score(
            "Christopher Bishop - Pattern Recognition and Machine Learning (2006)",
            "Pattern Recognition and Machine Learning",
        )
        assert score >= _FILENAME_MATCH_THRESHOLD

    def test_empty_title(self):
        score = compute_filename_match_score("Some File.pdf", "")
        assert score == 0.0


# ── Pipeline filename confirmation integration ─────────────────────────


class TestPipelineFilenameConfirmation:
    def test_boost_when_filename_confirms_title(self):
        """ISBN from text content, lookup succeeds, filename confirms title."""
        extractor = FakeExtractor(BookMetadata(
            isbn_13="9780765319852",
            confidence=0.6,
        ))
        lookup = FakeLookup(BookMetadata(
            title="Little Brother",
            authors=["Cory Doctorow"],
            isbn_13="9780765319852",
            confidence=0.95,
            source="openlibrary",
        ))
        pipeline = Pipeline(extractors=[extractor], lookups=[lookup])
        # Filename stem doesn't have the ISBN, but matches title
        result = pipeline.process(Path("/fake/Little Brother.pdf"))
        assert result.title == "Little Brother"
        # Confidence should be boosted above the base 0.95
        assert result.confidence >= 0.95

    def test_no_boost_when_isbn_in_filename(self):
        """ISBN is already in the filename, no extra confirmation needed."""
        extractor = FakeExtractor(BookMetadata(
            isbn_13="9780765319852",
            confidence=0.4,
        ))
        lookup = FakeLookup(BookMetadata(
            title="Little Brother",
            authors=["Cory Doctorow"],
            isbn_13="9780765319852",
            confidence=0.95,
            source="openlibrary",
        ))
        pipeline = Pipeline(extractors=[extractor], lookups=[lookup])
        # Filename contains the ISBN, so confirmation boost is skipped
        result = pipeline.process(Path("/fake/[9780765319852] Little Brother.pdf"))
        assert result.title == "Little Brother"
        # Should be exactly the lookup result confidence, no boost
        assert result.confidence == 0.95

    def test_boost_capped_at_one(self):
        """Confidence boost doesn't exceed 1.0."""
        extractor = FakeExtractor(BookMetadata(
            isbn_13="9780765319852",
            confidence=0.6,
        ))
        lookup = FakeLookup(BookMetadata(
            title="Little Brother",
            authors=["Cory Doctorow"],
            isbn_13="9780765319852",
            confidence=0.95,
            source="openlibrary",
        ))
        pipeline = Pipeline(extractors=[extractor], lookups=[lookup])
        result = pipeline.process(Path("/fake/Little Brother.pdf"))
        # 0.95 + 0.15 = 1.10 → capped to 1.0
        assert result.confidence == 1.0

    def test_no_boost_when_filename_doesnt_match(self):
        """ISBN from wrong book (false positive) — filename doesn't match title."""
        extractor = FakeExtractor(BookMetadata(
            isbn_13="9780765319852",
            confidence=0.6,
        ))
        lookup = FakeLookup(BookMetadata(
            title="Little Brother",
            authors=["Cory Doctorow"],
            isbn_13="9780765319852",
            confidence=0.95,
            source="openlibrary",
        ))
        pipeline = Pipeline(extractors=[extractor], lookups=[lookup])
        # Filename doesn't match the looked-up title at all
        result = pipeline.process(Path("/fake/Python Machine Learning.pdf"))
        assert result.title == "Little Brother"
        # Confidence stays at the base lookup confidence
        assert result.confidence == 0.95


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
