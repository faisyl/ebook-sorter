# ebook-sorter Design Specification

A Python CLI tool for organizing ebook collections by extracting metadata (title, ISBN, author, etc.) from book files and using it to rename and move them into a structured library.

Inspired by [na--/ebook-tools](https://github.com/na--/ebook-tools) but reimplemented in Python with direct API integrations and a modular pipeline architecture.

## Requirements

- **Formats**: PDF, EPUB, DJVU, MOBI/AZW, CBR/CBZ, and any format Calibre can handle as a fallback
- **Metadata lookup**: Open Library + Google Books APIs (no API key), with Calibre CLI as optional fallback
- **Identification without ISBN**: embedded file metadata, first/last page text extraction, filename token parsing
- **Interface**: CLI with subcommands for batch operations, plus an interactive TUI for reviewing uncertain matches
- **Output**: configurable filename and folder templates
- **OCR**: optional Tesseract fallback for scanned PDFs/DJVUs
- **Python**: 3.11+

## Architecture: Modular Pipeline

Each stage of identification is a standalone module. A pipeline orchestrator chains them, stopping when a confident match is found.

```
File → [Filename Check] → [Embedded Metadata] → [Text Extraction] → [OCR] → [ISBN Lookup / Title Search] → [Rename/Move]
```

## Project Structure

```
ebook-sorter/
├── pyproject.toml
├── src/
│   └── ebook_sorter/
│       ├── __init__.py
│       ├── cli.py                  # Click-based CLI with subcommands
│       ├── config.py               # Configuration loading (TOML/CLI args)
│       ├── models.py               # BookMetadata dataclass, confidence scoring
│       ├── pipeline.py             # Orchestrator that chains extractors
│       ├── extractors/
│       │   ├── __init__.py
│       │   ├── base.py             # Abstract base extractor
│       │   ├── filename.py         # Parse author/title/ISBN from filename
│       │   ├── embedded.py         # Read embedded metadata (PDF props, EPUB OPF, etc.)
│       │   ├── text_content.py     # Extract text from first/last pages, search for ISBN
│       │   └── ocr.py              # Tesseract OCR fallback
│       ├── isbn.py                 # ISBN detection, validation, and normalization
│       ├── lookup/
│       │   ├── __init__.py
│       │   ├── base.py             # Abstract metadata lookup source
│       │   ├── openlibrary.py      # Open Library API
│       │   ├── google_books.py     # Google Books API
│       │   └── calibre.py          # Calibre CLI wrapper (fetch-ebook-metadata)
│       ├── organizer.py            # Rename/move logic with template engine
│       ├── interactive.py          # TUI for reviewing uncertain matches
│       └── formats/
│           ├── __init__.py
│           ├── pdf.py              # PDF text extraction (pymupdf)
│           ├── epub.py             # EPUB text/metadata extraction (ebooklib)
│           ├── djvu.py             # DJVU handling
│           ├── mobi.py             # MOBI/AZW handling
│           └── comic.py            # CBR/CBZ handling
└── tests/
```

## Data Model

```python
@dataclass
class BookMetadata:
    title: str | None
    authors: list[str]
    isbn_10: str | None
    isbn_13: str | None
    publisher: str | None
    year: int | None
    series: str | None
    series_index: float | None
    language: str | None
    source: str              # which lookup/extractor produced this
    confidence: float        # 0.0-1.0, how confident we are in the match
    original_path: Path
    extension: str
```

## Pipeline Execution Order

The pipeline runs extractors in order, stopping when a confident match is found:

1. **Filename extractor** — parse ISBN from filename, tokenize for author/title
2. **Embedded metadata extractor** — read PDF properties, EPUB OPF, MOBI headers
3. **Text content extractor** — convert first N / last M pages to text, regex for ISBNs
4. **OCR extractor** (if enabled, and text extraction yielded nothing)
5. If ISBN found at any stage → **lookup sources** (Open Library → Google Books → Calibre)
6. If no ISBN → use extracted author/title tokens to search lookup sources
7. **Confidence scoring** — if confidence >= threshold, auto-organize; if below, queue for interactive review

## Confidence Scoring

| Scenario | Confidence |
|---|---|
| ISBN match with full metadata found online | 0.95 |
| Embedded metadata matches online result | 0.85 |
| OCR-derived ISBN with metadata found | 0.80 |
| Filename-derived title matches online result | 0.70 |
| Filename only, no online confirmation | 0.40 |

Configurable threshold (default **0.7**) determines what gets auto-organized vs. queued for interactive review.

## CLI Interface

### Subcommands

```
ebook-sorter scan <folder>          # Scan and report what was found (dry-run)
ebook-sorter organize <folder>      # Scan + rename/move files
ebook-sorter find-isbn <file>       # Find ISBNs in a single file
ebook-sorter identify <file>        # Show full metadata extraction for one file
ebook-sorter interactive <folder>   # Launch TUI for reviewing uncertain matches
```

### Global Options

| Option | Short | Default | Description |
|---|---|---|---|
| `--output-dir` | `-o` | cwd | Destination folder for organized files |
| `--template` | `-t` | `{authors} - {title} ({year}) [{isbn}].{ext}` | Output filename template |
| `--folder-template` | | `{authors}` | Output folder structure template |
| `--confidence-threshold` | | `0.7` | Min confidence for auto-organize |
| `--ocr / --no-ocr` | | `--no-ocr` | Enable/disable Tesseract OCR |
| `--ocr-pages` | | `7,3` | First/last pages to OCR |
| `--dry-run` | | off | Show what would happen without moving files |
| `--config` | | `ebook-sorter.toml` | Path to TOML config file |
| `--verbose` | `-v` | off | Increase logging verbosity |
| `--corrupt-dir` | | none | Move corrupt files here |
| `--uncertain-dir` | | none | Move uncertain matches here |

### Template Variables

`{authors}`, `{title}`, `{year}`, `{isbn}`, `{isbn13}`, `{publisher}`, `{series}`, `{series_index}`, `{ext}`, `{language}`

### Config File

`ebook-sorter.toml` mirrors all CLI options so users don't have to repeat flags. CLI args override config file values.

## Interactive TUI

When files fall below the confidence threshold, the interactive mode (using `rich`) presents each one for review:

- Shows the original filename and path
- Shows extracted metadata (what was found and by which extractor)
- Shows the proposed new name based on the template
- Actions: **Accept**, **Edit metadata**, **Search manually** (enter ISBN/title), **Skip**, **Mark as non-book**

## Error Handling

- **Corrupt files**: detected via failed text extraction or archive test (`7z t`). Moved to `--corrupt-dir` if specified, otherwise logged and skipped.
- **Duplicate ISBNs**: if two files resolve to the same book, append a counter to the filename.
- **Name collisions**: check destination before moving; if exists, auto-suffix with counter.
- **Missing dependencies**: at startup, check which optional tools are available (Calibre, Tesseract, djvutxt, 7z) and adjust pipeline accordingly. Warn but don't fail.
- **Rate limiting**: respect API rate limits with exponential backoff for Open Library / Google Books.
- **Atomic moves**: move files only after all metadata is resolved, never leave files in a half-moved state.

## Dependencies

### Python (pip)

| Package | Purpose |
|---|---|
| `click` | CLI framework |
| `pymupdf` | PDF text extraction and metadata |
| `ebooklib` | EPUB parsing |
| `isbnlib` | ISBN validation, normalization, basic lookup |
| `httpx` | Async HTTP for API calls |
| `rich` | TUI, progress bars, formatted output |
| `tomli` / `tomllib` | Config file parsing (stdlib in 3.11+) |

### System Tools (optional, detected at runtime)

| Tool | Purpose |
|---|---|
| `tesseract` | OCR for scanned PDFs/DJVUs |
| `calibre` | `ebook-meta`, `ebook-convert`, `fetch-ebook-metadata` |
| `djvutxt` | DJVU text extraction |
| `7z` | Archive extraction for EPUB/CHM/CBZ/CBR internals |

## Testing Strategy

- **Unit tests**: ISBN regex/validation, filename parsing, template rendering, confidence scoring
- **Integration tests**: sample ebook files as test fixtures, full extractor runs
- **Mock-based tests**: API lookup responses (Open Library, Google Books)
- **End-to-end test**: scan a folder of test files, verify output filenames and folder structure
