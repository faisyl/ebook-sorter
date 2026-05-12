from pathlib import Path

import fitz
import pytest
from click.testing import CliRunner

from ebook_sorter.cli import cli


@pytest.fixture
def runner():
    return CliRunner()


@pytest.fixture
def ebook_folder(tmp_path: Path) -> Path:
    folder = tmp_path / "ebooks"
    folder.mkdir()
    doc = fitz.open()
    doc.set_metadata({"title": "Test Book", "author": "Test Author"})
    page = doc.new_page()
    page.insert_text(fitz.Point(72, 72), "ISBN 978-0-7653-1985-2")
    doc.save(str(folder / "test.pdf"))
    doc.close()
    return folder


def test_cli_help(runner: CliRunner):
    result = runner.invoke(cli, ["--help"])
    assert result.exit_code == 0
    assert "Usage" in result.output


def test_cli_scan(runner: CliRunner, ebook_folder: Path):
    result = runner.invoke(cli, ["scan", str(ebook_folder)])
    assert result.exit_code == 0


def test_cli_find_isbn(runner: CliRunner, ebook_folder: Path):
    pdf = ebook_folder / "test.pdf"
    result = runner.invoke(cli, ["find-isbn", str(pdf)])
    assert result.exit_code == 0
    assert "9780765319852" in result.output


def test_cli_identify(runner: CliRunner, ebook_folder: Path):
    pdf = ebook_folder / "test.pdf"
    result = runner.invoke(cli, ["identify", str(pdf)])
    assert result.exit_code == 0


def test_cli_organize_dry_run(runner: CliRunner, ebook_folder: Path, tmp_path: Path):
    out_dir = tmp_path / "output"
    out_dir.mkdir()
    result = runner.invoke(cli, [
        "organize", str(ebook_folder),
        "--output-dir", str(out_dir),
        "--dry-run",
    ])
    assert result.exit_code == 0
    assert (ebook_folder / "test.pdf").exists()
