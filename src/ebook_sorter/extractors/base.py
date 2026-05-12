from __future__ import annotations

import abc
from pathlib import Path

from ebook_sorter.models import BookMetadata


class BaseExtractor(abc.ABC):
    @abc.abstractmethod
    def extract(self, path: Path) -> BookMetadata:
        ...
