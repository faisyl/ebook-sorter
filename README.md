# ebook-sorter

A Python CLI tool for organizing ebook collections by extracting metadata (title, ISBN, author, etc.) from book files and using it to rename and move them into a structured library.

Inspired by [na--/ebook-tools](https://github.com/na--/ebook-tools), reimplemented in Python with direct API integrations and a modular pipeline architecture.

## Features

- **Format support**: PDF, EPUB, DJVU, MOBI/AZW, CBR/CBZ
- **ISBN detection**: regex scanning of filenames, embedded metadata, and page content
- **Metadata lookup**: Open Library, Google Books, and Calibre CLI (no API keys needed)
- **OCR fallback**: optional Tesseract OCR for scanned PDFs/DJVUs
- **Configurable output**: customizable filename and folder templates
- **Interactive review**: TUI for manually reviewing uncertain matches
- **Confidence scoring**: auto-organizes high-confidence matches, flags uncertain ones

## Installation

```bash
pip install .
```

### Optional system dependencies

These are detected at runtime and used when available:

| Tool | Purpose |
|---|---|
| [Tesseract](https://github.com/tesseract-ocr/tesseract) | OCR for scanned books |
| [Calibre](https://calibre-ebook.com/) | metadata extraction and format conversion |
| [djvulibre](http://djvu.sourceforge.net/) | DJVU text extraction |
| [7-Zip](https://www.7-zip.org/) | archive extraction for EPUB/CBZ/CBR internals |

## Usage

```bash
# Scan a folder and preview extracted metadata
ebook-sorter scan /path/to/ebooks

# Organize (rename + move) ebooks into an output folder
ebook-sorter organize /path/to/ebooks -o /path/to/library

# Dry run (show what would happen without moving files)
ebook-sorter organize /path/to/ebooks -o /path/to/library --dry-run

# Find ISBNs in a single file
ebook-sorter find-isbn book.pdf

# Show full metadata extraction for one file
ebook-sorter identify book.epub

# Interactive review of uncertain matches
ebook-sorter interactive /path/to/ebooks -o /path/to/library
```

## Docker

```bash
# Build
docker build -t ebook-sorter .

# Run (mount your ebook folder as /data)
docker run --rm -v /path/to/ebooks:/data ebook-sorter scan /data

# Organize into a mounted output directory
docker run --rm \
  -v /path/to/ebooks:/data \
  -v /path/to/library:/output \
  ebook-sorter organize /data -o /output
```

Pre-built images are available from GHCR when the repository is configured on GitHub.

## Configuration

All CLI options can be set in an `ebook-sorter.toml` file:

```toml
[ebook-sorter]
output_dir = "/path/to/library"
filename_template = "{authors} - {title} ({year}) [{isbn}].{ext}"
folder_template = "{authors}"
confidence_threshold = 0.7
ocr_enabled = false
```

CLI arguments override config file values.

### Template variables

`{authors}`, `{title}`, `{year}`, `{isbn}`, `{isbn13}`, `{publisher}`, `{series}`, `{series_index}`, `{ext}`, `{language}`

### Output options

| Option | Default | Description |
|---|---|---|
| `--output-dir` / `-o` | current directory | Destination folder |
| `--template` / `-t` | `{authors} - {title} ({year}) [{isbn}].{ext}` | Filename template |
| `--folder-template` | `{authors}` | Folder structure template |
| `--confidence-threshold` | `0.7` | Min confidence for auto-organize |
| `--ocr / --no-ocr` | `--no-ocr` | Enable Tesseract OCR |
| `--dry-run` | off | Preview without moving files |
| `--corrupt-dir` | none | Move corrupt files here |
| `--uncertain-dir` | none | Move uncertain matches here |

## How it works

The tool runs a pipeline of extractors in order, stopping when a confident match is found:

1. **Filename parsing** - extract ISBN, author, title, year from the filename
2. **Embedded metadata** - read PDF properties, EPUB OPF, MOBI headers, ComicInfo.xml
3. **Text extraction** - convert first/last pages to text, scan for ISBNs
4. **OCR** (optional) - Tesseract fallback for scanned documents

When an ISBN is found, it's looked up via Open Library, Google Books, then Calibre. When no ISBN is found, extracted title/author tokens are searched online.

Results are scored by confidence (0.0-1.0). Files above the threshold are auto-organized; files below are skipped or queued for interactive review.

## Development

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
pytest
```

## License

This project is licensed under the GNU General Public License v2.0. See [LICENSE](LICENSE) for details.
