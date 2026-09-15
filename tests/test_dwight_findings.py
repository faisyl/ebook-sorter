"""Failing tests reproducing bugs from the T1 review (Jim).

These capture the concrete failure scenarios so the fix phase (Ryan)
can drive them green. Each test documents the expected vs actual
behaviour from the review report.
"""
import subprocess
from pathlib import Path
from unittest.mock import patch

from ebook_sorter.config import Config, load_config
from ebook_sorter.extractors.filename import FilenameExtractor
from ebook_sorter.models import BookMetadata
from ebook_sorter.organizer import Organizer


def make_path(name: str) -> Path:
    return Path(f"/fake/{name}")


# ── B1 · filename extraction drops middle segment ─────────────────────


class TestFilenameMiddleSegmentDrop:
    def setup_method(self):
        self.extractor = FilenameExtractor()

    def test_series_bracket_in_middle_keeps_real_title(self):
        """B1: "Author - Title [Omnibus] - Extra" should keep "Title" as title.

        Currently the series strip removes [Omnibus], the remaining
        "Author - Title - Extra" splits to ["Author","Title","Extra"],
        and title=parts[-1]="Extra" — the real title "Title" is lost.
        The real title should win over a trailing noise segment.
        """
        path = make_path("Author - Title [Omnibus] - Extra.epub")
        meta = self.extractor.extract(path)
        assert meta.series == "Omnibus"
        assert meta.title == "Title"
        assert meta.authors == ["Author"]

    def test_series_bracket_before_title_still_works(self):
        """Existing convention: "Author - [Series #1] - Title" → title="Title".

        The fix for B1 must not regress this case where the bracket
        precedes the title.
        """
        path = make_path("Author - [Series #1] - Title.epub")
        meta = self.extractor.extract(path)
        assert meta.series == "Series"
        assert meta.series_index == 1.0
        assert meta.title == "Title"

    def test_series_bracket_at_end_still_works(self):
        """Existing convention: "Author - Title [Series #1]" → title="Title"."""
        path = make_path("Author - Title [Series #1].epub")
        meta = self.extractor.extract(path)
        assert meta.series == "Series"
        assert meta.title == "Title"


# ── B7 · FilenameExtractor sets confidence=0.4 even when nothing found ──


class TestFilenameExtractorZeroConfidence:
    def setup_method(self):
        self.extractor = FilenameExtractor()

    def test_no_title_gives_zero_confidence(self):
        """B7: a stem like "book" has no real title — confidence should be 0.0."""
        path = make_path("book.epub")
        meta = self.extractor.extract(path)
        assert meta.title == "book"
        # confidence=0.4 on a bare unstructured stem overstates what we found
        assert meta.confidence == 0.0

    def test_meaningful_author_title_keeps_confidence(self):
        """When author + title are present, confidence=0.4 is still correct."""
        path = make_path("Cory Doctorow - Little Brother.epub")
        meta = self.extractor.extract(path)
        assert meta.title == "Little Brother"
        assert meta.authors == ["Cory Doctorow"]
        assert meta.confidence == 0.4


# ── B8 · render_filename trailing dot when ext is empty ───────────────


class TestRenderFilenameEmptyExt:
    def test_no_trailing_dot_when_ext_empty(self):
        """B8: with an unsupported format (ext=""), output must not end in ".".

        Template "{title}.{ext}" + ext="" → currently "Book." (trailing dot,
        hidden file on Unix). Expected: just "Book".
        """
        organizer = Organizer(
            output_dir=Path("/output"),
            filename_template="{title}.{ext}",
            folder_template="",
        )
        meta = BookMetadata(title="Book", extension="")
        filename = organizer.render_filename(meta)
        assert filename == "Book"
        assert not filename.endswith(".")

    def test_ext_present_still_appended(self):
        """Regression guard: a real ext still produces "Book.pdf"."""
        organizer = Organizer(
            output_dir=Path("/output"),
            filename_template="{title}.{ext}",
            folder_template="",
        )
        meta = BookMetadata(title="Book", extension="pdf")
        filename = organizer.render_filename(meta)
        assert filename == "Book.pdf"


# ── G6 · load_config missing-file test is flaky when env var is set ────


class TestLoadConfigDeterministic:
    def test_missing_file_ignores_env_vars(self):
        """G6: load_config on a missing file must return bare defaults.

        Currently _apply_env_vars runs unconditionally, so if
        GOOGLE_BOOKS_API_KEY is set in the environment, the returned
        Config differs from Config() and the assertion fails. The test
        must pin the env to be deterministic.
        """
        with patch.dict("os.environ", {}, clear=True):
            cfg = load_config(Path("/nonexistent/config.toml"))
            assert cfg.google_books_api_key is None
            assert cfg == Config()


# ── B5 · mobi extract_text cleans up tmp on timeout ───────────────────


class TestMobiExtractTextTmpCleanup:
    def test_tmp_file_removed_on_timeout(self, tmp_path: Path):
        """B5: NamedTemporaryFile(delete=False) leaks on TimeoutExpired."""
        from ebook_sorter.formats import mobi

        tmp_txt = tmp_path / "output.txt"
        tmp_txt.write_text("converted text")
        book = tmp_path / "book.mobi"
        book.write_text("dummy")

        def fake_run(*args, **kwargs):
            raise subprocess.TimeoutExpired(cmd="ebook-convert", timeout=120)

        with patch("ebook_sorter.formats.mobi.subprocess.run", side_effect=fake_run), \
             patch("ebook_sorter.formats.mobi.shutil.which", return_value="/usr/bin/ebook-convert"), \
             patch("ebook_sorter.formats.mobi.tempfile.NamedTemporaryFile") as mock_tmp:
            mock_tmp.return_value.name = str(tmp_txt)
            result = mobi.extract_text(book)
            assert result == ""
            assert not tmp_txt.exists(), "temp file leaked after TimeoutExpired"
