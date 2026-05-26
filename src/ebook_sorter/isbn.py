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


def isbn_13_to_10(isbn_13: str) -> str | None:
    """Derive ISBN-10 from a 978-prefixed ISBN-13.

    Only works for ISBN-13s starting with '978' (not '979').
    Returns None if the input doesn't start with 978.
    """
    normalized = normalize_isbn(isbn_13)
    if not normalized.startswith("978") or len(normalized) != 13:
        return None
    base = normalized[3:12]
    total = 0
    for i, ch in enumerate(base):
        total += int(ch) * (10 - i)
    check_digit = (11 - total % 11) % 11
    if check_digit == 10:
        return base + "X"
    return base + str(check_digit)


_ISBN_PATTERN = re.compile(
    r"(?:ISBN[-\s]?(?:1[03])?[-:\s]*)?"
    r"((?:97[89][-\s]?)?(?:\d[-\s]?){9}[\dXx])",
    re.IGNORECASE,
)

# Pattern that is guaranteed to have an "ISBN" prefix before the number.
_ISBN_PREFIXED_PATTERN = re.compile(
    r"ISBN[-\s]?(?:1[03])?[-:\s]*"
    r"((?:97[89][-\s]?)?(?:\d[-\s]?){9}[\dXx])",
    re.IGNORECASE,
)


def _is_valid_isbn(normalized: str) -> bool:
    if len(normalized) == 13 and is_valid_isbn_13(normalized):
        return True
    if len(normalized) == 10 and is_valid_isbn_10(normalized):
        return True
    return False


def find_isbns(text: str) -> list[str]:
    candidates = _ISBN_PATTERN.findall(text)
    valid: list[str] = []
    for raw in candidates:
        normalized = normalize_isbn(raw)
        if _is_valid_isbn(normalized):
            if normalized not in valid:
                valid.append(normalized)
    return valid


def find_isbns_prefixed(text: str) -> list[str]:
    """Return ISBNs whose match included the 'ISBN' prefix (high confidence)."""
    valid: list[str] = []
    for m in _ISBN_PREFIXED_PATTERN.finditer(text):
        raw = m.group(1)
        normalized = normalize_isbn(raw)
        if _is_valid_isbn(normalized) and normalized not in valid:
            valid.append(normalized)
    return valid


def find_isbns_with_context(text: str) -> tuple[list[str], list[str]]:
    """Return (prefixed, bare) ISBNs separately.

    *prefixed* — ISBNs that appeared with an 'ISBN' label (e.g. "ISBN 978-0-321-93190-0").
      These are high confidence real ISBNs, typically from the copyright page.
    *bare* — bare number matches that happen to pass checksum validation.
      These may include false positives from page/equation numbering.
    Both lists are in order of appearance in the text.
    """
    prefixed_set: set[str] = set()
    prefixed: list[str] = []
    bare: list[str] = []

    for m in _ISBN_PATTERN.finditer(text):
        full = m.group(0)
        raw = m.group(1)
        normalized = normalize_isbn(raw)
        if not _is_valid_isbn(normalized):
            continue

        has_prefix = bool(re.search(r"\bISBN", full, re.IGNORECASE))
        if has_prefix:
            if normalized not in prefixed_set:
                prefixed_set.add(normalized)
                prefixed.append(normalized)
        else:
            if normalized not in prefixed_set:
                prefixed_set.add(normalized)
                bare.append(normalized)

    return prefixed, bare
