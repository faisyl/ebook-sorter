from __future__ import annotations

import logging
import re
import shutil
from pathlib import Path

from ebook_sorter.models import BookMetadata

logger = logging.getLogger(__name__)

_UNSAFE_CHARS = re.compile(r'[<>:"/\\|?*]')


def _sanitize(name: str) -> str:
    return _UNSAFE_CHARS.sub("_", name).strip(". ")


class Organizer:
    def __init__(
        self,
        output_dir: Path,
        filename_template: str,
        folder_template: str,
        dry_run: bool = False,
    ) -> None:
        self.output_dir = output_dir
        self.filename_template = filename_template
        self.folder_template = folder_template
        self.dry_run = dry_run

    def render_filename(self, meta: BookMetadata) -> str:
        d = meta.template_dict()
        name_without_ext = self.filename_template.replace(".{ext}", "")
        rendered = name_without_ext.format_map(d)
        rendered = _sanitize(rendered)
        ext = d.get("ext", "")
        if ext:
            return f"{rendered}.{ext}"
        return rendered

    def render_path(self, meta: BookMetadata) -> Path:
        d = meta.template_dict()
        folder = ""
        if self.folder_template:
            folder = _sanitize(self.folder_template.format_map(d))
        filename = self.render_filename(meta)
        return self.output_dir / folder / filename if folder else self.output_dir / filename

    def move_file(self, meta: BookMetadata) -> Path:
        dest = self.render_path(meta)
        dest = self._resolve_collision(dest)

        if self.dry_run:
            logger.info("DRY RUN: %s -> %s", meta.original_path, dest)
            return dest

        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(meta.original_path), str(dest))
        logger.info("Moved: %s -> %s", meta.original_path, dest)
        return dest

    def _resolve_collision(self, dest: Path) -> Path:
        if not dest.exists():
            return dest
        stem = dest.stem
        ext = dest.suffix
        parent = dest.parent
        counter = 2
        while True:
            candidate = parent / f"{stem} ({counter}){ext}"
            if not candidate.exists():
                return candidate
            counter += 1
