"""Web-app configuration from environment variables."""
from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


@dataclass
class WebConfig:
    books_root: Path
    output_root: Path
    data_dir: Path
    user: str
    password: str
    secret: str
    port: int
    google_books_api_key: str | None
    # Pipeline defaults that seed new jobs
    filename_template: str
    folder_template: str
    confidence_threshold: float
    ocr_enabled: bool


def load_web_config() -> WebConfig:
    return WebConfig(
        books_root=Path(os.environ.get("BOOKS_ROOT", "/books")),
        output_root=Path(os.environ.get("OUTPUT_ROOT", "/output")),
        data_dir=Path(os.environ.get("APP_DATA", "/data")),
        user=os.environ.get("APP_USER", "admin"),
        password=os.environ.get("APP_PASSWORD", "changeme"),
        secret=os.environ.get("APP_SECRET", os.urandom(32).hex()),
        port=int(os.environ.get("PORT", "8080")),
        google_books_api_key=os.environ.get("GOOGLE_BOOKS_API_KEY"),
        filename_template=os.environ.get(
            "FILENAME_TEMPLATE",
            "{authors}{series_part} - {title} ({year}) [{isbn}].{ext}",
        ),
        folder_template=os.environ.get("FOLDER_TEMPLATE", "{author_sort}/{series}"),
        confidence_threshold=float(os.environ.get("CONFIDENCE_THRESHOLD", "0.7")),
        ocr_enabled=os.environ.get("OCR_ENABLED", "").lower() in ("1", "true", "yes"),
    )
