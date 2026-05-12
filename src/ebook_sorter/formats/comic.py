from __future__ import annotations

import shutil
import subprocess
import tempfile
import xml.etree.ElementTree as ET
from pathlib import Path


def _7z_available() -> bool:
    return shutil.which("7z") is not None


def extract_metadata(path: Path) -> dict[str, str]:
    if not path.exists():
        raise FileNotFoundError(f"File not found: {path}")
    if not _7z_available():
        return {}
    try:
        with tempfile.TemporaryDirectory() as tmp_dir:
            subprocess.run(
                ["7z", "e", str(path), "-o" + tmp_dir, "ComicInfo.xml", "-y"],
                capture_output=True,
                timeout=30,
            )
            info_path = Path(tmp_dir) / "ComicInfo.xml"
            if not info_path.exists():
                return {}
            tree = ET.parse(info_path)
            root = tree.getroot()
            meta: dict[str, str] = {}
            for field in ("Title", "Series", "Writer", "Publisher", "Year", "Number"):
                el = root.find(field)
                if el is not None and el.text:
                    meta[field.lower()] = el.text
            return meta
    except (subprocess.TimeoutExpired, ET.ParseError):
        return {}
