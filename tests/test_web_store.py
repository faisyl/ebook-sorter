"""JobStore unit tests (X17 cursor pagination)."""
from pathlib import Path

from ebook_sorter.web.store import JobStore


def _make_store(tmp_path: Path) -> JobStore:
    return JobStore(tmp_path / "jobs.db")


def _make_job_with_items(store: JobStore, count: int) -> tuple[str, list[str]]:
    job_id = store.create_job(
        name="job",
        input_root="",
        subdirs=[],
        output_dir="out",
        options={},
    )
    item_ids = [store.create_item(job_id, f"book{i}.epub") for i in range(count)]
    return job_id, item_ids


class TestListItemsCursor:
    def test_paginates_with_valid_cursor(self, tmp_path: Path) -> None:
        store = _make_store(tmp_path)
        job_id, item_ids = _make_job_with_items(store, 5)
        first_page, cursor = store.list_items(job_id, limit=2)
        assert [i["id"] for i in first_page] == item_ids[:2]
        assert cursor == item_ids[1]
        second_page, _ = store.list_items(job_id, cursor=cursor, limit=2)
        assert [i["id"] for i in second_page] == item_ids[2:4]

    def test_cursor_for_deleted_item_falls_back_to_first_page(
        self, tmp_path: Path
    ) -> None:
        # X17: if the cursor item was deleted, "rowid > (SELECT ...)"
        # evaluates to NULL and used to silently return zero rows.
        store = _make_store(tmp_path)
        job_id, item_ids = _make_job_with_items(store, 3)
        deleted_cursor = item_ids[1]
        with store._conn() as conn:
            conn.execute("DELETE FROM item WHERE id = ?", (deleted_cursor,))

        items, _ = store.list_items(job_id, cursor=deleted_cursor, limit=10)
        assert len(items) == 2
        assert {i["id"] for i in items} == {item_ids[0], item_ids[2]}

    def test_unknown_cursor_falls_back_to_first_page(self, tmp_path: Path) -> None:
        store = _make_store(tmp_path)
        job_id, item_ids = _make_job_with_items(store, 3)
        items, _ = store.list_items(job_id, cursor="not-a-real-id", limit=10)
        assert [i["id"] for i in items] == item_ids
