from pathlib import Path

from ebook_sorter.models import BookMetadata
from ebook_sorter.organizer import Organizer


class TestRenderFilename:
    def setup_method(self):
        self.organizer = Organizer(
            output_dir=Path("/output"),
            filename_template="{authors} - {title} ({year}) [{isbn}].{ext}",
            folder_template="{authors}",
        )

    def test_full_metadata(self):
        meta = BookMetadata(
            title="Little Brother",
            authors=["Cory Doctorow"],
            isbn_13="9780765319852",
            year=2008,
            extension="pdf",
        )
        filename = self.organizer.render_filename(meta)
        assert filename == "Cory Doctorow - Little Brother (2008) [9780765319852].pdf"

    def test_missing_year(self):
        meta = BookMetadata(
            title="Little Brother",
            authors=["Cory Doctorow"],
            isbn_13="9780765319852",
            extension="pdf",
        )
        filename = self.organizer.render_filename(meta)
        assert filename == "Cory Doctorow - Little Brother () [9780765319852].pdf"

    def test_sanitizes_filename(self):
        meta = BookMetadata(
            title="What/Is: This?",
            authors=["Author"],
            extension="pdf",
        )
        filename = self.organizer.render_filename(meta)
        assert "/" not in filename
        assert ":" not in filename
        assert "?" not in filename


class TestRenderPath:
    def test_with_folder_template(self):
        organizer = Organizer(
            output_dir=Path("/output"),
            filename_template="{title}.{ext}",
            folder_template="{authors}",
        )
        meta = BookMetadata(
            title="Little Brother",
            authors=["Cory Doctorow"],
            extension="pdf",
        )
        result = organizer.render_path(meta)
        assert result == Path("/output/Cory Doctorow/Little Brother.pdf")


class TestMoveFile:
    def test_move_file(self, tmp_path: Path):
        src = tmp_path / "source" / "book.pdf"
        src.parent.mkdir()
        src.write_text("fake pdf content")

        out = tmp_path / "output"
        out.mkdir()

        organizer = Organizer(
            output_dir=out,
            filename_template="{title}.{ext}",
            folder_template="",
        )
        meta = BookMetadata(
            title="Renamed",
            extension="pdf",
            original_path=src,
        )
        dest = organizer.move_file(meta)
        assert dest.exists()
        assert dest.name == "Renamed.pdf"
        assert not src.exists()

    def test_move_file_dry_run(self, tmp_path: Path):
        src = tmp_path / "book.pdf"
        src.write_text("fake pdf content")

        out = tmp_path / "output"
        out.mkdir()

        organizer = Organizer(
            output_dir=out,
            filename_template="{title}.{ext}",
            folder_template="",
            dry_run=True,
        )
        meta = BookMetadata(title="Renamed", extension="pdf", original_path=src)
        dest = organizer.move_file(meta)
        assert src.exists()
        assert not dest.exists()

    def test_move_file_handles_collision(self, tmp_path: Path):
        out = tmp_path / "output"
        out.mkdir()
        existing = out / "Book.pdf"
        existing.write_text("existing")

        src = tmp_path / "book.pdf"
        src.write_text("new content")

        organizer = Organizer(
            output_dir=out,
            filename_template="{title}.{ext}",
            folder_template="",
        )
        meta = BookMetadata(title="Book", extension="pdf", original_path=src)
        dest = organizer.move_file(meta)
        assert dest.exists()
        assert dest.name == "Book (2).pdf"
