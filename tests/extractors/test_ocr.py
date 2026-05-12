from pathlib import Path
from unittest.mock import patch

from ebook_sorter.extractors.ocr import OcrExtractor


class TestOcrExtractor:
    def setup_method(self):
        self.extractor = OcrExtractor()

    @patch("ebook_sorter.extractors.ocr.shutil.which", return_value=None)
    def test_returns_empty_when_tesseract_unavailable(self, mock_which, tmp_path: Path):
        path = tmp_path / "scan.pdf"
        path.write_bytes(b"%PDF-1.0 fake")
        meta = self.extractor.extract(path)
        assert meta.has_isbn is False
        assert meta.confidence == 0.0

    def test_source(self, tmp_path: Path):
        path = tmp_path / "scan.pdf"
        path.write_bytes(b"%PDF-1.0 fake")
        meta = self.extractor.extract(path)
        assert meta.source == "ocr"
