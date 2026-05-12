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
from ebook_sorter.sidecar import read_sidecar, write_sidecar

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
        GoogleBooksLookup(api_key=cfg.google_books_api_key),
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
@click.option("--sidecar/--no-sidecar", default=False, help="Write .metadata.json sidecar files next to each ebook.")
@click.pass_context
def scan(ctx: click.Context, folder: str, sidecar: bool) -> None:
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
        if sidecar:
            write_sidecar(meta, path)

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
@click.option("--sidecar/--no-sidecar", default=False, help="Use/write .metadata.json sidecar files.")
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
    sidecar: bool,
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
            meta = None
            if sidecar:
                meta = read_sidecar(path)
                if meta:
                    console.print(f"[dim]Using sidecar:[/dim] {path.name}")
            if meta is None:
                meta = pipeline.process(path)
            meta.original_path = path
            meta.extension = path.suffix.lstrip(".")

            if meta.confidence >= cfg.confidence_threshold and meta.title:
                dest = organizer.move_file(meta)
                if sidecar and not cfg.dry_run:
                    write_sidecar(meta, dest)
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
