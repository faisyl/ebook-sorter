from __future__ import annotations

import logging
import tomllib
from dataclasses import dataclass, field
from pathlib import Path

logger = logging.getLogger(__name__)


@dataclass
class Config:
    output_dir: Path = field(default_factory=lambda: Path("."))
    filename_template: str = "{authors} - {title} ({year}) [{isbn}].{ext}"
    folder_template: str = "{authors}"
    confidence_threshold: float = 0.7
    ocr_enabled: bool = False
    ocr_first_pages: int = 7
    ocr_last_pages: int = 3
    dry_run: bool = False
    verbose: bool = False
    corrupt_dir: Path | None = None
    uncertain_dir: Path | None = None
    google_books_api_key: str | None = None


def load_config(path: Path) -> Config:
    if not path.exists():
        return Config()

    try:
        with open(path, "rb") as f:
            data = tomllib.load(f)
    except Exception:
        logger.warning("Failed to parse config file: %s", path, exc_info=True)
        return Config()

    section = data.get("ebook-sorter", {})
    kwargs: dict = {}

    if "output_dir" in section:
        kwargs["output_dir"] = Path(section["output_dir"])
    if "filename_template" in section:
        kwargs["filename_template"] = section["filename_template"]
    if "folder_template" in section:
        kwargs["folder_template"] = section["folder_template"]
    if "confidence_threshold" in section:
        kwargs["confidence_threshold"] = float(section["confidence_threshold"])
    if "ocr_enabled" in section:
        kwargs["ocr_enabled"] = bool(section["ocr_enabled"])
    if "ocr_first_pages" in section:
        kwargs["ocr_first_pages"] = int(section["ocr_first_pages"])
    if "ocr_last_pages" in section:
        kwargs["ocr_last_pages"] = int(section["ocr_last_pages"])
    if "dry_run" in section:
        kwargs["dry_run"] = bool(section["dry_run"])
    if "corrupt_dir" in section:
        kwargs["corrupt_dir"] = Path(section["corrupt_dir"])
    if "uncertain_dir" in section:
        kwargs["uncertain_dir"] = Path(section["uncertain_dir"])
    if "google_books_api_key" in section:
        kwargs["google_books_api_key"] = section["google_books_api_key"]

    return Config(**kwargs)
