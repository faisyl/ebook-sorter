from pathlib import Path

from ebook_sorter.config import Config, load_config


def test_config_defaults():
    cfg = Config()
    assert cfg.output_dir == Path(".")
    assert cfg.filename_template == "{authors} - {title} ({year}) [{isbn}].{ext}"
    assert cfg.folder_template == "{authors}"
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
