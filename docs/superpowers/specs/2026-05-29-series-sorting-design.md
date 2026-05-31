# Series Sorting & Sibling Metadata Design

**Date:** 2026-05-29
**Branch:** fix-isbn-text-extraction → targeting main

## Overview

Two related features:

1. **`author_sort` template variable** — a "Last, First" sort key for the primary/canonical author of a series, with pre-populated defaults for common multi-author and legacy-continuation series, and per-series TOML overrides.
2. **Sibling file metadata borrowing** — during scan/sort, files sharing the same stem in the same directory (e.g., `book.mobi` and `book.epub`) merge their extracted metadata so each file benefits from whatever the richest sibling knows.

Together these enable folder layouts like `{author_sort}/{series}` that sort multi-author series coherently.

---

## Feature 1: `author_sort` field

### Data model (`models.py`)

Add field to `BookMetadata`:
```python
author_sort: str | None = None
```

Add to `merge()` — prefer non-None, prefer higher-confidence side on conflict (same logic as other fields via `pick()`).

Add `_derive_author_sort(name: str) -> str` module-level helper:
- If name contains `,` → already in "Last, First" form, return as-is
- Split on last space: `"Neil Gaiman"` → `"Gaiman, Neil"`, `"James S.A. Corey"` → `"Corey, James S.A."`
- Single-word name → return as-is

Add `{author_sort}` and `{series_index_padded}` to `template_dict()`:
- `author_sort`: if `self.author_sort` set → use it; else if authors → `_derive_author_sort(self.authors[0])`; else `""`
- `series_index_padded`: `series_index` zero-padded to 2 digits (e.g. `1` → `"01"`, `10` → `"10"`); empty string if no series_index. Needed because `series_index` is a string in the template dict, so Python format specs like `{series_index:02d}` won't work.

### Config (`config.py`)

New field:
```python
series_author_sort: dict[str, str] = field(default_factory=dict)
```

Module-level defaults dict `_DEFAULT_SERIES_AUTHOR_SORT` (merged at load time; user TOML wins on conflict):

```python
_DEFAULT_SERIES_AUTHOR_SORT: dict[str, str] = {
    # Pen names
    "The Expanse": "Corey, James S.A.",
    "Warriors": "Hunter, Erin",
    "Seekers": "Hunter, Erin",
    "Survivors": "Hunter, Erin",
    "Bravelands": "Hunter, Erin",
    "Dawn of the Clans": "Hunter, Erin",
    "A Vision of Shadows": "Hunter, Erin",
    "The Broken Code": "Hunter, Erin",
    "A Starless Clan": "Hunter, Erin",
    # Legacy continuations — sort under original author
    "Wheel of Time": "Jordan, Robert",
    "Dune": "Herbert, Frank",
    "Dune Chronicles": "Herbert, Frank",
    "Foundation": "Asimov, Isaac",
    "Robot": "Asimov, Isaac",
    "Dragonriders of Pern": "McCaffrey, Anne",
    "Pern": "McCaffrey, Anne",
    "The Hitchhiker's Guide to the Galaxy": "Adams, Douglas",
    "Hitchhiker's Guide to the Galaxy": "Adams, Douglas",
    "Dark Tower": "King, Stephen",
    "Valdemar": "Lackey, Mercedes",
    "Heralds of Valdemar": "Lackey, Mercedes",
    "Darkover": "Bradley, Marion Zimmer",
    # Co-written series (no pen name)
    "Good Omens": "Pratchett, Terry",
    "Dragonlance": "Weis, Margaret",
    "Dragonlance Chronicles": "Weis, Margaret",
    "Dragonlance Legends": "Weis, Margaret",
    "Liaden Universe": "Lee, Sharon",
    "Empire of Man": "Ringo, John",
    "Prince Roger": "Ringo, John",
    # Tom Clancy brand universe
    "Jack Ryan": "Clancy, Tom",
    "John Clark": "Clancy, Tom",
    "The Campus": "Clancy, Tom",
    "Net Force": "Clancy, Tom",
    "Op-Center": "Clancy, Tom",
    "Power Plays": "Clancy, Tom",
    # Shared-world anthologies
    "Wild Cards": "Martin, George R.R.",
    "1632": "Flint, Eric",
    "Ring of Fire": "Flint, Eric",
    "Man-Kzin Wars": "Niven, Larry",
    "Thieves' World": "Asprin, Robert",
    "MythAdventures": "Asprin, Robert",
}
```

TOML format for user overrides:
```toml
[ebook-sorter.series_author_sort]
"The Expanse" = "Corey, James S.A."
"My Custom Series" = "Smith, John"
```

Load logic in `load_config()`:
```python
user_overrides = section.get("series_author_sort", {})
kwargs["series_author_sort"] = {**_DEFAULT_SERIES_AUTHOR_SORT, **user_overrides}
```

When no config file exists: `Config()` default is `{}`, but `load_config()` always populates defaults, so direct `Config()` construction (in tests) gets an empty dict — acceptable.

### Resolution in CLI

After pipeline extraction and before organizing, call:
```python
def _resolve_author_sort(meta: BookMetadata, series_author_sort: dict[str, str]) -> BookMetadata:
    if meta.author_sort:
        return meta  # already set (e.g. by a future extractor)
    if meta.series and meta.series in series_author_sort:
        meta.author_sort = series_author_sort[meta.series]
    # else: template_dict() auto-derives from authors[0]
    return meta
```

Applied in both `scan` and `sort` commands after `meta` is assembled.

### Sidecar persistence (`sidecar.py`)

Add `"author_sort"` to `_SERIALIZED_FIELDS`. `read_sidecar()` populates `author_sort=data.get("author_sort")`. Backward-compatible: old sidecars without the field yield `None`, which falls back to auto-derivation.

---

## Feature 2: Sibling file metadata borrowing

### Grouping logic (CLI)

Replace the flat per-file loop with stem-group processing in both `scan` and `sort` commands.

```python
def _group_by_stem(files: list[Path]) -> dict[tuple[Path, str], list[Path]]:
    groups: dict[tuple[Path, str], list[Path]] = {}
    for f in files:
        key = (f.parent, f.stem)
        groups.setdefault(key, []).append(f)
    return groups
```

### Merge logic

```python
def _process_stem_group(
    paths: list[Path],
    pipeline: Pipeline,
    cfg: Config,
) -> dict[Path, BookMetadata]:
    """Extract metadata for each path, merge across siblings, return per-path results."""
    per_path: dict[Path, BookMetadata] = {}
    for path in paths:
        meta = read_sidecar(path)
        if meta is None:
            meta = pipeline.process(path)
        meta.original_path = path
        meta.extension = path.suffix.lstrip(".")
        per_path[path] = meta

    if len(per_path) == 1:
        return per_path  # fast path, no siblings

    # Merge all into a combined result
    combined = BookMetadata()
    for m in per_path.values():
        combined = combined.merge(m)

    # Each file gets the combined metadata but keeps its own path/extension
    result = {}
    for path, original_meta in per_path.items():
        merged = BookMetadata(
            **{f.name: getattr(combined, f.name) for f in fields(combined)}
        )
        merged.original_path = path
        merged.extension = path.suffix.lstrip(".")
        result[path] = merged
    return result
```

Key rules:
- Sidecar checked first per file (existing behavior preserved)
- Only same-dir, same-stem files are siblings
- No API lookups on siblings (pipeline uses extractors only for siblings, not the lookup chain) — actually since the full pipeline is run on each file independently, lookups would fire. To avoid doubling API calls, we should only run the extraction pipeline (without lookups) on siblings when the current file's metadata is already enriched by lookups. **Revised rule**: if the current file already has a sidecar, skip sibling extraction entirely (sidecar data is already the best known state). Sibling borrowing only applies to fresh (no-sidecar) files.
- After a successful `scan`, sidecars are written with the merged metadata so future runs skip re-extraction.

### Revised sibling rule

```python
def _process_stem_group(...):
    # Phase 1: check sidecars
    sidecar_results = {p: read_sidecar(p) for p in paths}
    
    # If ALL have sidecars, no sibling work needed
    if all(v is not None for v in sidecar_results.values()):
        result = {}
        for path, meta in sidecar_results.items():
            meta.original_path = path
            meta.extension = path.suffix.lstrip(".")
            result[path] = meta
        return result
    
    # Phase 2: extract for each file (pipeline for no-sidecar, sidecar data for others)
    per_path = {}
    for path in paths:
        if sidecar_results[path] is not None:
            meta = sidecar_results[path]
        else:
            meta = pipeline.process(path)
        meta.original_path = path
        meta.extension = path.suffix.lstrip(".")
        per_path[path] = meta
    
    if len(per_path) == 1:
        return per_path
    
    # Phase 3: merge across all siblings
    combined = BookMetadata()
    for m in per_path.values():
        combined = combined.merge(m)
    
    # Phase 4: each file keeps own path/extension, gets combined metadata
    # (uses `from copy import copy` and `from dataclasses import fields`)
    result = {}
    for path in paths:
        m = copy(combined)
        m.original_path = path
        m.extension = path.suffix.lstrip(".")
        result[path] = m
    return result
```

---

## Organizer: nested folder template paths (`organizer.py`)

`_sanitize()` replaces `/` with `_`, collapsing `{author_sort}/{series}` to a single directory. Fix `render_path()` to split on `/` first:

```python
def render_path(self, meta: BookMetadata) -> Path:
    d = meta.template_dict()
    segments = []
    if self.folder_template:
        for segment in self.folder_template.split("/"):
            rendered = _sanitize(segment.format_map(d))
            if rendered:  # skip empty segments (e.g. {series} when no series)
                segments.append(rendered)
    filename = self.render_filename(meta)
    return self.output_dir.joinpath(*segments, filename)
```

Empty segment skipping means books without series automatically collapse one directory level:
- With series: `output/Corey, James S.A./The Expanse/book.epub`
- Without series: `output/Gaiman, Neil/book.epub`

Backward-compatible: `"{authors}"` has no `/`, so single-segment behavior is unchanged.

---

## Files to change

| File | Change |
|------|--------|
| `src/ebook_sorter/models.py` | Add `author_sort` field, `_derive_author_sort()`, update `merge()` and `template_dict()` (adds `{author_sort}`, `{series_index_padded}`) |
| `src/ebook_sorter/config.py` | Add `series_author_sort` field, `_DEFAULT_SERIES_AUTHOR_SORT`, update `load_config()` |
| `src/ebook_sorter/sidecar.py` | Add `author_sort` to `_SERIALIZED_FIELDS`, update `read_sidecar()` |
| `src/ebook_sorter/organizer.py` | Fix `render_path()` to split folder template on `/` |
| `src/ebook_sorter/cli.py` | Add `_group_by_stem()`, `_process_stem_group()`, `_resolve_author_sort()`; update `scan` and `sort` loops |
| `tests/test_models.py` | Tests for `author_sort` field, `_derive_author_sort()` |
| `tests/test_organizer.py` | Tests for nested folder template paths |
| `tests/test_config.py` | Tests for `series_author_sort` defaults and TOML override |
| `tests/test_sidecar.py` | Tests for `author_sort` round-trip |

---

## Example config after this change

```toml
[ebook-sorter]
output_dir = "/media/books"
folder_template = "{author_sort}/{series}"
filename_template = "{series_index_padded} - {title} ({year}).{ext}"
confidence_threshold = 0.7

[ebook-sorter.series_author_sort]
"My Custom Series" = "Doe, Jane"
```

Result layout:
```
/media/books/
  Corey, James S.A./
    The Expanse/
      01 - Leviathan Wakes (2011).epub
      02 - Caliban's War (2012).epub
  Jordan, Robert/
    Wheel of Time/
      01 - The Eye of the World (1990).epub
      14 - A Memory of Light (2013).epub   ← Sanderson book, still under Jordan
  Gaiman, Neil/
    American Gods (2001).epub              ← no series, collapses one level
```
