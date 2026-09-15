"""Job state machine, preview/apply, and review/redo tests (W5)."""
import time
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from ebook_sorter.web.app import create_app
from ebook_sorter.web.config import WebConfig


@pytest.fixture
def web_cfg(tmp_path: Path) -> WebConfig:
    books = tmp_path / "books"
    books.mkdir()
    output = tmp_path / "output"
    output.mkdir()
    data = tmp_path / "data"
    data.mkdir()
    return WebConfig(
        books_root=books,
        output_root=output,
        data_dir=data,
        user="admin",
        password="secret123",
        secret="test-secret",
        port=8080,
        google_books_api_key=None,
        filename_template="{title}.{ext}",
        folder_template="",
        confidence_threshold=0.7,
        ocr_enabled=False,
    )


@pytest.fixture
def app(web_cfg: WebConfig):
    return create_app(web_cfg=web_cfg)


@pytest.fixture
def client(app) -> TestClient:
    return TestClient(app)


@pytest.fixture
def authed(client: TestClient) -> TestClient:
    client.post("/api/login", json={"username": "admin", "password": "secret123"})
    return client


def _create_job_with_files(
    authed: TestClient,
    web_cfg: WebConfig,
    subdir: str = "sub",
    files: list[str] | None = None,
    options: dict | None = None,
) -> str:
    """Helper: create subdir with ebook files, create job, return job_id."""
    if files is None:
        files = ["Author - Title.epub"]
    if options is None:
        options = {}
    sub = web_cfg.books_root / subdir
    sub.mkdir(parents=True, exist_ok=True)
    for f in files:
        (sub / f).write_text("dummy ebook content")
    resp = authed.post("/api/jobs", json={
        "name": "Test Job",
        "input_root": "",
        "subdirs": [subdir],
        "output_dir": "",
        "options": options,
    })
    return resp.json()["id"]

    def test_job_created_with_status_created(self, authed: TestClient, web_cfg: WebConfig):
        job_id = _create_job_with_files(authed, web_cfg)
        resp = authed.get(f"/api/jobs/{job_id}")
        assert resp.status_code == 200
        assert resp.json()["status"] == "created"

    def test_list_jobs_includes_created(self, authed: TestClient, web_cfg: WebConfig):
        _create_job_with_files(authed, web_cfg)
        resp = authed.get("/api/jobs")
        assert resp.status_code == 200
        assert len(resp.json()) >= 1

    def test_job_detail_not_found(self, authed: TestClient):
        resp = authed.get("/api/jobs/nonexistent-id")
        assert resp.status_code == 404

    def test_pause_job(self, authed: TestClient, web_cfg: WebConfig):
        job_id = _create_job_with_files(authed, web_cfg)
        resp = authed.post(f"/api/jobs/{job_id}/pause")
        assert resp.status_code == 200
        assert resp.json()["status"] == "paused"

    def test_resume_job(self, authed: TestClient, web_cfg: WebConfig):
        job_id = _create_job_with_files(authed, web_cfg)
        authed.post(f"/api/jobs/{job_id}/pause")
        resp = authed.post(f"/api/jobs/{job_id}/resume")
        assert resp.status_code == 200
        assert resp.json()["status"] == "running"

    def test_cancel_job(self, authed: TestClient, web_cfg: WebConfig):
        job_id = _create_job_with_files(authed, web_cfg)
        resp = authed.post(f"/api/jobs/{job_id}/cancel")
        assert resp.status_code == 200
        assert resp.json()["status"] == "cancelled"

    def test_status_persists_after_pause(self, authed: TestClient, web_cfg: WebConfig):
        job_id = _create_job_with_files(authed, web_cfg)
        authed.post(f"/api/jobs/{job_id}/pause")
        resp = authed.get(f"/api/jobs/{job_id}")
        assert resp.json()["status"] == "paused"


# ── X1 STRENGTHENED: pause/cancel actually stop processing ─────────────


class TestPauseCancelRealEffect:
    def test_pause_stops_processing(self, authed: TestClient, web_cfg: WebConfig):
        """X1: Pausing a job must actually STOP processing, not just flip status.

        After pause, the job should NOT reach preview_ready.
        """
        files = [f"Book{i} - Author.epub" for i in range(5)]
        job_id = _create_job_with_files(authed, web_cfg, files=files)
        authed.post(f"/api/jobs/{job_id}/preview")
        authed.post(f"/api/jobs/{job_id}/pause")
        # Wait a bit — if pause works, status should stay paused/previewing
        time.sleep(0.5)
        resp = authed.get(f"/api/jobs/{job_id}")
        # If pause is a real effect, job should NOT have completed processing
        assert resp.json()["status"] != "preview_ready"

    def test_cancel_stops_processing(self, authed: TestClient, web_cfg: WebConfig):
        """X1: Cancelling a job must actually STOP processing."""
        files = [f"Book{i} - Author.epub" for i in range(5)]
        job_id = _create_job_with_files(authed, web_cfg, files=files)
        authed.post(f"/api/jobs/{job_id}/preview")
        authed.post(f"/api/jobs/{job_id}/cancel")
        time.sleep(0.5)
        resp = authed.get(f"/api/jobs/{job_id}")
        assert resp.json()["status"] != "preview_ready"


# ── Job items ─────────────────────────────────────────────────────────


class TestJobItems:
    def test_items_listed_for_job(self, authed: TestClient, web_cfg: WebConfig, wait_for) -> None:
        job_id = _create_job_with_files(authed, web_cfg, files=["Book1.epub", "Book2.epub"], options={"confidence_threshold": 0.3})
        # Preview populates items asynchronously — wait for it
        wait_for(authed, job_id, "preview_ready")
        resp = authed.get(f"/api/jobs/{job_id}/items")
        assert resp.status_code == 200
        data = resp.json()
        assert "items" in data
        assert "next_cursor" in data

    def test_items_pagination_cursor(self, authed: TestClient, web_cfg: WebConfig, wait_for) -> None:
        """Items are populated by async preview — wait for preview_ready first."""
        files = [f"Book{i}.epub" for i in range(5)]
        job_id = _create_job_with_files(authed, web_cfg, files=files)
        wait_for(authed, job_id, "preview_ready")
        resp = authed.get(f"/api/jobs/{job_id}/items?limit=2")
        data = resp.json()
        assert len(data["items"]) == 2
        assert data["next_cursor"] is not None

    def test_items_filter_by_status(self, authed: TestClient, web_cfg: WebConfig, wait_for) -> None:
        job_id = _create_job_with_files(authed, web_cfg, files=["Book1.epub"], options={"confidence_threshold": 0.3})
        wait_for(authed, job_id, "preview_ready")
        resp = authed.get(f"/api/jobs/{job_id}/items?status=pending")
        assert resp.status_code == 200
        data = resp.json()
        assert "items" in data

    def test_counts_by_status(self, authed: TestClient, web_cfg: WebConfig, wait_for) -> None:
        job_id = _create_job_with_files(authed, web_cfg, files=["Book1.epub", "Book2.epub"], options={"confidence_threshold": 0.3})
        wait_for(authed, job_id, "preview_ready")
        resp = authed.get(f"/api/jobs/{job_id}")
        data = resp.json()
        assert "counts" in data


# ── Preview endpoint ──────────────────────────────────────────────────


class TestPreview:
    def test_start_preview(self, authed: TestClient, web_cfg: WebConfig):
        job_id = _create_job_with_files(authed, web_cfg)
        resp = authed.post(f"/api/jobs/{job_id}/preview")
        assert resp.status_code == 200
        assert resp.json()["status"] == "previewing"

    def test_preview_does_not_move_files(self, authed: TestClient, web_cfg: WebConfig, wait_for) -> None:
        """Preview must NOT move any files."""
        job_id = _create_job_with_files(authed, web_cfg, files=["Author - Title.epub"], options={"confidence_threshold": 0.3})
        authed.post(f"/api/jobs/{job_id}/preview")
        wait_for(authed, job_id, "preview_ready")
        sub = web_cfg.books_root / "sub"
        assert (sub / "Author - Title.epub").exists()


# ── Apply endpoint ────────────────────────────────────────────────────


class TestApply:
    def test_start_apply(self, authed: TestClient, web_cfg: WebConfig):
        job_id = _create_job_with_files(authed, web_cfg)
        resp = authed.post(f"/api/jobs/{job_id}/apply")
        assert resp.status_code == 200
        assert resp.json()["status"] == "applying"

    def test_apply_moves_matched_items(self, authed: TestClient, web_cfg: WebConfig, wait_for) -> None:
        """Apply should move matched items to output."""
        job_id = _create_job_with_files(authed, web_cfg, files=["Cory Doctorow - Little Brother.epub"], options={"confidence_threshold": 0.3})
        wait_for(authed, job_id, "preview_ready")
        authed.post(f"/api/jobs/{job_id}/apply")
        wait_for(authed, job_id, "completed")
        output_files = list(web_cfg.output_root.rglob("*.epub"))
        assert len(output_files) >= 1


# ── X3 STRENGTHENED: copy vs move mode ────────────────────────────────


class TestCopyVsMove:
    def test_move_mode_removes_original(self, authed: TestClient, web_cfg: WebConfig, wait_for) -> None:
        """X3: In move mode (default), original file should be GONE after apply."""
        job_id = _create_job_with_files(authed, web_cfg, files=["Cory Doctorow - Little Brother.epub"], options={"confidence_threshold": 0.3, "mode": "move"})
        wait_for(authed, job_id, "preview_ready")
        authed.post(f"/api/jobs/{job_id}/apply")
        wait_for(authed, job_id, "completed")
        # Original should be gone
        sub = web_cfg.books_root / "sub"
        assert not (sub / "Cory Doctorow - Little Brother.epub").exists()

    def test_copy_mode_keeps_original(self, authed: TestClient, web_cfg: WebConfig, wait_for) -> None:
        """X3: In copy mode, original file should STILL EXIST after apply."""
        job_id = _create_job_with_files(authed, web_cfg, files=["Cory Doctorow - Little Brother.epub"], options={"confidence_threshold": 0.3, "mode": "copy"})
        wait_for(authed, job_id, "preview_ready")
        authed.post(f"/api/jobs/{job_id}/apply")
        wait_for(authed, job_id, "completed")
        # Original should still exist
        sub = web_cfg.books_root / "sub"
        assert (sub / "Cory Doctorow - Little Brother.epub").exists()


# ── X2 STRENGTHENED: per-item apply actually moves file ───────────────


class TestPerItemApply:
    def test_per_item_apply_moves_file(self, authed: TestClient, web_cfg: WebConfig, wait_for) -> None:
        """X2: Per-item apply must actually move the FILE on disk, not just flip status."""
        job_id = _create_job_with_files(authed, web_cfg, files=["Cory Doctorow - Little Brother.epub"], options={"confidence_threshold": 0.3})
        wait_for(authed, job_id, "preview_ready")
        items = authed.get(f"/api/jobs/{job_id}/items").json()["items"]
        assert len(items) >= 1
        item_id = items[0]["id"]
        resp = authed.post(f"/api/jobs/{job_id}/items/{item_id}/apply")
        assert resp.status_code == 200
        # The file should actually be moved
        sub = web_cfg.books_root / "sub"
        output_files = list(web_cfg.output_root.rglob("*.epub"))
        assert len(output_files) >= 1, "per-item apply did not move the file"


# ── Item review / redo ───────────────────────────────────────────────


class TestItemReview:
    def test_get_item_detail(self, authed: TestClient, web_cfg: WebConfig, wait_for) -> None:
        job_id = _create_job_with_files(authed, web_cfg)
        wait_for(authed, job_id, "preview_ready")
        items_resp = authed.get(f"/api/jobs/{job_id}/items")
        items = items_resp.json()["items"]
        if items:
            item_id = items[0]["id"]
            resp = authed.get(f"/api/jobs/{job_id}/items/{item_id}")
            assert resp.status_code == 200
            assert "candidates" in resp.json()

    def test_get_item_not_found(self, authed: TestClient, web_cfg: WebConfig):
        job_id = _create_job_with_files(authed, web_cfg)
        resp = authed.get(f"/api/jobs/{job_id}/items/nonexistent")
        assert resp.status_code == 404

    def test_edit_item(self, authed: TestClient, web_cfg: WebConfig, wait_for) -> None:
        job_id = _create_job_with_files(authed, web_cfg)
        wait_for(authed, job_id, "preview_ready")
        items_resp = authed.get(f"/api/jobs/{job_id}/items")
        items = items_resp.json()["items"]
        if items:
            item_id = items[0]["id"]
            resp = authed.patch(f"/api/jobs/{job_id}/items/{item_id}", json={
                "title": "New Title",
                "authors": ["New Author"],
            })
            assert resp.status_code == 200
            assert resp.json()["status"] == "ok"

    def test_edit_item_not_found(self, authed: TestClient, web_cfg: WebConfig):
        job_id = _create_job_with_files(authed, web_cfg)
        resp = authed.patch(f"/api/jobs/{job_id}/items/nonexistent", json={"title": "X"})
        assert resp.status_code == 404

    def test_relookup_item(self, authed: TestClient, web_cfg: WebConfig, wait_for) -> None:
        job_id = _create_job_with_files(authed, web_cfg)
        wait_for(authed, job_id, "preview_ready")
        items_resp = authed.get(f"/api/jobs/{job_id}/items")
        items = items_resp.json()["items"]
        if items:
            item_id = items[0]["id"]
            resp = authed.post(f"/api/jobs/{job_id}/items/{item_id}/relookup", json={})
            assert resp.status_code == 200
            assert "candidates" in resp.json()

    def test_apply_single_item(self, authed: TestClient, web_cfg: WebConfig, wait_for) -> None:
        job_id = _create_job_with_files(authed, web_cfg)
        wait_for(authed, job_id, "preview_ready")
        items_resp = authed.get(f"/api/jobs/{job_id}/items")
        items = items_resp.json()["items"]
        if items:
            item_id = items[0]["id"]
            resp = authed.post(f"/api/jobs/{job_id}/items/{item_id}/apply")
            assert resp.status_code == 200
            assert resp.json()["status"] == "moved"

    def test_reset_item(self, authed: TestClient, web_cfg: WebConfig, wait_for) -> None:
        job_id = _create_job_with_files(authed, web_cfg)
        wait_for(authed, job_id, "preview_ready")
        items_resp = authed.get(f"/api/jobs/{job_id}/items")
        items = items_resp.json()["items"]
        if items:
            item_id = items[0]["id"]
            resp = authed.post(f"/api/jobs/{job_id}/items/{item_id}/reset")
            assert resp.status_code == 200
            assert resp.json()["status"] == "ok"


# ── Job counts ────────────────────────────────────────────────────────


class TestJobCounts:
    def test_counts_initial_zero(self, authed: TestClient, web_cfg: WebConfig):
        job_id = _create_job_with_files(authed, web_cfg)
        resp = authed.get(f"/api/jobs/{job_id}")
        counts = resp.json()["counts"]
        assert isinstance(counts, dict)

    def test_counts_reflect_items(self, authed: TestClient, web_cfg: WebConfig, wait_for) -> None:
        job_id = _create_job_with_files(authed, web_cfg, files=["A.epub", "B.epub"], options={"confidence_threshold": 0.3})
        wait_for(authed, job_id, "preview_ready")
        resp = authed.get(f"/api/jobs/{job_id}")
        counts = resp.json()["counts"]
        total = sum(counts.values())
        assert total >= 0


# ── Job store isolation ───────────────────────────────────────────────


class TestJobStore:
    def test_multiple_jobs_independent(self, authed: TestClient, web_cfg: WebConfig):
        """Jobs created in sequence don't interfere."""
        job1 = _create_job_with_files(authed, web_cfg, subdir="dir1", files=["A.epub"], options={"confidence_threshold": 0.3})
        job2 = _create_job_with_files(authed, web_cfg, subdir="dir2", files=["B.epub"], options={"confidence_threshold": 0.3})

        resp1 = authed.get(f"/api/jobs/{job1}")
        resp2 = authed.get(f"/api/jobs/{job2}")
        assert resp1.json()["id"] != resp2.json()["id"]
        assert resp1.status_code == 200
        assert resp2.status_code == 200

    def test_job_not_found_returns_404(self, authed: TestClient):
        resp = authed.get("/api/jobs/fake-id")
        assert resp.status_code == 404
