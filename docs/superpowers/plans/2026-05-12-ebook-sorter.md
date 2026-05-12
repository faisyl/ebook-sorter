# ebook-sorter Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a Python CLI tool that extracts metadata from ebook files (PDF, EPUB, DJVU, MOBI, CBR/CBZ) and uses it to rename and organize them into a structured library.

**Architecture:** Modular pipeline — standalone extractors pull signals (ISBNs, titles, authors) from files, lookup sources resolve them to full metadata via APIs, and an organizer renames/moves files using configurable templates. A pipeline orchestrator chains everything together with confidence scoring.

**Tech Stack:** Python 3.11+, Click (CLI), pymupdf (PDF), ebooklib (EPUB), isbnlib (ISBN), httpx (HTTP), rich (TUI)

---

## File Structure

```
ebook-sorter/
├── pyproject.toml
├── src/
│   └── ebook_sorter/
│       ├── __init__.py
│       ├── cli.py
│       ├── config.py
│       ├── models.py
│       ├── pipeline.py
│       ├── isbn.py
│       ├── organizer.py
│       ├── interactive.py
│       ├── extractors/
│       │   ├── __init__.py
│       │   ├── base.py
│       │   ├── filename.py
│       │   ├── embedded.py
│       │   ├── text_content.py
│       │   └── ocr.py
│       ├── lookup/
│       │   ├── __init__.py
│       │   ├── base.py
│       │   ├── openlibrary.py
│       │   ├── google_books.py
│       │   └── calibre.py
│       └── formats/
│           ├── __init__.py
│           ├── pdf.py
│           ├── epub.py
│           ├── djvu.py
│           ├── mobi.py
│           └── comic.py
└── tests/
    ├── __init__.py
    ├── conftest.py
    ├── test_models.py
    ├── test_isbn.py
    ├── test_config.py
    ├── test_organizer.py
    ├── test_pipeline.py
    ├── test_cli.py
    ├── extractors/
    │   ├── __init__.py
    │   ├── test_filename.py
    │   ├── test_embedded.py
    │   ├── test_text_content.py
    │   └── test_ocr.py
    ├── lookup/
    │   ├── __init__.py
    │   ├── test_openlibrary.py
    │   ├── test_google_books.py
    │   └── test_calibre.py
    └── formats/
        ├── __init__.py
        ├── test_pdf.py
        └── test_epub.py
```

---

### Task 1: Project Scaffolding

**Files:**
- Create: `pyproject.toml`
- Create: `src/ebook_sorter/__init__.py`
- Create: `tests/__init__.py`
- Create: `tests/conftest.py`

- [ ] **Step 1: Create `pyproject.toml`**

```toml
[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[project]
name = "ebook-sorter"
version = "0.1.0"
description = "Organize ebook collections by extracting metadata and renaming files"
requires-python = ">=3.11"
dependencies = [
    "click>=8.1",
    "pymupdf>=1.24",
    "ebooklib>=0.18",
    "isbnlib>=3.10",
    "httpx>=0.27",
    "rich>=13.0",
]

[project.optional-dependencies]
dev = [
    "pytest>=8.0",
    "pytest-httpx>=0.30",
    "respx>=0.21",
]

[project.scripts]
ebook-sorter = "ebook_sorter.cli:cli"

[tool.hatch.build.targets.wheel]
packages = ["src/ebook_sorter"]

[tool.pytest.ini_options]
testpaths = ["tests"]
pythonpath = ["src"]
```

- [ ] **Step 2: Create package init**

`src/ebook_sorter/__init__.py`:
```python
"""Ebook metadata extraction and organization tool."""

__version__ = "0.1.0"
```

- [ ] **Step 3: Create test infrastructure**

`tests/__init__.py`: empty file

`tests/conftest.py`:
```python
from pathlib import Path

import pytest


@pytest.fixture
def tmp_ebook_dir(tmp_path: Path) -> Path:
    return tmp_path / "ebooks"


@pytest.fixture
def tmp_output_dir(tmp_path: Path) -> Path:
    out = tmp_path / "output"
    out.mkdir()
    return out
```

- [ ] **Step 4: Create all package directories with `__init__.py`**

Create empty `__init__.py` in each:
- `src/ebook_sorter/extractors/__init__.py`
- `src/ebook_sorter/lookup/__init__.py`
- `src/ebook_sorter/formats/__init__.py`
- `tests/extractors/__init__.py`
- `tests/lookup/__init__.py`
- `tests/formats/__init__.py`

- [ ] **Step 5: Install in dev mode and verify**

Run: `cd /home/faisal/Extra/ebook-sorter && pip install -e ".[dev]"`
Expected: successful installation

Run: `python -c "import ebook_sorter; print(ebook_sorter.__version__)"`
Expected: `0.1.0`

- [ ] **Step 6: Commit**

```bash
git add pyproject.toml src/ tests/
git commit -m "feat: project scaffolding with pyproject.toml and package structure"
```

---

### Task 2: Data Model (BookMetadata)

**Files:**
- Create: `src/ebook_sorter/models.py`
- Create: `tests/test_models.py`

- [ ] **Step 1: Write the failing tests**

`tests/test_models.py`:
```python
from pathlib import Path

from ebook_sorter.models import BookMetadata


def test_book_metadata_defaults():
    meta = BookMetadata()
    assert meta.title is None
    assert meta.authors == []
    assert meta.isbn_10 is None
    assert meta.isbn_13 is None
    assert meta.confidence == 0.0


def test_isbn_property_prefers_isbn13():
    meta = BookMetadata(isbn_10="0765319853", isbn_13="9780765319852")
    assert meta.isbn == "9780765319852"


def test_isbn_property_falls_back_to_isbn10():
    meta = BookMetadata(isbn_10="0765319853")
    assert meta.isbn == "0765319853"


def test_isbn_property_none_when_missing():
    meta = BookMetadata()
    assert meta.isbn is None


def test_has_isbn():
    assert BookMetadata(isbn_13="9780765319852").has_isbn is True
    assert BookMetadata(isbn_10="0765319853").has_isbn is True
    assert BookMetadata().has_isbn is False


def test_merge_fills_missing_fields():
    base = BookMetadata(title="Little Brother", isbn_13="9780765319852")
    other = BookMetadata(
        authors=["Cory Doctorow"],
        year=2008,
        publisher="Tor Books",
        confidence=0.9,
    )
    merged = base.merge(other)
    assert merged.title == "Little Brother"
    assert merged.authors == ["Cory Doctorow"]
    assert merged.isbn_13 == "9780765319852"
    assert merged.year == 2008
    assert merged.publisher == "Tor Books"
    assert merged.confidence == 0.9


def test_merge_keeps_existing_fields():
    base = BookMetadata(title="Little Brother", authors=["Cory Doctorow"])
    other = BookMetadata(title="Wrong Title", authors=["Wrong Author"])
    merged = base.merge(other)
    assert merged.title == "Little Brother"
    assert merged.authors == ["Cory Doctorow"]


def test_merge_takes_max_confidence():
    base = BookMetadata(confidence=0.4)
    other = BookMetadata(confidence=0.9)
    assert base.merge(other).confidence == 0.9
    assert other.merge(base).confidence == 0.9


def test_template_dict():
    meta = BookMetadata(
        title="Little Brother",
        authors=["Cory Doctorow"],
        isbn_13="9780765319852",
        year=2008,
        series="Little Brother",
        series_index=1,
        extension="pdf",
    )
    d = meta.template_dict()
    assert d["title"] == "Little Brother"
    assert d["authors"] == "Cory Doctorow"
    assert d["isbn"] == "9780765319852"
    assert d["isbn13"] == "9780765319852"
    assert d["year"] == "2008"
    assert d["series"] == "Little Brother"
    assert d["series_index"] == "1"
    assert d["ext"] == "pdf"


def test_template_dict_multiple_authors():
    meta = BookMetadata(authors=["Author A", "Author B"])
    d = meta.template_dict()
    assert d["authors"] == "Author A, Author B"


def test_template_dict_missing_fields_are_empty():
    meta = BookMetadata()
    d = meta.template_dict()
    assert d["title"] == ""
    assert d["authors"] == ""
    assert d["year"] == ""
    assert d["isbn"] == ""
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_models.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'ebook_sorter.models'`

- [ ] **Step 3: Implement BookMetadata**

`src/ebook_sorter/models.py`:
```python
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class BookMetadata:
    title: str | None = None
    authors: list[str] = field(default_factory=list)
    isbn_10: str | None = None
    isbn_13: str | None = None
    publisher: str | None = None
    year: int | None = None
    series: str | None = None
    series_index: float | None = None
    language: str | None = None
    source: str = ""
    confidence: float = 0.0
    original_path: Path | None = None
    extension: str = ""

    @property
    def isbn(self) -> str | None:
        return self.isbn_13 or self.isbn_10

    @property
    def has_isbn(self) -> bool:
        return self.isbn_10 is not None or self.isbn_13 is not None

    def merge(self, other: BookMetadata) -> BookMetadata:
        return BookMetadata(
            title=self.title or other.title,
            authors=self.authors or other.authors,
            isbn_10=self.isbn_10 or other.isbn_10,
            isbn_13=self.isbn_13 or other.isbn_13,
            publisher=self.publisher or other.publisher,
            year=self.year or other.year,
            series=self.series or other.series,
            series_index=self.series_index if self.series_index is not None else other.series_index,
            language=self.language or other.language,
            source=self.source or other.source,
            confidence=max(self.confidence, other.confidence),
            original_path=self.original_path or other.original_path,
            extension=self.extension or other.extension,
        )

    def template_dict(self) -> dict[str, str]:
        return {
            "title": self.title or "",
            "authors": ", ".join(self.authors) if self.authors else "",
            "isbn": self.isbn or "",
            "isbn10": self.isbn_10 or "",
            "isbn13": self.isbn_13 or "",
            "publisher": self.publisher or "",
            "year": str(self.year) if self.year else "",
            "series": self.series or "",
            "series_index": str(int(self.series_index)) if self.series_index is not None and self.series_index == int(self.series_index) else str(self.series_index) if self.series_index is not None else "",
            "language": self.language or "",
            "ext": self.extension,
        }
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_models.py -v`
Expected: All PASS

- [ ] **Step 5: Commit**

```bash
git add src/ebook_sorter/models.py tests/test_models.py
git commit -m "feat: BookMetadata dataclass with merge and template support"
```

---

### Task 3: ISBN Detection & Validation

**Files:**
- Create: `src/ebook_sorter/isbn.py`
- Create: `tests/test_isbn.py`

- [ ] **Step 1: Write the failing tests**

`tests/test_isbn.py`:
```python
from ebook_sorter.isbn import (
    find_isbns,
    is_valid_isbn_10,
    is_valid_isbn_13,
    isbn_10_to_13,
    normalize_isbn,
)


class TestNormalizeIsbn:
    def test_removes_hyphens(self):
        assert normalize_isbn("978-0-7653-1985-2") == "9780765319852"

    def test_removes_spaces(self):
        assert normalize_isbn("978 0 7653 1985 2") == "9780765319852"

    def test_uppercases_x(self):
        assert normalize_isbn("080442957x") == "080442957X"

    def test_already_clean(self):
        assert normalize_isbn("9780765319852") == "9780765319852"


class TestIsValidIsbn10:
    def test_valid(self):
        assert is_valid_isbn_10("0765319853") is True

    def test_valid_with_x(self):
        assert is_valid_isbn_10("080442957X") is True

    def test_invalid_checksum(self):
        assert is_valid_isbn_10("0765319850") is False

    def test_wrong_length(self):
        assert is_valid_isbn_10("123") is False

    def test_x_not_at_end(self):
        assert is_valid_isbn_10("X765319853") is False


class TestIsValidIsbn13:
    def test_valid_978(self):
        assert is_valid_isbn_13("9780765319852") is True

    def test_valid_979(self):
        assert is_valid_isbn_13("9791032305690") is True

    def test_invalid_checksum(self):
        assert is_valid_isbn_13("9780765319850") is False

    def test_wrong_length(self):
        assert is_valid_isbn_13("978076531985") is False

    def test_non_numeric(self):
        assert is_valid_isbn_13("978076531985X") is False


class TestIsbn10To13:
    def test_conversion(self):
        assert isbn_10_to_13("0765319853") == "9780765319852"

    def test_conversion_with_x(self):
        assert isbn_10_to_13("080442957X") == "9780804429573"


class TestFindIsbns:
    def test_finds_isbn13_in_text(self):
        text = "This book ISBN is 978-0-7653-1985-2 and it's great"
        assert "9780765319852" in find_isbns(text)

    def test_finds_isbn10_in_text(self):
        text = "ISBN: 0-7653-1985-3 is the number"
        assert "0765319853" in find_isbns(text)

    def test_finds_multiple_isbns(self):
        text = "ISBN-10: 0765319853 and ISBN-13: 9780765319852"
        result = find_isbns(text)
        assert len(result) >= 1

    def test_no_isbns(self):
        text = "This is a regular text without any book numbers"
        assert find_isbns(text) == []

    def test_ignores_invalid_checksums(self):
        text = "Not a real ISBN: 1234567890"
        assert find_isbns(text) == []

    def test_deduplicates(self):
        text = "ISBN 9780765319852 appears twice: 9780765319852"
        result = find_isbns(text)
        assert result.count("9780765319852") == 1

    def test_finds_isbn_with_label(self):
        text = "ISBN-13: 978-0-7653-1985-2"
        assert "9780765319852" in find_isbns(text)

    def test_isbn_at_start_of_text(self):
        text = "9780765319852 is the ISBN"
        assert "9780765319852" in find_isbns(text)

    def test_isbn_at_end_of_text(self):
        text = "The ISBN is 9780765319852"
        assert "9780765319852" in find_isbns(text)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_isbn.py -v`
Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 3: Implement isbn.py**

`src/ebook_sorter/isbn.py`:
```python
from __future__ import annotations

import re


def normalize_isbn(isbn: str) -> str:
    return re.sub(r"[-\s]", "", isbn).upper()


def is_valid_isbn_10(isbn: str) -> bool:
    isbn = normalize_isbn(isbn)
    if len(isbn) != 10:
        return False
    total = 0
    for i, ch in enumerate(isbn):
        if ch == "X":
            if i != 9:
                return False
            val = 10
        elif ch.isdigit():
            val = int(ch)
        else:
            return False
        total += val * (10 - i)
    return total % 11 == 0


def is_valid_isbn_13(isbn: str) -> bool:
    isbn = normalize_isbn(isbn)
    if len(isbn) != 13 or not isbn.isdigit():
        return False
    total = sum(
        int(ch) * (1 if i % 2 == 0 else 3) for i, ch in enumerate(isbn)
    )
    return total % 10 == 0


def isbn_10_to_13(isbn_10: str) -> str:
    isbn_10 = normalize_isbn(isbn_10)
    base = "978" + isbn_10[:9]
    total = sum(
        int(ch) * (1 if i % 2 == 0 else 3) for i, ch in enumerate(base)
    )
    check = (10 - total % 10) % 10
    return base + str(check)


_ISBN_PATTERN = re.compile(
    r"(?:ISBN[-\s]?(?:1[03])?[-:\s]*)?"
    r"((?:97[89][-\s]?)?(?:\d[-\s]?){9}[\dXx])",
    re.IGNORECASE,
)


def find_isbns(text: str) -> list[str]:
    candidates = _ISBN_PATTERN.findall(text)
    valid: list[str] = []
    for raw in candidates:
        normalized = normalize_isbn(raw)
        if len(normalized) == 13 and is_valid_isbn_13(normalized):
            if normalized not in valid:
                valid.append(normalized)
        elif len(normalized) == 10 and is_valid_isbn_10(normalized):
            if normalized not in valid:
                valid.append(normalized)
    return valid
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_isbn.py -v`
Expected: All PASS

- [ ] **Step 5: Commit**

```bash
git add src/ebook_sorter/isbn.py tests/test_isbn.py
git commit -m "feat: ISBN detection, validation, and normalization"
```

---

### Task 4: PDF Format Handler

**Files:**
- Create: `src/ebook_sorter/formats/pdf.py`
- Create: `tests/formats/test_pdf.py`

- [ ] **Step 1: Write the failing tests**

`tests/formats/test_pdf.py`:
```python
from pathlib import Path

import fitz
import pytest

from ebook_sorter.formats.pdf import extract_metadata, extract_text


@pytest.fixture
def sample_pdf(tmp_path: Path) -> Path:
    path = tmp_path / "test.pdf"
    doc = fitz.open()
    doc.set_metadata({
        "title": "Test Book",
        "author": "Test Author",
        "subject": "Testing",
    })
    for i in range(5):
        page = doc.new_page()
        text_point = fitz.Point(72, 72)
        page.insert_text(text_point, f"Page {i + 1} content. ISBN 978-0-7653-1985-2")
    doc.save(str(path))
    doc.close()
    return path


@pytest.fixture
def empty_pdf(tmp_path: Path) -> Path:
    path = tmp_path / "empty.pdf"
    doc = fitz.open()
    doc.new_page()
    doc.save(str(path))
    doc.close()
    return path


def test_extract_metadata(sample_pdf: Path):
    meta = extract_metadata(sample_pdf)
    assert meta["title"] == "Test Book"
    assert meta["author"] == "Test Author"


def test_extract_metadata_empty(empty_pdf: Path):
    meta = extract_metadata(empty_pdf)
    assert meta["title"] == ""


def test_extract_text(sample_pdf: Path):
    text = extract_text(sample_pdf)
    assert "Page 1 content" in text
    assert "ISBN" in text


def test_extract_text_first_last_pages(sample_pdf: Path):
    text = extract_text(sample_pdf, first_pages=2, last_pages=1)
    assert "Page 1 content" in text
    assert "Page 2 content" in text
    assert "Page 5 content" in text


def test_extract_text_empty(empty_pdf: Path):
    text = extract_text(empty_pdf)
    assert text.strip() == ""


def test_extract_text_nonexistent():
    with pytest.raises(FileNotFoundError):
        extract_text(Path("/nonexistent/file.pdf"))
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/formats/test_pdf.py -v`
Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 3: Implement pdf.py**

`src/ebook_sorter/formats/pdf.py`:
```python
from __future__ import annotations

from pathlib import Path

import fitz


def extract_metadata(path: Path) -> dict[str, str]:
    if not path.exists():
        raise FileNotFoundError(f"File not found: {path}")
    doc = fitz.open(str(path))
    meta = doc.metadata or {}
    doc.close()
    return {
        "title": meta.get("title", "") or "",
        "author": meta.get("author", "") or "",
        "subject": meta.get("subject", "") or "",
        "creator": meta.get("creator", "") or "",
        "producer": meta.get("producer", "") or "",
    }


def extract_text(
    path: Path,
    first_pages: int | None = None,
    last_pages: int | None = None,
) -> str:
    if not path.exists():
        raise FileNotFoundError(f"File not found: {path}")
    doc = fitz.open(str(path))
    total = len(doc)

    if first_pages is None and last_pages is None:
        page_indices = range(total)
    else:
        first_n = first_pages or 0
        last_m = last_pages or 0
        indices: list[int] = []
        indices.extend(range(min(first_n, total)))
        last_start = max(total - last_m, first_n)
        indices.extend(range(last_start, total))
        page_indices = sorted(set(indices))

    parts: list[str] = []
    for i in page_indices:
        parts.append(doc[i].get_text())
    doc.close()
    return "\n".join(parts)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/formats/test_pdf.py -v`
Expected: All PASS

- [ ] **Step 5: Commit**

```bash
git add src/ebook_sorter/formats/pdf.py tests/formats/test_pdf.py
git commit -m "feat: PDF text and metadata extraction via pymupdf"
```

---

### Task 5: EPUB Format Handler

**Files:**
- Create: `src/ebook_sorter/formats/epub.py`
- Create: `tests/formats/test_epub.py`

- [ ] **Step 1: Write the failing tests**

`tests/formats/test_epub.py`:
```python
from pathlib import Path

import pytest
from ebooklib import epub

from ebook_sorter.formats.epub import extract_metadata, extract_text


@pytest.fixture
def sample_epub(tmp_path: Path) -> Path:
    path = tmp_path / "test.epub"
    book = epub.EpubBook()
    book.set_identifier("9780765319852")
    book.set_title("Test EPUB Book")
    book.set_language("en")
    book.add_author("Test Author")
    book.add_metadata("DC", "publisher", "Test Publisher")

    ch1 = epub.EpubHtml(title="Chapter 1", file_name="ch1.xhtml", lang="en")
    ch1.content = b"<html><body><p>Chapter 1 text content.</p></body></html>"
    book.add_item(ch1)

    ch2 = epub.EpubHtml(title="Chapter 2", file_name="ch2.xhtml", lang="en")
    ch2.content = b"<html><body><p>Chapter 2 text content.</p></body></html>"
    book.add_item(ch2)

    book.add_item(epub.EpubNcx())
    book.add_item(epub.EpubNav())
    book.spine = ["nav", ch1, ch2]
    epub.write_epub(str(path), book)
    return path


def test_extract_metadata(sample_epub: Path):
    meta = extract_metadata(sample_epub)
    assert meta["title"] == "Test EPUB Book"
    assert "Test Author" in meta["authors"]
    assert "9780765319852" in meta["identifiers"]


def test_extract_metadata_has_publisher(sample_epub: Path):
    meta = extract_metadata(sample_epub)
    assert meta["publisher"] == "Test Publisher"


def test_extract_text(sample_epub: Path):
    text = extract_text(sample_epub)
    assert "Chapter 1 text content" in text
    assert "Chapter 2 text content" in text


def test_extract_text_nonexistent():
    with pytest.raises(FileNotFoundError):
        extract_text(Path("/nonexistent/file.epub"))
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/formats/test_epub.py -v`
Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 3: Implement epub.py**

`src/ebook_sorter/formats/epub.py`:
```python
from __future__ import annotations

import html.parser
from pathlib import Path

import ebooklib
from ebooklib import epub


class _TextExtractor(html.parser.HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self._parts: list[str] = []

    def handle_data(self, data: str) -> None:
        self._parts.append(data)

    def get_text(self) -> str:
        return " ".join(self._parts)


def _html_to_text(content: bytes) -> str:
    parser = _TextExtractor()
    parser.feed(content.decode("utf-8", errors="replace"))
    return parser.get_text()


def extract_metadata(path: Path) -> dict[str, object]:
    if not path.exists():
        raise FileNotFoundError(f"File not found: {path}")
    book = epub.read_epub(str(path), options={"ignore_ncx": True})

    title_entries = book.get_metadata("DC", "title")
    title = title_entries[0][0] if title_entries else ""

    author_entries = book.get_metadata("DC", "creator")
    authors = [a[0] for a in author_entries] if author_entries else []

    id_entries = book.get_metadata("DC", "identifier")
    identifiers = [i[0] for i in id_entries] if id_entries else []

    pub_entries = book.get_metadata("DC", "publisher")
    publisher = pub_entries[0][0] if pub_entries else ""

    lang_entries = book.get_metadata("DC", "language")
    language = lang_entries[0][0] if lang_entries else ""

    return {
        "title": title,
        "authors": authors,
        "identifiers": identifiers,
        "publisher": publisher,
        "language": language,
    }


def extract_text(path: Path) -> str:
    if not path.exists():
        raise FileNotFoundError(f"File not found: {path}")
    book = epub.read_epub(str(path), options={"ignore_ncx": True})
    parts: list[str] = []
    for item in book.get_items_of_type(ebooklib.ITEM_DOCUMENT):
        text = _html_to_text(item.get_content())
        if text.strip():
            parts.append(text)
    return "\n".join(parts)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/formats/test_epub.py -v`
Expected: All PASS

- [ ] **Step 5: Commit**

```bash
git add src/ebook_sorter/formats/epub.py tests/formats/test_epub.py
git commit -m "feat: EPUB text and metadata extraction via ebooklib"
```

---

### Task 6: DJVU, MOBI, and Comic Format Handlers

**Files:**
- Create: `src/ebook_sorter/formats/djvu.py`
- Create: `src/ebook_sorter/formats/mobi.py`
- Create: `src/ebook_sorter/formats/comic.py`

These handlers delegate to external CLI tools (`djvutxt`, `ebook-meta`, `7z`) which may not be installed. They gracefully return empty results when tools are missing.

- [ ] **Step 1: Implement djvu.py**

`src/ebook_sorter/formats/djvu.py`:
```python
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
```

- [ ] **Step 2: Implement mobi.py**

`src/ebook_sorter/formats/mobi.py`:
```python
from __future__ import annotations

import shutil
import subprocess
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
        import tempfile

        with tempfile.NamedTemporaryFile(suffix=".txt", delete=True) as tmp:
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
```

- [ ] **Step 3: Implement comic.py**

`src/ebook_sorter/formats/comic.py`:
```python
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
```

- [ ] **Step 4: Commit**

```bash
git add src/ebook_sorter/formats/djvu.py src/ebook_sorter/formats/mobi.py src/ebook_sorter/formats/comic.py
git commit -m "feat: DJVU, MOBI, and comic book format handlers"
```

---

### Task 7: Extractor Base Class & Filename Extractor

**Files:**
- Create: `src/ebook_sorter/extractors/base.py`
- Create: `src/ebook_sorter/extractors/filename.py`
- Create: `tests/extractors/test_filename.py`

- [ ] **Step 1: Implement extractor base class**

`src/ebook_sorter/extractors/base.py`:
```python
from __future__ import annotations

import abc
from pathlib import Path

from ebook_sorter.models import BookMetadata


class BaseExtractor(abc.ABC):
    @abc.abstractmethod
    def extract(self, path: Path) -> BookMetadata:
        ...
```

- [ ] **Step 2: Write the failing tests for filename extractor**

`tests/extractors/test_filename.py`:
```python
from pathlib import Path

from ebook_sorter.extractors.filename import FilenameExtractor


def make_path(name: str) -> Path:
    return Path(f"/fake/{name}")


class TestFilenameExtractor:
    def setup_method(self):
        self.extractor = FilenameExtractor()

    def test_extracts_isbn13_from_filename(self):
        path = make_path("Some Book [9780765319852].pdf")
        meta = self.extractor.extract(path)
        assert meta.isbn_13 == "9780765319852"

    def test_extracts_isbn10_from_filename(self):
        path = make_path("Some Book [0765319853].pdf")
        meta = self.extractor.extract(path)
        assert meta.isbn_10 == "0765319853"

    def test_extracts_extension(self):
        path = make_path("book.epub")
        meta = self.extractor.extract(path)
        assert meta.extension == "epub"

    def test_extracts_author_title_dash_pattern(self):
        path = make_path("Cory Doctorow - Little Brother.pdf")
        meta = self.extractor.extract(path)
        assert meta.authors == ["Cory Doctorow"]
        assert meta.title == "Little Brother"

    def test_extracts_title_only(self):
        path = make_path("Little Brother.pdf")
        meta = self.extractor.extract(path)
        assert meta.title == "Little Brother"
        assert meta.authors == []

    def test_extracts_author_title_with_year(self):
        path = make_path("Cory Doctorow - Little Brother (2008).pdf")
        meta = self.extractor.extract(path)
        assert meta.authors == ["Cory Doctorow"]
        assert meta.title == "Little Brother"
        assert meta.year == 2008

    def test_extracts_series_in_brackets(self):
        path = make_path("Author - [Series #1] - Title.epub")
        meta = self.extractor.extract(path)
        assert meta.series == "Series"
        assert meta.series_index == 1.0
        assert meta.title == "Title"

    def test_source_is_filename(self):
        path = make_path("book.pdf")
        meta = self.extractor.extract(path)
        assert meta.source == "filename"

    def test_confidence(self):
        path = make_path("Author - Title.pdf")
        meta = self.extractor.extract(path)
        assert meta.confidence == 0.4
```

- [ ] **Step 3: Run tests to verify they fail**

Run: `pytest tests/extractors/test_filename.py -v`
Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 4: Implement filename extractor**

`src/ebook_sorter/extractors/filename.py`:
```python
from __future__ import annotations

import re
from pathlib import Path

from ebook_sorter.extractors.base import BaseExtractor
from ebook_sorter.isbn import find_isbns, is_valid_isbn_13
from ebook_sorter.models import BookMetadata

_YEAR_RE = re.compile(r"\((\d{4})\)")
_SERIES_RE = re.compile(r"\[([^\]]+?)(?:\s*#(\d+(?:\.\d+)?))?\]")


class FilenameExtractor(BaseExtractor):
    def extract(self, path: Path) -> BookMetadata:
        stem = path.stem
        ext = path.suffix.lstrip(".")

        isbns = find_isbns(stem)
        isbn_10 = None
        isbn_13 = None
        for isbn in isbns:
            if len(isbn) == 13 and is_valid_isbn_13(isbn):
                isbn_13 = isbn
            elif len(isbn) == 10:
                isbn_10 = isbn

        year = None
        year_match = _YEAR_RE.search(stem)
        if year_match:
            year = int(year_match.group(1))

        series = None
        series_index = None
        series_match = _SERIES_RE.search(stem)
        if series_match:
            series = series_match.group(1).strip()
            if series_match.group(2):
                series_index = float(series_match.group(2))

        clean = stem
        for pattern in [_YEAR_RE, _SERIES_RE]:
            clean = pattern.sub("", clean)
        for isbn in isbns:
            clean = clean.replace(isbn, "")
        clean = re.sub(r"\[[\s]*\]", "", clean).strip()

        authors: list[str] = []
        title: str | None = None

        if " - " in clean:
            parts = [p.strip() for p in clean.split(" - ", maxsplit=1)]
            parts = [p for p in parts if p]
            if len(parts) == 2:
                authors = [parts[0]]
                title = parts[1] if parts[1] else None
            elif len(parts) == 1:
                title = parts[0]
        else:
            title = clean.strip() if clean.strip() else None

        return BookMetadata(
            title=title,
            authors=authors,
            isbn_10=isbn_10,
            isbn_13=isbn_13,
            year=year,
            series=series,
            series_index=series_index,
            extension=ext,
            source="filename",
            confidence=0.4,
            original_path=path,
        )
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `pytest tests/extractors/test_filename.py -v`
Expected: All PASS

- [ ] **Step 6: Commit**

```bash
git add src/ebook_sorter/extractors/base.py src/ebook_sorter/extractors/filename.py tests/extractors/test_filename.py
git commit -m "feat: extractor base class and filename extractor"
```

---

### Task 8: Embedded Metadata Extractor

**Files:**
- Create: `src/ebook_sorter/extractors/embedded.py`
- Create: `tests/extractors/test_embedded.py`

- [ ] **Step 1: Write the failing tests**

`tests/extractors/test_embedded.py`:
```python
from pathlib import Path

import fitz
import pytest
from ebooklib import epub

from ebook_sorter.extractors.embedded import EmbeddedExtractor


@pytest.fixture
def pdf_with_metadata(tmp_path: Path) -> Path:
    path = tmp_path / "book.pdf"
    doc = fitz.open()
    doc.set_metadata({"title": "PDF Title", "author": "PDF Author"})
    doc.new_page()
    doc.save(str(path))
    doc.close()
    return path


@pytest.fixture
def epub_with_metadata(tmp_path: Path) -> Path:
    path = tmp_path / "book.epub"
    book = epub.EpubBook()
    book.set_identifier("9780765319852")
    book.set_title("EPUB Title")
    book.set_language("en")
    book.add_author("EPUB Author")
    book.add_metadata("DC", "publisher", "EPUB Publisher")
    book.add_item(epub.EpubNcx())
    book.add_item(epub.EpubNav())
    book.spine = ["nav"]
    epub.write_epub(str(path), book)
    return path


@pytest.fixture
def pdf_no_metadata(tmp_path: Path) -> Path:
    path = tmp_path / "empty.pdf"
    doc = fitz.open()
    doc.new_page()
    doc.save(str(path))
    doc.close()
    return path


class TestEmbeddedExtractor:
    def setup_method(self):
        self.extractor = EmbeddedExtractor()

    def test_pdf_metadata(self, pdf_with_metadata: Path):
        meta = self.extractor.extract(pdf_with_metadata)
        assert meta.title == "PDF Title"
        assert meta.authors == ["PDF Author"]

    def test_epub_metadata(self, epub_with_metadata: Path):
        meta = self.extractor.extract(epub_with_metadata)
        assert meta.title == "EPUB Title"
        assert meta.authors == ["EPUB Author"]
        assert meta.publisher == "EPUB Publisher"

    def test_epub_isbn_from_identifier(self, epub_with_metadata: Path):
        meta = self.extractor.extract(epub_with_metadata)
        assert meta.isbn_13 == "9780765319852"

    def test_no_metadata(self, pdf_no_metadata: Path):
        meta = self.extractor.extract(pdf_no_metadata)
        assert meta.title is None
        assert meta.authors == []

    def test_source(self, pdf_with_metadata: Path):
        meta = self.extractor.extract(pdf_with_metadata)
        assert meta.source == "embedded"

    def test_unsupported_format(self, tmp_path: Path):
        path = tmp_path / "file.xyz"
        path.write_text("not an ebook")
        meta = self.extractor.extract(path)
        assert meta.title is None
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/extractors/test_embedded.py -v`
Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 3: Implement embedded extractor**

`src/ebook_sorter/extractors/embedded.py`:
```python
from __future__ import annotations

import logging
from pathlib import Path

from ebook_sorter.extractors.base import BaseExtractor
from ebook_sorter.isbn import find_isbns, is_valid_isbn_13
from ebook_sorter.models import BookMetadata

logger = logging.getLogger(__name__)

_SUPPORTED_FORMATS: dict[str, str] = {
    ".pdf": "pdf",
    ".epub": "epub",
    ".mobi": "mobi",
    ".azw": "mobi",
    ".azw3": "mobi",
    ".djvu": "djvu",
    ".cbr": "comic",
    ".cbz": "comic",
}


class EmbeddedExtractor(BaseExtractor):
    def extract(self, path: Path) -> BookMetadata:
        ext = path.suffix.lower()
        fmt = _SUPPORTED_FORMATS.get(ext)
        if fmt is None:
            return BookMetadata(
                original_path=path,
                extension=ext.lstrip("."),
                source="embedded",
            )

        try:
            if fmt == "pdf":
                return self._extract_pdf(path)
            elif fmt == "epub":
                return self._extract_epub(path)
            elif fmt == "mobi":
                return self._extract_mobi(path)
            elif fmt == "djvu":
                return self._extract_djvu(path)
            elif fmt == "comic":
                return self._extract_comic(path)
        except Exception:
            logger.debug("Failed to extract embedded metadata from %s", path, exc_info=True)

        return BookMetadata(
            original_path=path,
            extension=ext.lstrip("."),
            source="embedded",
        )

    def _extract_pdf(self, path: Path) -> BookMetadata:
        from ebook_sorter.formats.pdf import extract_metadata

        raw = extract_metadata(path)
        title = raw.get("title") or None
        author_str = raw.get("author", "")
        authors = [a.strip() for a in author_str.split(",")] if author_str else []
        authors = [a for a in authors if a]

        return BookMetadata(
            title=title,
            authors=authors,
            extension="pdf",
            source="embedded",
            confidence=0.5 if title else 0.0,
            original_path=path,
        )

    def _extract_epub(self, path: Path) -> BookMetadata:
        from ebook_sorter.formats.epub import extract_metadata

        raw = extract_metadata(path)
        title = raw.get("title") or None
        authors = raw.get("authors", [])
        publisher = raw.get("publisher") or None
        language = raw.get("language") or None

        isbn_10 = None
        isbn_13 = None
        for ident in raw.get("identifiers", []):
            for found in find_isbns(str(ident)):
                if len(found) == 13 and is_valid_isbn_13(found):
                    isbn_13 = found
                elif len(found) == 10:
                    isbn_10 = found

        return BookMetadata(
            title=title,
            authors=authors,
            isbn_10=isbn_10,
            isbn_13=isbn_13,
            publisher=publisher,
            language=language,
            extension="epub",
            source="embedded",
            confidence=0.6 if title else 0.0,
            original_path=path,
        )

    def _extract_mobi(self, path: Path) -> BookMetadata:
        from ebook_sorter.formats.mobi import extract_metadata

        raw = extract_metadata(path)
        title = raw.get("title") or None
        author_str = raw.get("author(s)", "")
        authors = [a.strip() for a in author_str.split("&")] if author_str else []
        authors = [a for a in authors if a]

        return BookMetadata(
            title=title,
            authors=authors,
            extension=path.suffix.lstrip("."),
            source="embedded",
            confidence=0.5 if title else 0.0,
            original_path=path,
        )

    def _extract_djvu(self, path: Path) -> BookMetadata:
        from ebook_sorter.formats.djvu import extract_metadata

        raw = extract_metadata(path)
        title = raw.get("title") or None
        author_str = raw.get("author", "")
        authors = [a.strip() for a in author_str.split(",")] if author_str else []
        authors = [a for a in authors if a]

        return BookMetadata(
            title=title,
            authors=authors,
            extension="djvu",
            source="embedded",
            confidence=0.5 if title else 0.0,
            original_path=path,
        )

    def _extract_comic(self, path: Path) -> BookMetadata:
        from ebook_sorter.formats.comic import extract_metadata

        raw = extract_metadata(path)
        title = raw.get("title") or None
        series = raw.get("series") or None
        writer = raw.get("writer", "")
        authors = [a.strip() for a in writer.split(",")] if writer else []
        authors = [a for a in authors if a]
        year = None
        if raw.get("year"):
            try:
                year = int(raw["year"])
            except ValueError:
                pass
        series_index = None
        if raw.get("number"):
            try:
                series_index = float(raw["number"])
            except ValueError:
                pass

        return BookMetadata(
            title=title,
            authors=authors,
            series=series,
            series_index=series_index,
            year=year,
            extension=path.suffix.lstrip("."),
            source="embedded",
            confidence=0.5 if title else 0.0,
            original_path=path,
        )
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/extractors/test_embedded.py -v`
Expected: All PASS

- [ ] **Step 5: Commit**

```bash
git add src/ebook_sorter/extractors/embedded.py tests/extractors/test_embedded.py
git commit -m "feat: embedded metadata extractor for PDF, EPUB, MOBI, DJVU, comics"
```

---

### Task 9: Text Content Extractor & OCR Extractor

**Files:**
- Create: `src/ebook_sorter/extractors/text_content.py`
- Create: `src/ebook_sorter/extractors/ocr.py`
- Create: `tests/extractors/test_text_content.py`
- Create: `tests/extractors/test_ocr.py`

- [ ] **Step 1: Write the failing tests for text content extractor**

`tests/extractors/test_text_content.py`:
```python
from pathlib import Path

import fitz
import pytest

from ebook_sorter.extractors.text_content import TextContentExtractor


@pytest.fixture
def pdf_with_isbn(tmp_path: Path) -> Path:
    path = tmp_path / "book.pdf"
    doc = fitz.open()
    page = doc.new_page()
    page.insert_text(fitz.Point(72, 72), "ISBN 978-0-7653-1985-2")
    for i in range(4):
        p = doc.new_page()
        p.insert_text(fitz.Point(72, 72), f"Page {i + 2} content")
    doc.save(str(path))
    doc.close()
    return path


@pytest.fixture
def pdf_without_isbn(tmp_path: Path) -> Path:
    path = tmp_path / "no_isbn.pdf"
    doc = fitz.open()
    page = doc.new_page()
    page.insert_text(fitz.Point(72, 72), "Just some regular text")
    doc.save(str(path))
    doc.close()
    return path


class TestTextContentExtractor:
    def setup_method(self):
        self.extractor = TextContentExtractor()

    def test_finds_isbn_in_pdf(self, pdf_with_isbn: Path):
        meta = self.extractor.extract(pdf_with_isbn)
        assert meta.isbn_13 == "9780765319852"

    def test_no_isbn_found(self, pdf_without_isbn: Path):
        meta = self.extractor.extract(pdf_without_isbn)
        assert meta.has_isbn is False

    def test_source(self, pdf_with_isbn: Path):
        meta = self.extractor.extract(pdf_with_isbn)
        assert meta.source == "text_content"

    def test_confidence_with_isbn(self, pdf_with_isbn: Path):
        meta = self.extractor.extract(pdf_with_isbn)
        assert meta.confidence > 0.0

    def test_unsupported_format(self, tmp_path: Path):
        path = tmp_path / "file.xyz"
        path.write_text("some text with ISBN 9780765319852")
        meta = self.extractor.extract(path)
        assert meta.has_isbn is False
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/extractors/test_text_content.py -v`
Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 3: Implement text content extractor**

`src/ebook_sorter/extractors/text_content.py`:
```python
from __future__ import annotations

import logging
from pathlib import Path

from ebook_sorter.extractors.base import BaseExtractor
from ebook_sorter.isbn import find_isbns, is_valid_isbn_13
from ebook_sorter.models import BookMetadata

logger = logging.getLogger(__name__)


class TextContentExtractor(BaseExtractor):
    def __init__(self, first_pages: int = 7, last_pages: int = 3) -> None:
        self.first_pages = first_pages
        self.last_pages = last_pages

    def extract(self, path: Path) -> BookMetadata:
        ext = path.suffix.lower()
        text = ""

        try:
            if ext == ".pdf":
                from ebook_sorter.formats.pdf import extract_text

                text = extract_text(path, self.first_pages, self.last_pages)
            elif ext == ".epub":
                from ebook_sorter.formats.epub import extract_text

                text = extract_text(path)
            elif ext == ".djvu":
                from ebook_sorter.formats.djvu import extract_text

                text = extract_text(path)
            elif ext in (".mobi", ".azw", ".azw3"):
                from ebook_sorter.formats.mobi import extract_text

                text = extract_text(path)
        except Exception:
            logger.debug("Text extraction failed for %s", path, exc_info=True)

        isbns = find_isbns(text)
        isbn_10 = None
        isbn_13 = None
        for isbn in isbns:
            if len(isbn) == 13 and is_valid_isbn_13(isbn):
                isbn_13 = isbn
            elif len(isbn) == 10:
                isbn_10 = isbn

        return BookMetadata(
            isbn_10=isbn_10,
            isbn_13=isbn_13,
            extension=ext.lstrip("."),
            source="text_content",
            confidence=0.5 if (isbn_10 or isbn_13) else 0.0,
            original_path=path,
        )
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/extractors/test_text_content.py -v`
Expected: All PASS

- [ ] **Step 5: Write the failing tests for OCR extractor**

`tests/extractors/test_ocr.py`:
```python
from pathlib import Path
from unittest.mock import patch

import pytest

from ebook_sorter.extractors.ocr import OcrExtractor


class TestOcrExtractor:
    def setup_method(self):
        self.extractor = OcrExtractor()

    @patch("ebook_sorter.extractors.ocr.shutil.which", return_value=None)
    def test_returns_empty_when_tesseract_unavailable(self, mock_which, tmp_path: Path):
        path = tmp_path / "scan.pdf"
        path.write_bytes(b"%PDF-1.0 fake")
        meta = self.extractor.extract(path)
        assert meta.has_isbn is False
        assert meta.confidence == 0.0

    def test_source(self, tmp_path: Path):
        path = tmp_path / "scan.pdf"
        path.write_bytes(b"%PDF-1.0 fake")
        meta = self.extractor.extract(path)
        assert meta.source == "ocr"
```

- [ ] **Step 6: Implement OCR extractor**

`src/ebook_sorter/extractors/ocr.py`:
```python
from __future__ import annotations

import logging
import shutil
import subprocess
import tempfile
from pathlib import Path

import fitz

from ebook_sorter.extractors.base import BaseExtractor
from ebook_sorter.isbn import find_isbns, is_valid_isbn_13
from ebook_sorter.models import BookMetadata

logger = logging.getLogger(__name__)


class OcrExtractor(BaseExtractor):
    def __init__(self, first_pages: int = 7, last_pages: int = 3) -> None:
        self.first_pages = first_pages
        self.last_pages = last_pages

    def extract(self, path: Path) -> BookMetadata:
        ext = path.suffix.lower()
        if ext not in (".pdf", ".djvu") or not shutil.which("tesseract"):
            return BookMetadata(
                extension=ext.lstrip("."),
                source="ocr",
                original_path=path,
            )

        text = ""
        try:
            if ext == ".pdf":
                text = self._ocr_pdf(path)
        except Exception:
            logger.debug("OCR failed for %s", path, exc_info=True)

        isbns = find_isbns(text)
        isbn_10 = None
        isbn_13 = None
        for isbn in isbns:
            if len(isbn) == 13 and is_valid_isbn_13(isbn):
                isbn_13 = isbn
            elif len(isbn) == 10:
                isbn_10 = isbn

        return BookMetadata(
            isbn_10=isbn_10,
            isbn_13=isbn_13,
            extension=ext.lstrip("."),
            source="ocr",
            confidence=0.4 if (isbn_10 or isbn_13) else 0.0,
            original_path=path,
        )

    def _ocr_pdf(self, path: Path) -> str:
        doc = fitz.open(str(path))
        total = len(doc)
        indices: list[int] = []
        indices.extend(range(min(self.first_pages, total)))
        last_start = max(total - self.last_pages, self.first_pages)
        indices.extend(range(last_start, total))
        page_indices = sorted(set(indices))

        parts: list[str] = []
        for i in page_indices:
            page = doc[i]
            pix = page.get_pixmap(dpi=300)
            with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as f:
                img_path = Path(f.name)
                pix.save(str(img_path))
            try:
                result = subprocess.run(
                    ["tesseract", str(img_path), "stdout"],
                    capture_output=True,
                    text=True,
                    timeout=60,
                )
                parts.append(result.stdout)
            except subprocess.TimeoutExpired:
                pass
            finally:
                img_path.unlink(missing_ok=True)
        doc.close()
        return "\n".join(parts)
```

- [ ] **Step 7: Run all extractor tests**

Run: `pytest tests/extractors/ -v`
Expected: All PASS

- [ ] **Step 8: Commit**

```bash
git add src/ebook_sorter/extractors/text_content.py src/ebook_sorter/extractors/ocr.py tests/extractors/test_text_content.py tests/extractors/test_ocr.py
git commit -m "feat: text content extractor and OCR extractor"
```

---

### Task 10: Lookup Base Class & Open Library + Google Books

**Files:**
- Create: `src/ebook_sorter/lookup/base.py`
- Create: `src/ebook_sorter/lookup/openlibrary.py`
- Create: `src/ebook_sorter/lookup/google_books.py`
- Create: `tests/lookup/test_openlibrary.py`
- Create: `tests/lookup/test_google_books.py`

- [ ] **Step 1: Implement lookup base class**

`src/ebook_sorter/lookup/base.py`:
```python
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
```

- [ ] **Step 2: Write the failing tests for Open Library**

`tests/lookup/test_openlibrary.py`:
```python
import httpx
import pytest
import respx

from ebook_sorter.lookup.openlibrary import OpenLibraryLookup

ISBN_RESPONSE = {
    "ISBN:9780765319852": {
        "title": "Little Brother",
        "authors": [{"name": "Cory Doctorow"}],
        "publishers": [{"name": "Tor Books"}],
        "publish_date": "2008",
        "number_of_pages": 382,
    }
}

SEARCH_RESPONSE = {
    "docs": [
        {
            "title": "Little Brother",
            "author_name": ["Cory Doctorow"],
            "publisher": ["Tor Books"],
            "first_publish_year": 2008,
            "isbn": ["9780765319852"],
        }
    ]
}


class TestOpenLibraryLookup:
    def setup_method(self):
        self.lookup = OpenLibraryLookup()

    @respx.mock
    def test_lookup_isbn_found(self):
        respx.get("https://openlibrary.org/api/books").mock(
            return_value=httpx.Response(200, json=ISBN_RESPONSE)
        )
        meta = self.lookup.lookup_isbn("9780765319852")
        assert meta is not None
        assert meta.title == "Little Brother"
        assert "Cory Doctorow" in meta.authors
        assert meta.publisher == "Tor Books"

    @respx.mock
    def test_lookup_isbn_not_found(self):
        respx.get("https://openlibrary.org/api/books").mock(
            return_value=httpx.Response(200, json={})
        )
        meta = self.lookup.lookup_isbn("9780000000000")
        assert meta is None

    @respx.mock
    def test_search_found(self):
        respx.get("https://openlibrary.org/search.json").mock(
            return_value=httpx.Response(200, json=SEARCH_RESPONSE)
        )
        meta = self.lookup.search("Little Brother", "Cory Doctorow")
        assert meta is not None
        assert meta.title == "Little Brother"

    @respx.mock
    def test_search_not_found(self):
        respx.get("https://openlibrary.org/search.json").mock(
            return_value=httpx.Response(200, json={"docs": []})
        )
        meta = self.lookup.search("Nonexistent Book")
        assert meta is None

    @respx.mock
    def test_lookup_isbn_confidence(self):
        respx.get("https://openlibrary.org/api/books").mock(
            return_value=httpx.Response(200, json=ISBN_RESPONSE)
        )
        meta = self.lookup.lookup_isbn("9780765319852")
        assert meta is not None
        assert meta.confidence == 0.95
        assert meta.source == "openlibrary"
```

- [ ] **Step 3: Run tests to verify they fail**

Run: `pytest tests/lookup/test_openlibrary.py -v`
Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 4: Implement Open Library lookup**

`src/ebook_sorter/lookup/openlibrary.py`:
```python
from __future__ import annotations

import logging
import re

import httpx

from ebook_sorter.isbn import find_isbns, is_valid_isbn_13
from ebook_sorter.lookup.base import BaseLookup
from ebook_sorter.models import BookMetadata

logger = logging.getLogger(__name__)

_BASE = "https://openlibrary.org"


class OpenLibraryLookup(BaseLookup):
    def __init__(self, timeout: float = 15.0) -> None:
        self._timeout = timeout

    def lookup_isbn(self, isbn: str) -> BookMetadata | None:
        try:
            resp = httpx.get(
                f"{_BASE}/api/books",
                params={
                    "bibkeys": f"ISBN:{isbn}",
                    "format": "json",
                    "jscmd": "data",
                },
                timeout=self._timeout,
            )
            resp.raise_for_status()
            data = resp.json()
        except (httpx.HTTPError, ValueError):
            logger.debug("Open Library ISBN lookup failed for %s", isbn, exc_info=True)
            return None

        key = f"ISBN:{isbn}"
        if key not in data:
            return None

        book = data[key]
        return self._parse_book(book, isbn)

    def search(self, title: str, author: str = "") -> BookMetadata | None:
        query = title
        if author:
            query = f"{title} {author}"
        try:
            resp = httpx.get(
                f"{_BASE}/search.json",
                params={"q": query, "limit": 5},
                timeout=self._timeout,
            )
            resp.raise_for_status()
            data = resp.json()
        except (httpx.HTTPError, ValueError):
            logger.debug("Open Library search failed for %s", query, exc_info=True)
            return None

        docs = data.get("docs", [])
        if not docs:
            return None

        doc = docs[0]
        isbn_13 = None
        isbn_10 = None
        for raw_isbn in doc.get("isbn", []):
            for found in find_isbns(raw_isbn):
                if len(found) == 13 and is_valid_isbn_13(found):
                    isbn_13 = isbn_13 or found
                elif len(found) == 10:
                    isbn_10 = isbn_10 or found

        year = doc.get("first_publish_year")

        return BookMetadata(
            title=doc.get("title"),
            authors=doc.get("author_name", []),
            isbn_13=isbn_13,
            isbn_10=isbn_10,
            publisher=(doc.get("publisher") or [None])[0],
            year=year,
            source="openlibrary",
            confidence=0.7,
        )

    def _parse_book(self, book: dict, isbn: str) -> BookMetadata:
        authors = [a["name"] for a in book.get("authors", [])]
        publishers = [p["name"] for p in book.get("publishers", [])]
        year = None
        pub_date = book.get("publish_date", "")
        year_match = re.search(r"\d{4}", pub_date)
        if year_match:
            year = int(year_match.group())

        isbn_13 = isbn if len(isbn) == 13 else None
        isbn_10 = isbn if len(isbn) == 10 else None

        return BookMetadata(
            title=book.get("title"),
            authors=authors,
            isbn_13=isbn_13,
            isbn_10=isbn_10,
            publisher=publishers[0] if publishers else None,
            year=year,
            source="openlibrary",
            confidence=0.95,
        )
```

- [ ] **Step 5: Run Open Library tests**

Run: `pytest tests/lookup/test_openlibrary.py -v`
Expected: All PASS

- [ ] **Step 6: Write the failing tests for Google Books**

`tests/lookup/test_google_books.py`:
```python
import httpx
import pytest
import respx

from ebook_sorter.lookup.google_books import GoogleBooksLookup

VOLUME_RESPONSE = {
    "totalItems": 1,
    "items": [
        {
            "volumeInfo": {
                "title": "Little Brother",
                "authors": ["Cory Doctorow"],
                "publisher": "Tor Books",
                "publishedDate": "2008-04-29",
                "industryIdentifiers": [
                    {"type": "ISBN_13", "identifier": "9780765319852"},
                    {"type": "ISBN_10", "identifier": "0765319853"},
                ],
                "language": "en",
            }
        }
    ],
}


class TestGoogleBooksLookup:
    def setup_method(self):
        self.lookup = GoogleBooksLookup()

    @respx.mock
    def test_lookup_isbn(self):
        respx.get("https://www.googleapis.com/books/v1/volumes").mock(
            return_value=httpx.Response(200, json=VOLUME_RESPONSE)
        )
        meta = self.lookup.lookup_isbn("9780765319852")
        assert meta is not None
        assert meta.title == "Little Brother"
        assert "Cory Doctorow" in meta.authors
        assert meta.isbn_13 == "9780765319852"
        assert meta.confidence == 0.95

    @respx.mock
    def test_lookup_isbn_not_found(self):
        respx.get("https://www.googleapis.com/books/v1/volumes").mock(
            return_value=httpx.Response(200, json={"totalItems": 0})
        )
        meta = self.lookup.lookup_isbn("9780000000000")
        assert meta is None

    @respx.mock
    def test_search(self):
        respx.get("https://www.googleapis.com/books/v1/volumes").mock(
            return_value=httpx.Response(200, json=VOLUME_RESPONSE)
        )
        meta = self.lookup.search("Little Brother", "Cory Doctorow")
        assert meta is not None
        assert meta.title == "Little Brother"
        assert meta.source == "google_books"

    @respx.mock
    def test_search_not_found(self):
        respx.get("https://www.googleapis.com/books/v1/volumes").mock(
            return_value=httpx.Response(200, json={"totalItems": 0})
        )
        meta = self.lookup.search("Nonexistent Book")
        assert meta is None
```

- [ ] **Step 7: Implement Google Books lookup**

`src/ebook_sorter/lookup/google_books.py`:
```python
from __future__ import annotations

import logging
import re

import httpx

from ebook_sorter.lookup.base import BaseLookup
from ebook_sorter.models import BookMetadata

logger = logging.getLogger(__name__)

_BASE = "https://www.googleapis.com/books/v1/volumes"


class GoogleBooksLookup(BaseLookup):
    def __init__(self, timeout: float = 15.0) -> None:
        self._timeout = timeout

    def lookup_isbn(self, isbn: str) -> BookMetadata | None:
        return self._query(f"isbn:{isbn}", is_isbn_lookup=True)

    def search(self, title: str, author: str = "") -> BookMetadata | None:
        query = f'intitle:"{title}"'
        if author:
            query += f' inauthor:"{author}"'
        return self._query(query, is_isbn_lookup=False)

    def _query(self, q: str, is_isbn_lookup: bool) -> BookMetadata | None:
        try:
            resp = httpx.get(
                _BASE,
                params={"q": q, "maxResults": 5},
                timeout=self._timeout,
            )
            resp.raise_for_status()
            data = resp.json()
        except (httpx.HTTPError, ValueError):
            logger.debug("Google Books query failed: %s", q, exc_info=True)
            return None

        if data.get("totalItems", 0) == 0 or "items" not in data:
            return None

        vol = data["items"][0]["volumeInfo"]
        isbn_10 = None
        isbn_13 = None
        for ident in vol.get("industryIdentifiers", []):
            if ident["type"] == "ISBN_13":
                isbn_13 = ident["identifier"]
            elif ident["type"] == "ISBN_10":
                isbn_10 = ident["identifier"]

        year = None
        pub_date = vol.get("publishedDate", "")
        year_match = re.search(r"\d{4}", pub_date)
        if year_match:
            year = int(year_match.group())

        return BookMetadata(
            title=vol.get("title"),
            authors=vol.get("authors", []),
            isbn_10=isbn_10,
            isbn_13=isbn_13,
            publisher=vol.get("publisher"),
            year=year,
            language=vol.get("language"),
            source="google_books",
            confidence=0.95 if is_isbn_lookup else 0.7,
        )
```

- [ ] **Step 8: Run all lookup tests**

Run: `pytest tests/lookup/ -v`
Expected: All PASS

- [ ] **Step 9: Commit**

```bash
git add src/ebook_sorter/lookup/ tests/lookup/
git commit -m "feat: Open Library and Google Books metadata lookup"
```

---

### Task 11: Calibre CLI Lookup

**Files:**
- Create: `src/ebook_sorter/lookup/calibre.py`
- Create: `tests/lookup/test_calibre.py`

- [ ] **Step 1: Write the failing tests**

`tests/lookup/test_calibre.py`:
```python
from pathlib import Path
from unittest.mock import patch

import pytest

from ebook_sorter.lookup.calibre import CalibreLookup

FETCH_OUTPUT = """Title               : Little Brother
Author(s)           : Cory Doctorow
Publisher           : Tor Books
Tags                : fiction, technology
Published           : 2008-04-29T00:00:00+00:00
ISBN                : 9780765319852
"""


class TestCalibreLookup:
    def setup_method(self):
        self.lookup = CalibreLookup()

    @patch("ebook_sorter.lookup.calibre.shutil.which", return_value=None)
    def test_unavailable(self, mock_which):
        meta = self.lookup.lookup_isbn("9780765319852")
        assert meta is None

    @patch("ebook_sorter.lookup.calibre.shutil.which", return_value="/usr/bin/fetch-ebook-metadata")
    @patch("ebook_sorter.lookup.calibre.subprocess.run")
    def test_lookup_isbn(self, mock_run, mock_which):
        mock_run.return_value.stdout = FETCH_OUTPUT
        mock_run.return_value.returncode = 0
        meta = self.lookup.lookup_isbn("9780765319852")
        assert meta is not None
        assert meta.title == "Little Brother"
        assert "Cory Doctorow" in meta.authors
        assert meta.source == "calibre"

    @patch("ebook_sorter.lookup.calibre.shutil.which", return_value="/usr/bin/fetch-ebook-metadata")
    @patch("ebook_sorter.lookup.calibre.subprocess.run")
    def test_lookup_isbn_not_found(self, mock_run, mock_which):
        mock_run.return_value.stdout = ""
        mock_run.return_value.returncode = 1
        meta = self.lookup.lookup_isbn("9780000000000")
        assert meta is None

    @patch("ebook_sorter.lookup.calibre.shutil.which", return_value="/usr/bin/fetch-ebook-metadata")
    @patch("ebook_sorter.lookup.calibre.subprocess.run")
    def test_search(self, mock_run, mock_which):
        mock_run.return_value.stdout = FETCH_OUTPUT
        mock_run.return_value.returncode = 0
        meta = self.lookup.search("Little Brother", "Cory Doctorow")
        assert meta is not None
        assert meta.title == "Little Brother"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/lookup/test_calibre.py -v`
Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 3: Implement Calibre lookup**

`src/ebook_sorter/lookup/calibre.py`:
```python
from __future__ import annotations

import logging
import re
import shutil
import subprocess

from ebook_sorter.lookup.base import BaseLookup
from ebook_sorter.models import BookMetadata

logger = logging.getLogger(__name__)


def _parse_fetch_output(output: str) -> dict[str, str]:
    result: dict[str, str] = {}
    for line in output.splitlines():
        if ":" in line:
            key, _, value = line.partition(":")
            key = key.strip().lower()
            value = value.strip()
            if key and value:
                result[key] = value
    return result


class CalibreLookup(BaseLookup):
    def __init__(self, timeout: float = 60.0) -> None:
        self._timeout = timeout

    def _is_available(self) -> bool:
        return shutil.which("fetch-ebook-metadata") is not None

    def lookup_isbn(self, isbn: str) -> BookMetadata | None:
        if not self._is_available():
            return None
        return self._fetch(["--isbn", isbn])

    def search(self, title: str, author: str = "") -> BookMetadata | None:
        if not self._is_available():
            return None
        args = ["--title", title]
        if author:
            args.extend(["--author", author])
        return self._fetch(args)

    def _fetch(self, extra_args: list[str]) -> BookMetadata | None:
        cmd = ["fetch-ebook-metadata"] + extra_args
        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=self._timeout,
            )
        except subprocess.TimeoutExpired:
            logger.debug("Calibre fetch timed out: %s", cmd)
            return None

        if result.returncode != 0 or not result.stdout.strip():
            return None

        parsed = _parse_fetch_output(result.stdout)
        if not parsed.get("title"):
            return None

        author_str = parsed.get("author(s)", "")
        authors = [a.strip() for a in re.split(r"[,&]", author_str)] if author_str else []
        authors = [a for a in authors if a]

        year = None
        pub_date = parsed.get("published", "")
        year_match = re.search(r"\d{4}", pub_date)
        if year_match:
            year = int(year_match.group())

        isbn = parsed.get("isbn")
        isbn_10 = None
        isbn_13 = None
        if isbn:
            if len(isbn) == 13:
                isbn_13 = isbn
            elif len(isbn) == 10:
                isbn_10 = isbn

        return BookMetadata(
            title=parsed.get("title"),
            authors=authors,
            isbn_10=isbn_10,
            isbn_13=isbn_13,
            publisher=parsed.get("publisher"),
            year=year,
            source="calibre",
            confidence=0.9,
        )
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/lookup/test_calibre.py -v`
Expected: All PASS

- [ ] **Step 5: Commit**

```bash
git add src/ebook_sorter/lookup/calibre.py tests/lookup/test_calibre.py
git commit -m "feat: Calibre CLI metadata lookup wrapper"
```

---

### Task 12: Pipeline Orchestrator

**Files:**
- Create: `src/ebook_sorter/pipeline.py`
- Create: `tests/test_pipeline.py`

- [ ] **Step 1: Write the failing tests**

`tests/test_pipeline.py`:
```python
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from ebook_sorter.extractors.base import BaseExtractor
from ebook_sorter.lookup.base import BaseLookup
from ebook_sorter.models import BookMetadata
from ebook_sorter.pipeline import Pipeline


class FakeExtractor(BaseExtractor):
    def __init__(self, result: BookMetadata):
        self._result = result

    def extract(self, path: Path) -> BookMetadata:
        return self._result


class FakeLookup(BaseLookup):
    def __init__(self, result: BookMetadata | None = None):
        self._result = result

    def lookup_isbn(self, isbn: str) -> BookMetadata | None:
        return self._result

    def search(self, title: str, author: str = "") -> BookMetadata | None:
        return self._result


def test_pipeline_isbn_found_and_looked_up():
    extractor = FakeExtractor(BookMetadata(isbn_13="9780765319852", confidence=0.5))
    lookup = FakeLookup(BookMetadata(
        title="Little Brother",
        authors=["Cory Doctorow"],
        isbn_13="9780765319852",
        confidence=0.95,
        source="openlibrary",
    ))
    pipeline = Pipeline(extractors=[extractor], lookups=[lookup])
    result = pipeline.process(Path("/fake/book.pdf"))
    assert result.title == "Little Brother"
    assert result.isbn_13 == "9780765319852"
    assert result.confidence == 0.95


def test_pipeline_no_isbn_searches_by_title():
    extractor = FakeExtractor(BookMetadata(
        title="Little Brother",
        authors=["Cory Doctorow"],
        confidence=0.4,
    ))
    lookup = FakeLookup(BookMetadata(
        title="Little Brother",
        authors=["Cory Doctorow"],
        isbn_13="9780765319852",
        confidence=0.7,
        source="openlibrary",
    ))
    pipeline = Pipeline(extractors=[extractor], lookups=[lookup])
    result = pipeline.process(Path("/fake/book.pdf"))
    assert result.isbn_13 == "9780765319852"
    assert result.confidence == 0.7


def test_pipeline_merges_extractor_results():
    ext1 = FakeExtractor(BookMetadata(title="Little Brother", confidence=0.3))
    ext2 = FakeExtractor(BookMetadata(authors=["Cory Doctorow"], confidence=0.4))
    pipeline = Pipeline(extractors=[ext1, ext2], lookups=[])
    result = pipeline.process(Path("/fake/book.pdf"))
    assert result.title == "Little Brother"
    assert result.authors == ["Cory Doctorow"]


def test_pipeline_no_results():
    extractor = FakeExtractor(BookMetadata())
    pipeline = Pipeline(extractors=[extractor], lookups=[])
    result = pipeline.process(Path("/fake/book.pdf"))
    assert result.title is None
    assert result.confidence == 0.0


def test_pipeline_lookup_fallback():
    extractor = FakeExtractor(BookMetadata(isbn_13="9780765319852"))
    lookup1 = FakeLookup(None)
    lookup2 = FakeLookup(BookMetadata(
        title="Little Brother",
        isbn_13="9780765319852",
        confidence=0.95,
    ))
    pipeline = Pipeline(extractors=[extractor], lookups=[lookup1, lookup2])
    result = pipeline.process(Path("/fake/book.pdf"))
    assert result.title == "Little Brother"


def test_pipeline_stops_lookup_on_first_hit():
    extractor = FakeExtractor(BookMetadata(isbn_13="9780765319852"))
    lookup1 = FakeLookup(BookMetadata(title="First Result", confidence=0.95))
    lookup2 = FakeLookup(BookMetadata(title="Second Result", confidence=0.95))
    pipeline = Pipeline(extractors=[extractor], lookups=[lookup1, lookup2])
    result = pipeline.process(Path("/fake/book.pdf"))
    assert result.title == "First Result"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_pipeline.py -v`
Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 3: Implement pipeline**

`src/ebook_sorter/pipeline.py`:
```python
from __future__ import annotations

import logging
from pathlib import Path

from ebook_sorter.extractors.base import BaseExtractor
from ebook_sorter.lookup.base import BaseLookup
from ebook_sorter.models import BookMetadata

logger = logging.getLogger(__name__)


class Pipeline:
    def __init__(
        self,
        extractors: list[BaseExtractor],
        lookups: list[BaseLookup],
    ) -> None:
        self.extractors = extractors
        self.lookups = lookups

    def process(self, path: Path) -> BookMetadata:
        merged = BookMetadata(original_path=path, extension=path.suffix.lstrip("."))

        for extractor in self.extractors:
            try:
                result = extractor.extract(path)
                merged = merged.merge(result)
            except Exception:
                logger.debug(
                    "Extractor %s failed on %s",
                    type(extractor).__name__,
                    path,
                    exc_info=True,
                )

        if merged.has_isbn:
            isbn = merged.isbn
            lookup_result = self._lookup_isbn(isbn)
            if lookup_result:
                merged = merged.merge(lookup_result)
        elif merged.title:
            author_str = ", ".join(merged.authors) if merged.authors else ""
            lookup_result = self._search(merged.title, author_str)
            if lookup_result:
                merged = merged.merge(lookup_result)

        return merged

    def _lookup_isbn(self, isbn: str) -> BookMetadata | None:
        for lookup in self.lookups:
            try:
                result = lookup.lookup_isbn(isbn)
                if result and result.title:
                    return result
            except Exception:
                logger.debug(
                    "Lookup %s failed for ISBN %s",
                    type(lookup).__name__,
                    isbn,
                    exc_info=True,
                )
        return None

    def _search(self, title: str, author: str) -> BookMetadata | None:
        for lookup in self.lookups:
            try:
                result = lookup.search(title, author)
                if result and result.title:
                    return result
            except Exception:
                logger.debug(
                    "Search %s failed for %s / %s",
                    type(lookup).__name__,
                    title,
                    author,
                    exc_info=True,
                )
        return None
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_pipeline.py -v`
Expected: All PASS

- [ ] **Step 5: Commit**

```bash
git add src/ebook_sorter/pipeline.py tests/test_pipeline.py
git commit -m "feat: pipeline orchestrator chaining extractors and lookup sources"
```

---

### Task 13: Config Module

**Files:**
- Create: `src/ebook_sorter/config.py`
- Create: `tests/test_config.py`

- [ ] **Step 1: Write the failing tests**

`tests/test_config.py`:
```python
from pathlib import Path

import pytest

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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_config.py -v`
Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 3: Implement config module**

`src/ebook_sorter/config.py`:
```python
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

    return Config(**kwargs)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_config.py -v`
Expected: All PASS

- [ ] **Step 5: Commit**

```bash
git add src/ebook_sorter/config.py tests/test_config.py
git commit -m "feat: TOML config loading with sensible defaults"
```

---

### Task 14: Organizer (Template Engine + File Operations)

**Files:**
- Create: `src/ebook_sorter/organizer.py`
- Create: `tests/test_organizer.py`

- [ ] **Step 1: Write the failing tests**

`tests/test_organizer.py`:
```python
from pathlib import Path

import pytest

from ebook_sorter.models import BookMetadata
from ebook_sorter.organizer import Organizer


class TestRenderFilename:
    def setup_method(self):
        self.organizer = Organizer(
            output_dir=Path("/output"),
            filename_template="{authors} - {title} ({year}) [{isbn}].{ext}",
            folder_template="{authors}",
        )

    def test_full_metadata(self):
        meta = BookMetadata(
            title="Little Brother",
            authors=["Cory Doctorow"],
            isbn_13="9780765319852",
            year=2008,
            extension="pdf",
        )
        filename = self.organizer.render_filename(meta)
        assert filename == "Cory Doctorow - Little Brother (2008) [9780765319852].pdf"

    def test_missing_year(self):
        meta = BookMetadata(
            title="Little Brother",
            authors=["Cory Doctorow"],
            isbn_13="9780765319852",
            extension="pdf",
        )
        filename = self.organizer.render_filename(meta)
        assert filename == "Cory Doctorow - Little Brother () [9780765319852].pdf"

    def test_sanitizes_filename(self):
        meta = BookMetadata(
            title="What/Is: This?",
            authors=["Author"],
            extension="pdf",
        )
        filename = self.organizer.render_filename(meta)
        assert "/" not in filename
        assert ":" not in filename
        assert "?" not in filename


class TestRenderPath:
    def test_with_folder_template(self):
        organizer = Organizer(
            output_dir=Path("/output"),
            filename_template="{title}.{ext}",
            folder_template="{authors}",
        )
        meta = BookMetadata(
            title="Little Brother",
            authors=["Cory Doctorow"],
            extension="pdf",
        )
        result = organizer.render_path(meta)
        assert result == Path("/output/Cory Doctorow/Little Brother.pdf")


class TestMoveFile:
    def test_move_file(self, tmp_path: Path):
        src = tmp_path / "source" / "book.pdf"
        src.parent.mkdir()
        src.write_text("fake pdf content")

        out = tmp_path / "output"
        out.mkdir()

        organizer = Organizer(
            output_dir=out,
            filename_template="{title}.{ext}",
            folder_template="",
        )
        meta = BookMetadata(
            title="Renamed",
            extension="pdf",
            original_path=src,
        )
        dest = organizer.move_file(meta)
        assert dest.exists()
        assert dest.name == "Renamed.pdf"
        assert not src.exists()

    def test_move_file_dry_run(self, tmp_path: Path):
        src = tmp_path / "book.pdf"
        src.write_text("fake pdf content")

        out = tmp_path / "output"
        out.mkdir()

        organizer = Organizer(
            output_dir=out,
            filename_template="{title}.{ext}",
            folder_template="",
            dry_run=True,
        )
        meta = BookMetadata(title="Renamed", extension="pdf", original_path=src)
        dest = organizer.move_file(meta)
        assert src.exists()
        assert not dest.exists()

    def test_move_file_handles_collision(self, tmp_path: Path):
        out = tmp_path / "output"
        out.mkdir()
        existing = out / "Book.pdf"
        existing.write_text("existing")

        src = tmp_path / "book.pdf"
        src.write_text("new content")

        organizer = Organizer(
            output_dir=out,
            filename_template="{title}.{ext}",
            folder_template="",
        )
        meta = BookMetadata(title="Book", extension="pdf", original_path=src)
        dest = organizer.move_file(meta)
        assert dest.exists()
        assert dest.name == "Book (2).pdf"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_organizer.py -v`
Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 3: Implement organizer**

`src/ebook_sorter/organizer.py`:
```python
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
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_organizer.py -v`
Expected: All PASS

- [ ] **Step 5: Commit**

```bash
git add src/ebook_sorter/organizer.py tests/test_organizer.py
git commit -m "feat: organizer with template rendering and collision handling"
```

---

### Task 15: CLI Subcommands

**Files:**
- Create: `src/ebook_sorter/cli.py`
- Create: `tests/test_cli.py`

- [ ] **Step 1: Write the failing tests**

`tests/test_cli.py`:
```python
from pathlib import Path

import fitz
import pytest
from click.testing import CliRunner

from ebook_sorter.cli import cli


@pytest.fixture
def runner():
    return CliRunner()


@pytest.fixture
def ebook_folder(tmp_path: Path) -> Path:
    folder = tmp_path / "ebooks"
    folder.mkdir()
    doc = fitz.open()
    doc.set_metadata({"title": "Test Book", "author": "Test Author"})
    page = doc.new_page()
    page.insert_text(fitz.Point(72, 72), "ISBN 978-0-7653-1985-2")
    doc.save(str(folder / "test.pdf"))
    doc.close()
    return folder


def test_cli_help(runner: CliRunner):
    result = runner.invoke(cli, ["--help"])
    assert result.exit_code == 0
    assert "ebook-sorter" in result.output.lower() or "Usage" in result.output


def test_cli_scan(runner: CliRunner, ebook_folder: Path):
    result = runner.invoke(cli, ["scan", str(ebook_folder)])
    assert result.exit_code == 0


def test_cli_find_isbn(runner: CliRunner, ebook_folder: Path):
    pdf = ebook_folder / "test.pdf"
    result = runner.invoke(cli, ["find-isbn", str(pdf)])
    assert result.exit_code == 0
    assert "9780765319852" in result.output


def test_cli_identify(runner: CliRunner, ebook_folder: Path):
    pdf = ebook_folder / "test.pdf"
    result = runner.invoke(cli, ["identify", str(pdf)])
    assert result.exit_code == 0


def test_cli_organize_dry_run(runner: CliRunner, ebook_folder: Path, tmp_path: Path):
    out_dir = tmp_path / "output"
    out_dir.mkdir()
    result = runner.invoke(cli, [
        "organize", str(ebook_folder),
        "--output-dir", str(out_dir),
        "--dry-run",
    ])
    assert result.exit_code == 0
    assert (ebook_folder / "test.pdf").exists()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_cli.py -v`
Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 3: Implement CLI**

`src/ebook_sorter/cli.py`:
```python
from __future__ import annotations

import logging
from pathlib import Path

import click
from rich.console import Console
from rich.table import Table

from ebook_sorter.config import Config, load_config
from ebook_sorter.extractors.embedded import EmbeddedExtractor
from ebook_sorter.extractors.filename import FilenameExtractor
from ebook_sorter.extractors.ocr import OcrExtractor
from ebook_sorter.extractors.text_content import TextContentExtractor
from ebook_sorter.isbn import find_isbns
from ebook_sorter.lookup.calibre import CalibreLookup
from ebook_sorter.lookup.google_books import GoogleBooksLookup
from ebook_sorter.lookup.openlibrary import OpenLibraryLookup
from ebook_sorter.models import BookMetadata
from ebook_sorter.organizer import Organizer
from ebook_sorter.pipeline import Pipeline

console = Console()

EBOOK_EXTENSIONS = {
    ".pdf", ".epub", ".mobi", ".azw", ".azw3",
    ".djvu", ".cbr", ".cbz", ".chm", ".doc", ".docx", ".odt",
}


def _build_pipeline(cfg: Config) -> Pipeline:
    extractors = [
        FilenameExtractor(),
        EmbeddedExtractor(),
        TextContentExtractor(cfg.ocr_first_pages, cfg.ocr_last_pages),
    ]
    if cfg.ocr_enabled:
        extractors.append(OcrExtractor(cfg.ocr_first_pages, cfg.ocr_last_pages))
    lookups = [
        OpenLibraryLookup(),
        GoogleBooksLookup(),
        CalibreLookup(),
    ]
    return Pipeline(extractors=extractors, lookups=lookups)


def _find_ebooks(folder: Path) -> list[Path]:
    files: list[Path] = []
    for path in sorted(folder.rglob("*")):
        if path.is_file() and path.suffix.lower() in EBOOK_EXTENSIONS:
            files.append(path)
    return files


@click.group()
@click.option("--config", "config_path", type=click.Path(exists=False), default="ebook-sorter.toml")
@click.option("-v", "--verbose", is_flag=True)
@click.pass_context
def cli(ctx: click.Context, config_path: str, verbose: bool) -> None:
    """Organize ebook collections by extracting metadata."""
    cfg = load_config(Path(config_path))
    cfg.verbose = verbose
    if verbose:
        logging.basicConfig(level=logging.DEBUG)
    ctx.ensure_object(dict)
    ctx.obj["config"] = cfg


@cli.command()
@click.argument("folder", type=click.Path(exists=True))
@click.pass_context
def scan(ctx: click.Context, folder: str) -> None:
    """Scan a folder and report metadata found (dry-run)."""
    cfg: Config = ctx.obj["config"]
    pipeline = _build_pipeline(cfg)
    files = _find_ebooks(Path(folder))

    table = Table(title=f"Scan: {folder}")
    table.add_column("File", style="cyan")
    table.add_column("Title")
    table.add_column("Author(s)")
    table.add_column("ISBN")
    table.add_column("Confidence", justify="right")

    for path in files:
        meta = pipeline.process(path)
        table.add_row(
            path.name,
            meta.title or "—",
            ", ".join(meta.authors) if meta.authors else "—",
            meta.isbn or "—",
            f"{meta.confidence:.2f}",
        )

    console.print(table)


@cli.command("find-isbn")
@click.argument("file", type=click.Path(exists=True))
def find_isbn_cmd(file: str) -> None:
    """Find ISBNs in a single file."""
    path = Path(file)
    ext = path.suffix.lower()

    isbns_found: list[str] = []

    isbns_found.extend(find_isbns(path.stem))

    try:
        if ext == ".pdf":
            from ebook_sorter.formats.pdf import extract_text
            text = extract_text(path)
            isbns_found.extend(find_isbns(text))
        elif ext == ".epub":
            from ebook_sorter.formats.epub import extract_text
            text = extract_text(path)
            isbns_found.extend(find_isbns(text))
    except Exception as e:
        console.print(f"[yellow]Warning: {e}[/yellow]")

    seen: set[str] = set()
    unique: list[str] = []
    for isbn in isbns_found:
        if isbn not in seen:
            seen.add(isbn)
            unique.append(isbn)

    if unique:
        for isbn in unique:
            console.print(isbn)
    else:
        console.print("[yellow]No ISBNs found.[/yellow]")


@cli.command()
@click.argument("file", type=click.Path(exists=True))
@click.pass_context
def identify(ctx: click.Context, file: str) -> None:
    """Show full metadata extraction for one file."""
    cfg: Config = ctx.obj["config"]
    pipeline = _build_pipeline(cfg)
    meta = pipeline.process(Path(file))

    table = Table(title=f"Identify: {Path(file).name}")
    table.add_column("Field", style="bold")
    table.add_column("Value")

    table.add_row("Title", meta.title or "—")
    table.add_row("Author(s)", ", ".join(meta.authors) if meta.authors else "—")
    table.add_row("ISBN-10", meta.isbn_10 or "—")
    table.add_row("ISBN-13", meta.isbn_13 or "—")
    table.add_row("Publisher", meta.publisher or "—")
    table.add_row("Year", str(meta.year) if meta.year else "—")
    table.add_row("Series", meta.series or "—")
    table.add_row("Language", meta.language or "—")
    table.add_row("Source", meta.source)
    table.add_row("Confidence", f"{meta.confidence:.2f}")

    console.print(table)


@cli.command()
@click.argument("folder", type=click.Path(exists=True))
@click.option("-o", "--output-dir", type=click.Path(), default=None)
@click.option("-t", "--template", default=None)
@click.option("--folder-template", default=None)
@click.option("--confidence-threshold", type=float, default=None)
@click.option("--ocr/--no-ocr", "ocr_enabled", default=None)
@click.option("--dry-run", is_flag=True, default=False)
@click.option("--corrupt-dir", type=click.Path(), default=None)
@click.option("--uncertain-dir", type=click.Path(), default=None)
@click.pass_context
def organize(
    ctx: click.Context,
    folder: str,
    output_dir: str | None,
    template: str | None,
    folder_template: str | None,
    confidence_threshold: float | None,
    ocr_enabled: bool | None,
    dry_run: bool,
    corrupt_dir: str | None,
    uncertain_dir: str | None,
) -> None:
    """Scan and organize ebooks by renaming and moving them."""
    cfg: Config = ctx.obj["config"]

    if output_dir:
        cfg.output_dir = Path(output_dir)
    if template:
        cfg.filename_template = template
    if folder_template:
        cfg.folder_template = folder_template
    if confidence_threshold is not None:
        cfg.confidence_threshold = confidence_threshold
    if ocr_enabled is not None:
        cfg.ocr_enabled = ocr_enabled
    if dry_run:
        cfg.dry_run = True
    if corrupt_dir:
        cfg.corrupt_dir = Path(corrupt_dir)
    if uncertain_dir:
        cfg.uncertain_dir = Path(uncertain_dir)

    pipeline = _build_pipeline(cfg)
    organizer = Organizer(
        output_dir=cfg.output_dir,
        filename_template=cfg.filename_template,
        folder_template=cfg.folder_template,
        dry_run=cfg.dry_run,
    )

    files = _find_ebooks(Path(folder))
    organized = 0
    uncertain = 0
    failed = 0

    for path in files:
        try:
            meta = pipeline.process(path)
            meta.original_path = path

            if meta.confidence >= cfg.confidence_threshold and meta.title:
                dest = organizer.move_file(meta)
                action = "DRY RUN" if cfg.dry_run else "Moved"
                console.print(f"[green]{action}:[/green] {path.name} -> {dest}")
                organized += 1
            elif cfg.uncertain_dir and meta.title:
                uncertain_organizer = Organizer(
                    output_dir=cfg.uncertain_dir,
                    filename_template=cfg.filename_template,
                    folder_template=cfg.folder_template,
                    dry_run=cfg.dry_run,
                )
                dest = uncertain_organizer.move_file(meta)
                console.print(f"[yellow]Uncertain:[/yellow] {path.name} -> {dest}")
                uncertain += 1
            else:
                console.print(f"[red]Skipped:[/red] {path.name} (confidence: {meta.confidence:.2f})")
                uncertain += 1
        except Exception as e:
            console.print(f"[red]Error:[/red] {path.name}: {e}")
            failed += 1

    console.print(f"\nOrganized: {organized}, Uncertain: {uncertain}, Failed: {failed}")
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_cli.py -v`
Expected: All PASS

- [ ] **Step 5: Commit**

```bash
git add src/ebook_sorter/cli.py tests/test_cli.py
git commit -m "feat: Click CLI with scan, find-isbn, identify, and organize commands"
```

---

### Task 16: Interactive TUI

**Files:**
- Create: `src/ebook_sorter/interactive.py`

This task involves interactive terminal UI which is hard to unit test. Implementation is verified manually.

- [ ] **Step 1: Implement interactive TUI**

`src/ebook_sorter/interactive.py`:
```python
from __future__ import annotations

from pathlib import Path

from rich.console import Console
from rich.panel import Panel
from rich.prompt import Prompt
from rich.table import Table

from ebook_sorter.lookup.base import BaseLookup
from ebook_sorter.models import BookMetadata
from ebook_sorter.organizer import Organizer

console = Console()


def review_loop(
    uncertain_files: list[tuple[Path, BookMetadata]],
    organizer: Organizer,
    lookups: list[BaseLookup],
) -> None:
    total = len(uncertain_files)
    for i, (path, meta) in enumerate(uncertain_files, 1):
        console.print(f"\n[bold]File {i}/{total}[/bold]")
        _show_file(path, meta, organizer)
        action = _prompt_action()

        if action == "a":
            dest = organizer.move_file(meta)
            console.print(f"[green]Moved:[/green] {dest}")
        elif action == "e":
            meta = _edit_metadata(meta)
            dest = organizer.move_file(meta)
            console.print(f"[green]Moved:[/green] {dest}")
        elif action == "s":
            meta = _manual_search(meta, lookups)
            if meta.title:
                _show_file(path, meta, organizer)
                confirm = Prompt.ask("Accept this?", choices=["y", "n"], default="y")
                if confirm == "y":
                    dest = organizer.move_file(meta)
                    console.print(f"[green]Moved:[/green] {dest}")
        elif action == "k":
            console.print("[dim]Skipped.[/dim]")
        elif action == "n":
            console.print("[dim]Marked as non-book.[/dim]")
        elif action == "q":
            console.print("[bold]Exiting review.[/bold]")
            break


def _show_file(path: Path, meta: BookMetadata, organizer: Organizer) -> None:
    table = Table(show_header=False, box=None)
    table.add_column("Field", style="bold", width=15)
    table.add_column("Value")
    table.add_row("Original", str(path))
    table.add_row("Title", meta.title or "—")
    table.add_row("Author(s)", ", ".join(meta.authors) if meta.authors else "—")
    table.add_row("ISBN", meta.isbn or "—")
    table.add_row("Year", str(meta.year) if meta.year else "—")
    table.add_row("Source", meta.source)
    table.add_row("Confidence", f"{meta.confidence:.2f}")
    table.add_row("Proposed", organizer.render_filename(meta))
    console.print(Panel(table, title="Review"))


def _prompt_action() -> str:
    return Prompt.ask(
        "[a]ccept  [e]dit  [s]earch  s[k]ip  [n]on-book  [q]uit",
        choices=["a", "e", "s", "k", "n", "q"],
        default="a",
    )


def _edit_metadata(meta: BookMetadata) -> BookMetadata:
    title = Prompt.ask("Title", default=meta.title or "")
    authors_str = Prompt.ask(
        "Authors (comma-separated)",
        default=", ".join(meta.authors) if meta.authors else "",
    )
    isbn = Prompt.ask("ISBN", default=meta.isbn or "")
    year_str = Prompt.ask("Year", default=str(meta.year) if meta.year else "")

    authors = [a.strip() for a in authors_str.split(",") if a.strip()]
    year = int(year_str) if year_str.isdigit() else None

    isbn_10 = isbn if len(isbn) == 10 else meta.isbn_10
    isbn_13 = isbn if len(isbn) == 13 else meta.isbn_13

    return BookMetadata(
        title=title or None,
        authors=authors,
        isbn_10=isbn_10,
        isbn_13=isbn_13,
        publisher=meta.publisher,
        year=year,
        series=meta.series,
        series_index=meta.series_index,
        language=meta.language,
        source="manual",
        confidence=1.0,
        original_path=meta.original_path,
        extension=meta.extension,
    )


def _manual_search(meta: BookMetadata, lookups: list[BaseLookup]) -> BookMetadata:
    query = Prompt.ask("Enter ISBN or title to search")
    from ebook_sorter.isbn import find_isbns

    isbns = find_isbns(query)
    for lookup in lookups:
        try:
            if isbns:
                result = lookup.lookup_isbn(isbns[0])
            else:
                result = lookup.search(query)
            if result and result.title:
                result.original_path = meta.original_path
                result.extension = meta.extension
                return result
        except Exception:
            continue
    console.print("[yellow]No results found.[/yellow]")
    return meta
```

- [ ] **Step 2: Wire interactive command into CLI**

Add to `src/ebook_sorter/cli.py` — append this command after the `organize` command:

```python
@cli.command()
@click.argument("folder", type=click.Path(exists=True))
@click.option("-o", "--output-dir", type=click.Path(), default=None)
@click.option("-t", "--template", default=None)
@click.option("--folder-template", default=None)
@click.pass_context
def interactive(
    ctx: click.Context,
    folder: str,
    output_dir: str | None,
    template: str | None,
    folder_template: str | None,
) -> None:
    """Launch interactive TUI for reviewing uncertain matches."""
    from ebook_sorter.interactive import review_loop

    cfg: Config = ctx.obj["config"]
    if output_dir:
        cfg.output_dir = Path(output_dir)
    if template:
        cfg.filename_template = template
    if folder_template:
        cfg.folder_template = folder_template

    pipeline = _build_pipeline(cfg)
    organizer = Organizer(
        output_dir=cfg.output_dir,
        filename_template=cfg.filename_template,
        folder_template=cfg.folder_template,
    )

    files = _find_ebooks(Path(folder))
    uncertain: list[tuple[Path, BookMetadata]] = []

    for path in files:
        meta = pipeline.process(path)
        meta.original_path = path
        uncertain.append((path, meta))

    if not uncertain:
        console.print("[green]No files to review.[/green]")
        return

    lookups = [OpenLibraryLookup(), GoogleBooksLookup(), CalibreLookup()]
    review_loop(uncertain, organizer, lookups)
```

- [ ] **Step 3: Verify CLI help includes interactive command**

Run: `ebook-sorter --help`
Expected: output lists `interactive` subcommand

- [ ] **Step 4: Commit**

```bash
git add src/ebook_sorter/interactive.py src/ebook_sorter/cli.py
git commit -m "feat: interactive TUI for reviewing uncertain ebook matches"
```

---

### Task 17: Integration Test & Final Wiring

**Files:**
- Modify: `tests/conftest.py`
- Create: `tests/test_integration.py`

- [ ] **Step 1: Write integration test**

`tests/test_integration.py`:
```python
from pathlib import Path

import fitz
import pytest
from ebooklib import epub

from ebook_sorter.config import Config
from ebook_sorter.organizer import Organizer
from ebook_sorter.pipeline import Pipeline
from ebook_sorter.extractors.filename import FilenameExtractor
from ebook_sorter.extractors.embedded import EmbeddedExtractor
from ebook_sorter.extractors.text_content import TextContentExtractor


@pytest.fixture
def sample_library(tmp_path: Path) -> Path:
    lib = tmp_path / "library"
    lib.mkdir()

    doc = fitz.open()
    doc.set_metadata({"title": "Integration Test Book", "author": "Test Author"})
    page = doc.new_page()
    page.insert_text(fitz.Point(72, 72), "Some content on page 1")
    doc.save(str(lib / "messy_filename.pdf"))
    doc.close()

    book = epub.EpubBook()
    book.set_identifier("test-id")
    book.set_title("EPUB Integration Book")
    book.set_language("en")
    book.add_author("EPUB Writer")
    ch = epub.EpubHtml(title="Ch1", file_name="ch1.xhtml", lang="en")
    ch.content = b"<html><body><p>Hello world</p></body></html>"
    book.add_item(ch)
    book.add_item(epub.EpubNcx())
    book.add_item(epub.EpubNav())
    book.spine = ["nav", ch]
    epub.write_epub(str(lib / "another_book.epub"), book)

    return lib


def test_full_pipeline_extracts_metadata(sample_library: Path):
    pipeline = Pipeline(
        extractors=[
            FilenameExtractor(),
            EmbeddedExtractor(),
            TextContentExtractor(),
        ],
        lookups=[],
    )
    pdf = sample_library / "messy_filename.pdf"
    meta = pipeline.process(pdf)
    assert meta.title == "Integration Test Book"
    assert "Test Author" in meta.authors


def test_full_pipeline_epub(sample_library: Path):
    pipeline = Pipeline(
        extractors=[
            FilenameExtractor(),
            EmbeddedExtractor(),
            TextContentExtractor(),
        ],
        lookups=[],
    )
    ep = sample_library / "another_book.epub"
    meta = pipeline.process(ep)
    assert meta.title == "EPUB Integration Book"
    assert "EPUB Writer" in meta.authors


def test_organize_end_to_end(sample_library: Path, tmp_path: Path):
    output = tmp_path / "output"
    output.mkdir()

    pipeline = Pipeline(
        extractors=[
            FilenameExtractor(),
            EmbeddedExtractor(),
            TextContentExtractor(),
        ],
        lookups=[],
    )
    organizer = Organizer(
        output_dir=output,
        filename_template="{authors} - {title}.{ext}",
        folder_template="",
    )

    pdf = sample_library / "messy_filename.pdf"
    meta = pipeline.process(pdf)
    meta.original_path = pdf
    dest = organizer.move_file(meta)

    assert dest.exists()
    assert "Test Author" in dest.name
    assert "Integration Test Book" in dest.name
    assert not pdf.exists()
```

- [ ] **Step 2: Run integration tests**

Run: `pytest tests/test_integration.py -v`
Expected: All PASS

- [ ] **Step 3: Run full test suite**

Run: `pytest tests/ -v`
Expected: All PASS

- [ ] **Step 4: Commit**

```bash
git add tests/test_integration.py
git commit -m "feat: integration tests for full pipeline and organize flow"
```

- [ ] **Step 5: Final verification — run the CLI**

Run: `ebook-sorter --help`
Expected: shows all subcommands (scan, find-isbn, identify, organize, interactive)

Run: `ebook-sorter scan /tmp` (or any folder with a test PDF)
Expected: table output with metadata

```bash
git add -A
git commit -m "chore: final wiring and cleanup"
```
