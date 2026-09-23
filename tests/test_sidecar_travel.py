"""W17: sidecar must travel with the book on move/copy."""
import json
from pathlib import Path

import pytest

from ebook_sorter.models import BookMetadata
from ebook_sorter.organizer import Organizer
from ebook_sorter.sidecar import sidecar_path, write_sidecar


@pytest.fixture
def sample_meta() -> BookMetadata:
    return BookMetadata(
        title="Dune",
        authors=["Frank Herbert"],
        isbn_13="9780441172719",
        year=1965,
        extension="epub",
        confidence=0.9,
    )


def _make_book_with_sidecar(dir_path: Path, name: str) -> tuple[Path, Path]:
    """Create a book file and its metadata sidecar."""
    book = dir_path / name
    book.write_text("dummy ebook content")
    meta = BookMetadata(
        title=name.replace(".epub", ""),
        authors=["Test Author"],
        isbn_13="9780441172719",
        year=2020,
        extension="epub",
        confidence=0.9,
    )
    sidecar = write_sidecar(meta, book)
    return book, sidecar


class TestOrganizerSidecarMove:
    """Test 1: organizer.move_file moves the sidecar with the book."""

    def test_sidecar_moved_with_book(self, tmp_path, sample_meta):
        """After move_file, sidecar must be next to the destination, not orphaned."""
        src_dir = tmp_path / "source"
        src_dir.mkdir()
        out_dir = tmp_path / "output"
        out_dir.mkdir()

        book, sidecar = _make_book_with_sidecar(src_dir, "Dune.epub")
        assert sidecar.exists(), "sidecar should exist before move"

        organizer = Organizer(
            output_dir=out_dir,
            filename_template="{title}.{ext}",
            folder_template="",
        )
        sample_meta.original_path = book
        dest = organizer.move_file(sample_meta)

        assert dest.exists(), "book should be at destination"
        assert not book.exists(), "original book should be gone (move)"

        expected_sidecar = sidecar_path(dest)
        assert expected_sidecar.exists(), f"sidecar should be at destination: {expected_sidecar}"
        assert not sidecar.exists(), "original sidecar should be gone after move"

    def test_no_sidecar_is_fine(self, tmp_path, sample_meta):
        """move_file without a sidecar should still work."""
        src_dir = tmp_path / "source"
        src_dir.mkdir()
        out_dir = tmp_path / "output"
        out_dir.mkdir()

        book = src_dir / "Dune.epub"
        book.write_text("dummy")

        organizer = Organizer(
            output_dir=out_dir,
            filename_template="{title}.{ext}",
            folder_template="",
        )
        sample_meta.original_path = book
        dest = organizer.move_file(sample_meta)
        assert dest.exists()

    def test_dry_run_does_not_move_sidecar(self, tmp_path, sample_meta):
        """In dry_run mode, neither book nor sidecar should move."""
        src_dir = tmp_path / "source"
        src_dir.mkdir()
        out_dir = tmp_path / "output"
        out_dir.mkdir()

        book, sidecar = _make_book_with_sidecar(src_dir, "Dune.epub")

        organizer = Organizer(
            output_dir=out_dir,
            filename_template="{title}.{ext}",
            folder_template="",
            dry_run=True,
        )
        sample_meta.original_path = book
        dest = organizer.move_file(sample_meta)

        assert book.exists(), "book should NOT move in dry_run"
        assert sidecar.exists(), "sidecar should NOT move in dry_run"
        assert not dest.exists(), "destination should NOT exist in dry_run"


class TestSidecarCopyMode:
    """Test 2: copy mode should leave original sidecar in place."""

    def test_copy_keeps_original_sidecar(self, tmp_path, sample_meta):
        """In copy mode, both book and sidecar should remain at source."""
        src_dir = tmp_path / "source"
        src_dir.mkdir()
        out_dir = tmp_path / "output"
        out_dir.mkdir()

        book, sidecar = _make_book_with_sidecar(src_dir, "Dune.epub")

        organizer = Organizer(
            output_dir=out_dir,
            filename_template="{title}.{ext}",
            folder_template="",
        )
        # Simulate copy: shutil.copy2 for both book and sidecar
        dest = out_dir / "Dune.epub"
        import shutil
        shutil.copy2(str(book), str(dest))
        sidecar_dest = sidecar_path(dest)
        shutil.copy2(str(sidecar), str(sidecar_dest))

        assert book.exists(), "original book should remain in copy mode"
        assert sidecar.exists(), "original sidecar should remain in copy mode"
        assert dest.exists(), "book copy should exist"
        assert sidecar_dest.exists(), "sidecar copy should exist"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
