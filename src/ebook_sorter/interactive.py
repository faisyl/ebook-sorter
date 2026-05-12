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
