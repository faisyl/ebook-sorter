from pathlib import Path

from ebook_sorter.models import BookMetadata


def test_book_metadata_defaults():
    meta = BookMetadata()
    assert meta.title is None
    assert meta.authors == []
    assert meta.isbn_10 is None
    assert meta.isbn_13 is None
    assert meta.confidence == 0.0


def test_isbn_property_prefers_isbn13():
    meta = BookMetadata(isbn_10="0765319853", isbn_13="9780765319852")
    assert meta.isbn == "9780765319852"


def test_isbn_property_falls_back_to_isbn10():
    meta = BookMetadata(isbn_10="0765319853")
    assert meta.isbn == "0765319853"


def test_isbn_property_none_when_missing():
    meta = BookMetadata()
    assert meta.isbn is None


def test_has_isbn():
    assert BookMetadata(isbn_13="9780765319852").has_isbn is True
    assert BookMetadata(isbn_10="0765319853").has_isbn is True
    assert BookMetadata().has_isbn is False


def test_merge_fills_missing_fields():
    base = BookMetadata(title="Little Brother", isbn_13="9780765319852")
    other = BookMetadata(
        authors=["Cory Doctorow"],
        year=2008,
        publisher="Tor Books",
        confidence=0.9,
    )
    merged = base.merge(other)
    assert merged.title == "Little Brother"
    assert merged.authors == ["Cory Doctorow"]
    assert merged.isbn_13 == "9780765319852"
    assert merged.year == 2008
    assert merged.publisher == "Tor Books"
    assert merged.confidence == 0.9


def test_merge_keeps_existing_fields():
    base = BookMetadata(title="Little Brother", authors=["Cory Doctorow"])
    other = BookMetadata(title="Wrong Title", authors=["Wrong Author"])
    merged = base.merge(other)
    assert merged.title == "Little Brother"
    assert merged.authors == ["Cory Doctorow"]


def test_merge_higher_confidence_overrides():
    base = BookMetadata(title="filename_title", authors=["filename"], confidence=0.4)
    other = BookMetadata(title="Real Title", authors=["Real Author"], confidence=0.6)
    merged = base.merge(other)
    assert merged.title == "Real Title"
    assert merged.authors == ["Real Author"]


def test_merge_takes_max_confidence():
    base = BookMetadata(confidence=0.4)
    other = BookMetadata(confidence=0.9)
    assert base.merge(other).confidence == 0.9
    assert other.merge(base).confidence == 0.9


def test_template_dict():
    meta = BookMetadata(
        title="Little Brother",
        authors=["Cory Doctorow"],
        isbn_13="9780765319852",
        year=2008,
        series="Little Brother",
        series_index=1,
        extension="pdf",
    )
    d = meta.template_dict()
    assert d["title"] == "Little Brother"
    assert d["authors"] == "Cory Doctorow"
    assert d["isbn"] == "9780765319852"
    assert d["isbn13"] == "9780765319852"
    assert d["year"] == "2008"
    assert d["series"] == "Little Brother"
    assert d["series_index"] == "1"
    assert d["ext"] == "pdf"


def test_template_dict_multiple_authors():
    meta = BookMetadata(authors=["Author A", "Author B"])
    d = meta.template_dict()
    assert d["authors"] == "Author A, Author B"


def test_template_dict_missing_fields_are_empty():
    meta = BookMetadata()
    d = meta.template_dict()
    assert d["title"] == ""
    assert d["authors"] == ""
    assert d["year"] == ""
    assert d["isbn"] == ""
