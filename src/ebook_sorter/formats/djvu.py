from __future__ import annotations

import shutil
import subprocess
from pathlib import Path


def is_available() -> bool:
    return shutil.which("djvutxt") is not None


def extract_text(path: Path) -> str:
    if not path.exists():
        raise FileNotFoundError(f"File not found: {path}")
    if not is_available():
        return ""
    try:
        result = subprocess.run(
            ["djvutxt", str(path)],
            capture_output=True,
            text=True,
            timeout=120,
        )
        return result.stdout
    except subprocess.TimeoutExpired:
        return ""


def extract_metadata(path: Path) -> dict[str, str]:
    if not path.exists():
        raise FileNotFoundError(f"File not found: {path}")
    if shutil.which("djvused") is None:
        return {}
    try:
        result = subprocess.run(
            ["djvused", str(path), "-e", "print-meta"],
            capture_output=True,
            text=True,
            timeout=30,
        )
        meta: dict[str, str] = {}
        for line in result.stdout.splitlines():
            if "\t" in line:
                key, _, value = line.partition("\t")
                meta[key.strip().lower()] = value.strip().strip('"')
        return meta
    except subprocess.TimeoutExpired:
        return {}
