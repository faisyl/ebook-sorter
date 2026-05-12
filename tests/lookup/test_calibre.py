from unittest.mock import patch

from ebook_sorter.lookup.calibre import CalibreLookup

FETCH_OUTPUT = """Title               : Little Brother
Author(s)           : Cory Doctorow
Publisher           : Tor Books
Tags                : fiction, technology
Published           : 2008-04-29T00:00:00+00:00
ISBN                : 9780765319852
"""


class TestCalibreLookup:
    def setup_method(self):
        self.lookup = CalibreLookup()

    @patch("ebook_sorter.lookup.calibre.shutil.which", return_value=None)
    def test_unavailable(self, mock_which):
        meta = self.lookup.lookup_isbn("9780765319852")
        assert meta is None

    @patch("ebook_sorter.lookup.calibre.shutil.which", return_value="/usr/bin/fetch-ebook-metadata")
    @patch("ebook_sorter.lookup.calibre.subprocess.run")
    def test_lookup_isbn(self, mock_run, mock_which):
        mock_run.return_value.stdout = FETCH_OUTPUT
        mock_run.return_value.returncode = 0
        meta = self.lookup.lookup_isbn("9780765319852")
        assert meta is not None
        assert meta.title == "Little Brother"
        assert "Cory Doctorow" in meta.authors
        assert meta.source == "calibre"

    @patch("ebook_sorter.lookup.calibre.shutil.which", return_value="/usr/bin/fetch-ebook-metadata")
    @patch("ebook_sorter.lookup.calibre.subprocess.run")
    def test_lookup_isbn_not_found(self, mock_run, mock_which):
        mock_run.return_value.stdout = ""
        mock_run.return_value.returncode = 1
        meta = self.lookup.lookup_isbn("9780000000000")
        assert meta is None

    @patch("ebook_sorter.lookup.calibre.shutil.which", return_value="/usr/bin/fetch-ebook-metadata")
    @patch("ebook_sorter.lookup.calibre.subprocess.run")
    def test_search(self, mock_run, mock_which):
        mock_run.return_value.stdout = FETCH_OUTPUT
        mock_run.return_value.returncode = 0
        meta = self.lookup.search("Little Brother", "Cory Doctorow")
        assert meta is not None
        assert meta.title == "Little Brother"
