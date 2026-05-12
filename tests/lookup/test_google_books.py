import httpx
import respx

from ebook_sorter.lookup.google_books import GoogleBooksLookup

VOLUME_RESPONSE = {
    "totalItems": 1,
    "items": [
        {
            "volumeInfo": {
                "title": "Little Brother",
                "authors": ["Cory Doctorow"],
                "publisher": "Tor Books",
                "publishedDate": "2008-04-29",
                "industryIdentifiers": [
                    {"type": "ISBN_13", "identifier": "9780765319852"},
                    {"type": "ISBN_10", "identifier": "0765319853"},
                ],
                "language": "en",
            }
        }
    ],
}


class TestGoogleBooksLookup:
    def setup_method(self):
        self.lookup = GoogleBooksLookup()

    @respx.mock
    def test_lookup_isbn(self):
        respx.get("https://www.googleapis.com/books/v1/volumes").mock(
            return_value=httpx.Response(200, json=VOLUME_RESPONSE)
        )
        meta = self.lookup.lookup_isbn("9780765319852")
        assert meta is not None
        assert meta.title == "Little Brother"
        assert "Cory Doctorow" in meta.authors
        assert meta.isbn_13 == "9780765319852"
        assert meta.confidence == 0.95

    @respx.mock
    def test_lookup_isbn_not_found(self):
        respx.get("https://www.googleapis.com/books/v1/volumes").mock(
            return_value=httpx.Response(200, json={"totalItems": 0})
        )
        meta = self.lookup.lookup_isbn("9780000000000")
        assert meta is None

    @respx.mock
    def test_search(self):
        respx.get("https://www.googleapis.com/books/v1/volumes").mock(
            return_value=httpx.Response(200, json=VOLUME_RESPONSE)
        )
        meta = self.lookup.search("Little Brother", "Cory Doctorow")
        assert meta is not None
        assert meta.title == "Little Brother"
        assert meta.source == "google_books"

    @respx.mock
    def test_search_not_found(self):
        respx.get("https://www.googleapis.com/books/v1/volumes").mock(
            return_value=httpx.Response(200, json={"totalItems": 0})
        )
        meta = self.lookup.search("Nonexistent Book")
        assert meta is None
