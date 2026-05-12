from __future__ import annotations

import shutil
import subprocess
import tempfile
from pathlib import Path


def _calibre_available() -> bool:
    return shutil.which("ebook-meta") is not None


def extract_metadata(path: Path) -> dict[str, str]:
    if not path.exists():
        raise FileNotFoundError(f"File not found: {path}")
    if not _calibre_available():
        return {}
    try:
        result = subprocess.run(
            ["ebook-meta", str(path)],
            capture_output=True,
            text=True,
            timeout=30,
        )
        meta: dict[str, str] = {}
        for line in result.stdout.splitlines():
            if ":" in line:
                key, _, value = line.partition(":")
                key = key.strip().lower()
                value = value.strip()
                if key and value:
                    meta[key] = value
        return meta
    except subprocess.TimeoutExpired:
        return {}


def extract_text(path: Path) -> str:
    if not path.exists():
        raise FileNotFoundError(f"File not found: {path}")
    if not shutil.which("ebook-convert"):
        return ""
    try:
        with tempfile.NamedTemporaryFile(suffix=".txt", delete=False) as tmp:
            tmp_path = tmp.name
        subprocess.run(
            ["ebook-convert", str(path), tmp_path],
            capture_output=True,
            timeout=120,
        )
        txt = Path(tmp_path)
        if txt.exists():
            text = txt.read_text(errors="replace")
            txt.unlink()
            return text
        return ""
    except subprocess.TimeoutExpired:
        return ""
