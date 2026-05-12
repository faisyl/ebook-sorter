import httpx
import respx

from ebook_sorter.lookup.openlibrary import OpenLibraryLookup

ISBN_RESPONSE = {
    "ISBN:9780765319852": {
        "title": "Little Brother",
        "authors": [{"name": "Cory Doctorow"}],
        "publishers": [{"name": "Tor Books"}],
        "publish_date": "2008",
        "number_of_pages": 382,
    }
}

SEARCH_RESPONSE = {
    "docs": [
        {
            "title": "Little Brother",
            "author_name": ["Cory Doctorow"],
            "publisher": ["Tor Books"],
            "first_publish_year": 2008,
            "isbn": ["9780765319852"],
        }
    ]
}


class TestOpenLibraryLookup:
    def setup_method(self):
        self.lookup = OpenLibraryLookup()

    @respx.mock
    def test_lookup_isbn_found(self):
        respx.get("https://openlibrary.org/api/books").mock(
            return_value=httpx.Response(200, json=ISBN_RESPONSE)
        )
        meta = self.lookup.lookup_isbn("9780765319852")
        assert meta is not None
        assert meta.title == "Little Brother"
        assert "Cory Doctorow" in meta.authors
        assert meta.publisher == "Tor Books"

    @respx.mock
    def test_lookup_isbn_not_found(self):
        respx.get("https://openlibrary.org/api/books").mock(
            return_value=httpx.Response(200, json={})
        )
        meta = self.lookup.lookup_isbn("9780000000000")
        assert meta is None

    @respx.mock
    def test_search_found(self):
        respx.get("https://openlibrary.org/search.json").mock(
            return_value=httpx.Response(200, json=SEARCH_RESPONSE)
        )
        meta = self.lookup.search("Little Brother", "Cory Doctorow")
        assert meta is not None
        assert meta.title == "Little Brother"

    @respx.mock
    def test_search_not_found(self):
        respx.get("https://openlibrary.org/search.json").mock(
            return_value=httpx.Response(200, json={"docs": []})
        )
        meta = self.lookup.search("Nonexistent Book")
        assert meta is None

    @respx.mock
    def test_lookup_isbn_confidence(self):
        respx.get("https://openlibrary.org/api/books").mock(
            return_value=httpx.Response(200, json=ISBN_RESPONSE)
        )
        meta = self.lookup.lookup_isbn("9780765319852")
        assert meta is not None
        assert meta.confidence == 0.95
        assert meta.source == "openlibrary"
