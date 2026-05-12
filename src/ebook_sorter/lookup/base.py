from __future__ import annotations

import abc

from ebook_sorter.models import BookMetadata


class BaseLookup(abc.ABC):
    @abc.abstractmethod
    def lookup_isbn(self, isbn: str) -> BookMetadata | None:
        ...

    @abc.abstractmethod
    def search(self, title: str, author: str = "") -> BookMetadata | None:
        ...
