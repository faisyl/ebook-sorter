from __future__ import annotations

import logging
import os
import tomllib
from dataclasses import dataclass, field
from pathlib import Path

logger = logging.getLogger(__name__)

_DEFAULT_SERIES_AUTHOR_SORT: dict[str, str] = {
    # Pen names (multiple real authors writing under one name)
    "The Expanse": "Corey, James S.A.",
    "Warriors": "Hunter, Erin",
    "Seekers": "Hunter, Erin",
    "Survivors": "Hunter, Erin",
    "Bravelands": "Hunter, Erin",
    "Dawn of the Clans": "Hunter, Erin",
    "A Vision of Shadows": "Hunter, Erin",
    "The Broken Code": "Hunter, Erin",
    "A Starless Clan": "Hunter, Erin",
    # Legacy continuations — sort under original author
    "Wheel of Time": "Jordan, Robert",
    "Dune": "Herbert, Frank",
    "Dune Chronicles": "Herbert, Frank",
    "Foundation": "Asimov, Isaac",
    "Robot": "Asimov, Isaac",
    "Dragonriders of Pern": "McCaffrey, Anne",
    "Pern": "McCaffrey, Anne",
    "The Hitchhiker's Guide to the Galaxy": "Adams, Douglas",
    "Hitchhiker's Guide to the Galaxy": "Adams, Douglas",
    "Dark Tower": "King, Stephen",
    "Valdemar": "Lackey, Mercedes",
    "Heralds of Valdemar": "Lackey, Mercedes",
    "Darkover": "Bradley, Marion Zimmer",
    # Co-written series (no pen name)
    "Good Omens": "Pratchett, Terry",
    "Dragonlance": "Weis, Margaret",
    "Dragonlance Chronicles": "Weis, Margaret",
    "Dragonlance Legends": "Weis, Margaret",
    "Liaden Universe": "Lee, Sharon",
    "Empire of Man": "Ringo, John",
    "Prince Roger": "Ringo, John",
    # Tom Clancy brand universe
    "Jack Ryan": "Clancy, Tom",
    "John Clark": "Clancy, Tom",
    "The Campus": "Clancy, Tom",
    "Net Force": "Clancy, Tom",
    "Op-Center": "Clancy, Tom",
    "Power Plays": "Clancy, Tom",
    # Shared-world anthologies
    "Wild Cards": "Martin, George R.R.",
    "1632": "Flint, Eric",
    "Ring of Fire": "Flint, Eric",
    "Man-Kzin Wars": "Niven, Larry",
    "Thieves' World": "Asprin, Robert",
    "MythAdventures": "Asprin, Robert",
}


@dataclass
class Config:
    output_dir: Path = field(default_factory=lambda: Path("."))
    filename_template: str = "{authors} - {series} {series_index_padded} - {title} [{isbn}].{ext}"
    folder_template: str = "{author_sort}/{series}"
    confidence_threshold: float = 0.7
    ocr_enabled: bool = False
    ocr_first_pages: int = 7
    ocr_last_pages: int = 3
    dry_run: bool = False
    verbose: bool = False
    corrupt_dir: Path | None = None
    uncertain_dir: Path | None = None
    google_books_api_key: str | None = None
    series_author_sort: dict[str, str] = field(default_factory=dict)


def _apply_env_vars(cfg: Config) -> Config:
    if not cfg.google_books_api_key:
        cfg.google_books_api_key = os.environ.get("GOOGLE_BOOKS_API_KEY")
    return cfg


def load_config(path: Path) -> Config:
    if not path.exists():
        return _apply_env_vars(Config())

    try:
        with open(path, "rb") as f:
            data = tomllib.load(f)
    except Exception:
        logger.warning("Failed to parse config file: %s", path, exc_info=True)
        return _apply_env_vars(Config())

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

    user_overrides = section.get("series_author_sort", {})
    kwargs["series_author_sort"] = {**_DEFAULT_SERIES_AUTHOR_SORT, **user_overrides}

    return _apply_env_vars(Config(**kwargs))
