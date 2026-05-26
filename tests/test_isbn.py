from ebook_sorter.isbn import (
    find_isbns,
    find_isbns_prefixed,
    find_isbns_with_context,
    is_valid_isbn_10,
    is_valid_isbn_13,
    isbn_10_to_13,
    isbn_13_to_10,
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


class TestFindIsbnsPrefixed:
    def test_finds_prefixed_isbn(self):
        text = "ISBN 978-0-7653-1985-2, also see 1234567890"
        result = find_isbns_prefixed(text)
        assert "9780765319852" in result
        assert "1234567890" not in result  # bare number without prefix

    def test_prefixed_isbn_all_formats(self):
        text = "ISBN: 9780765319852 and ISBN-10: 0765319853 and ISBN-13: 9780765319852"
        result = find_isbns_prefixed(text)
        assert "9780765319852" in result
        assert "0765319853" in result

    def test_no_prefixed_no_match(self):
        text = "Just a number 9780765319852 without label"
        assert find_isbns_prefixed(text) == []

    def test_empty_text(self):
        assert find_isbns_prefixed("") == []


class TestFindIsbnsWithContext:
    def test_prefixed_and_bare_separated(self):
        text = "ISBN 9780765319852 is real, but 1292057696 might not be"
        prefixed, bare = find_isbns_with_context(text)
        assert "9780765319852" in prefixed
        assert "1292057696" in bare

    def test_prefixed_only(self):
        text = "ISBN-10: 0765319853"
        prefixed, bare = find_isbns_with_context(text)
        assert "0765319853" in prefixed
        assert bare == []

    def test_bare_only(self):
        text = "Found number 9780765319852 in the wild"
        prefixed, bare = find_isbns_with_context(text)
        assert "9780765319852" in bare
        assert prefixed == []

    def test_no_isbns(self):
        text = "No numbers here at all"
        prefixed, bare = find_isbns_with_context(text)
        assert prefixed == []
        assert bare == []

    def test_deduplicates_across_groups(self):
        text = "ISBN 9780765319852 and bare 9780765319852"
        prefixed, bare = find_isbns_with_context(text)
        assert "9780765319852" in prefixed
        assert "9780765319852" not in bare  # deduplicated from bare

    def test_orders_preserved(self):
        text = "bare 1292057696 then ISBN 9780765319852 then bare 0765319853"
        prefixed, bare = find_isbns_with_context(text)
        assert bare == ["1292057696", "0765319853"]
        assert prefixed == ["9780765319852"]


class TestIsbn13To10:
    def test_converts_978(self):
        assert isbn_13_to_10("9780765319852") == "0765319853"

    def test_returns_none_for_979(self):
        assert isbn_13_to_10("9791032305690") is None

    def test_returns_none_wrong_length(self):
        assert isbn_13_to_10("978076531985") is None
