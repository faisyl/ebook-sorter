"""create_app config loading via CONFIG_PATH env var (X16)."""
from pathlib import Path

import pytest

from ebook_sorter.web.app import create_app
from ebook_sorter.web.config import WebConfig


@pytest.fixture
def web_cfg(tmp_path: Path) -> WebConfig:
    books = tmp_path / "books"
    books.mkdir()
    output = tmp_path / "output"
    output.mkdir()
    data = tmp_path / "data"
    data.mkdir()
    return WebConfig(
        books_root=books,
        output_root=output,
        data_dir=data,
        user="admin",
        password="secret123",
        secret="test-secret",
        port=8080,
        google_books_api_key=None,
        filename_template="{title}.{ext}",
        folder_template="",
        confidence_threshold=0.7,
        ocr_enabled=False,
    )


def test_config_path_env_var_is_honored(
    web_cfg: WebConfig, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Simulate a container where CWD is "/" and the config is mounted
    # elsewhere: CONFIG_PATH must be consulted instead of the CWD-relative
    # default (X16), which previously silently fell back to defaults.
    config_file = tmp_path / "mounted" / "ebook-sorter.toml"
    config_file.parent.mkdir()
    config_file.write_text(
        '[ebook-sorter]\nfilename_template = "{title}-CONFIG-PATH-MARKER.{ext}"\n'
    )
    monkeypatch.setenv("CONFIG_PATH", str(config_file))
    # Also confirm the CWD-relative file (if any) is NOT what gets read.
    monkeypatch.chdir(tmp_path)

    app = create_app(web_cfg=web_cfg)
    assert app.state.cfg.filename_template == "{title}-CONFIG-PATH-MARKER.{ext}"


def test_missing_config_path_falls_back_to_defaults(
    web_cfg: WebConfig, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv("CONFIG_PATH", raising=False)
    monkeypatch.chdir(tmp_path)  # no ebook-sorter.toml here

    app = create_app(web_cfg=web_cfg)
    assert app.state.cfg.filename_template != "{title}-CONFIG-PATH-MARKER.{ext}"
