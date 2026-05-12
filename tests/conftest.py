from pathlib import Path

import pytest


@pytest.fixture
def tmp_ebook_dir(tmp_path: Path) -> Path:
    return tmp_path / "ebooks"


@pytest.fixture
def tmp_output_dir(tmp_path: Path) -> Path:
    out = tmp_path / "output"
    out.mkdir()
    return out
