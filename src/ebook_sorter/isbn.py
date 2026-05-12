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
