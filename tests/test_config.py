from pathlib import Path

from ebook_sorter.config import Config, _DEFAULT_SERIES_AUTHOR_SORT, load_config


def test_config_defaults():
    cfg = Config()
    assert cfg.output_dir == Path(".")
    assert cfg.filename_template == "{authors} - {title} ({year}) [{isbn}].{ext}"
    assert cfg.folder_template == "{author_sort}/{series}"
    assert cfg.confidence_threshold == 0.7
    assert cfg.ocr_enabled is False
    assert cfg.ocr_first_pages == 7
    assert cfg.ocr_last_pages == 3
    assert cfg.dry_run is False


def test_load_config_from_toml(tmp_path: Path):
    config_file = tmp_path / "config.toml"
    config_file.write_text("""
[ebook-sorter]
output_dir = "/tmp/output"
filename_template = "{title}.{ext}"
confidence_threshold = 0.8
ocr_enabled = true
""")
    cfg = load_config(config_file)
    assert cfg.output_dir == Path("/tmp/output")
    assert cfg.filename_template == "{title}.{ext}"
    assert cfg.confidence_threshold == 0.8
    assert cfg.ocr_enabled is True


def test_load_config_missing_file():
    cfg = load_config(Path("/nonexistent/config.toml"))
    assert cfg == Config()


def test_config_ocr_pages_parsing():
    cfg = Config()
    assert cfg.ocr_first_pages == 7
    assert cfg.ocr_last_pages == 3


def test_defaults_include_common_series():
    assert "The Expanse" in _DEFAULT_SERIES_AUTHOR_SORT
    assert _DEFAULT_SERIES_AUTHOR_SORT["The Expanse"] == "Corey, James S.A."
    assert "Wheel of Time" in _DEFAULT_SERIES_AUTHOR_SORT
    assert _DEFAULT_SERIES_AUTHOR_SORT["Wheel of Time"] == "Jordan, Robert"
    assert "Warriors" in _DEFAULT_SERIES_AUTHOR_SORT
    assert _DEFAULT_SERIES_AUTHOR_SORT["Warriors"] == "Hunter, Erin"


def test_load_config_injects_defaults(tmp_path: Path):
    config_file = tmp_path / "config.toml"
    config_file.write_text("[ebook-sorter]\noutput_dir = \"/tmp\"\n")
    cfg = load_config(config_file)
    assert cfg.series_author_sort.get("The Expanse") == "Corey, James S.A."
    assert cfg.series_author_sort.get("Wheel of Time") == "Jordan, Robert"


def test_load_config_user_overrides_win(tmp_path: Path):
    config_file = tmp_path / "config.toml"
    config_file.write_text("""
[ebook-sorter]
output_dir = "/tmp"

[ebook-sorter.series_author_sort]
"The Expanse" = "Abraham, Daniel"
"My Series" = "Doe, Jane"
""")
    cfg = load_config(config_file)
    assert cfg.series_author_sort["The Expanse"] == "Abraham, Daniel"
    assert cfg.series_author_sort["My Series"] == "Doe, Jane"
    # Other defaults still present
    assert cfg.series_author_sort.get("Wheel of Time") == "Jordan, Robert"


def test_load_config_no_file_has_empty_series_overrides():
    cfg = load_config(Path("/nonexistent/config.toml"))
    # Direct Config() construction gives empty dict; load_config for missing file same
    assert cfg.series_author_sort == {}
