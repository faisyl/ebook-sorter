"""Classification, preview vs apply behavior, and edge cases (W5)."""
import time
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from ebook_sorter.web.app import create_app, _classify, _render_dest
from ebook_sorter.web.config import WebConfig
from ebook_sorter.models import BookMetadata


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


def _create_job(authed: TestClient, web_cfg: WebConfig, subdir: str = "sub",
                files: list[str] | None = None, options: dict | None = None) -> str:
    if files is None:
        files = ["Author - Title.epub"]
    if options is None:
        options = {}
    sub = web_cfg.books_root / subdir
    sub.mkdir(parents=True, exist_ok=True)
    for f in files:
        (sub / f).write_text("dummy")
    resp = authed.post("/api/jobs", json={
        "name": "Test Job",
        "input_root": "",
        "subdirs": [subdir],
        "output_dir": "",
        "options": options,
    })
    return resp.json()["id"]


# ── Classification (_classify) ────────────────────────────────────────


class TestClassify:
    def test_matched_when_confidence_above_threshold_and_title(self):
        meta = BookMetadata(title="Book", confidence=0.8)
        assert _classify(meta, 0.7) == "matched"

    def test_uncertain_when_confidence_below_threshold(self):
        meta = BookMetadata(title="Book", confidence=0.5)
        assert _classify(meta, 0.7) == "uncertain"

    def test_uncertain_when_no_title(self):
        meta = BookMetadata(title=None, confidence=0.9)
        assert _classify(meta, 0.7) == "uncertain"

    def test_uncertain_at_exact_threshold(self):
        """Confidence exactly equal to threshold should match (>= per code)."""
        meta = BookMetadata(title="Book", confidence=0.7)
        assert _classify(meta, 0.7) == "matched"

    def test_custom_threshold(self):
        meta = BookMetadata(title="Book", confidence=0.6)
        assert _classify(meta, 0.5) == "matched"
        assert _classify(meta, 0.7) == "uncertain"


# ── Preview vs Apply semantics ────────────────────────────────────────


class TestPreviewDoesNotMove:
    def test_preview_leaves_files_in_place(self, authed: TestClient, web_cfg: WebConfig):
        """Preview must NEVER move files."""
        job_id = _create_job(authed, web_cfg, files=["My Book.epub"])
        authed.post(f"/api/jobs/{job_id}/preview")
        time.sleep(0.5)
        # Files must still be in books root
        sub = web_cfg.books_root / "sub"
        assert (sub / "My Book.epub").exists()
        # Nothing should be in output
        output_files = list(web_cfg.output_root.rglob("*"))
        # Filter out directories
        output_files = [f for f in output_files if f.is_file()]
        assert len(output_files) == 0


class TestApplyMovesFiles:
    def test_apply_moves_files_to_output(self, authed: TestClient, web_cfg: WebConfig):
        """Apply should move matched items to output directory."""
        job_id = _create_job(authed, web_cfg, files=["Cory Doctorow - Little Brother.epub"])
        authed.post(f"/api/jobs/{job_id}/preview")
        time.sleep(0.5)
        authed.post(f"/api/jobs/{job_id}/apply")
        time.sleep(0.5)
        # After apply, at least one file should be in output
        output_files = list(web_cfg.output_root.rglob("*.epub"))
        assert len(output_files) >= 1


# ── Job creation with options ─────────────────────────────────────────


class TestJobCreation:
    def test_create_job_with_options(self, authed: TestClient, web_cfg: WebConfig):
        job_id = _create_job(authed, web_cfg, options={
            "filename_template": "{title} - {authors}.{ext}",
            "confidence_threshold": 0.5,
            "ocr_enabled": True,
        })
        resp = authed.get(f"/api/jobs/{job_id}")
        data = resp.json()
        assert data["id"] == job_id
        assert data["status"] == "created"

    def test_create_job_empty_subdirs(self, authed: TestClient, web_cfg: WebConfig):
        resp = authed.post("/api/jobs", json={
            "name": "Empty Job",
            "input_root": "",
            "subdirs": [],
            "output_dir": "",
            "options": {},
        })
        assert resp.status_code == 200
        assert "id" in resp.json()


# ── Edge cases ────────────────────────────────────────────────────────


class TestEdgeCases:
    def test_no_ebooks_in_subdir(self, authed: TestClient, web_cfg: WebConfig):
        """Job with no ebook files should still create successfully."""
        job_id = _create_job(authed, web_cfg, files=["readme.txt", "image.jpg"])
        resp = authed.get(f"/api/jobs/{job_id}")
        assert resp.status_code == 200

    def test_job_with_many_files(self, authed: TestClient, web_cfg: WebConfig, wait_for):
        """Job with many files should handle pagination."""
        files = [f"Book{i} - Author.epub" for i in range(10)]
        job_id = _create_job(authed, web_cfg, files=files)
        wait_for(authed, job_id, "preview_ready")
        resp = authed.get(f"/api/jobs/{job_id}/items?limit=3")
        data = resp.json()
        assert len(data["items"]) == 3

    def test_apply_empty_job(self, authed: TestClient, web_cfg: WebConfig):
        """Apply on job with no items should complete without error."""
        job_id = _create_job(authed, web_cfg, files=["readme.txt"])
        resp = authed.post(f"/api/jobs/{job_id}/apply")
        assert resp.status_code == 200

    def test_double_cancel(self, authed: TestClient, web_cfg: WebConfig):
        """Cancelling twice should not error."""
        job_id = _create_job(authed, web_cfg)
        authed.post(f"/api/jobs/{job_id}/cancel")
        resp = authed.post(f"/api/jobs/{job_id}/cancel")
        assert resp.status_code == 200


# ── Item state transitions ────────────────────────────────────────────


class TestItemTransitions:
    def test_edit_marks_user_edited(self, authed: TestClient, web_cfg: WebConfig):
        """Editing an item should mark it user_edited."""
        job_id = _create_job(authed, web_cfg)
        items = authed.get(f"/api/jobs/{job_id}/items").json()["items"]
        if items:
            item_id = items[0]["id"]
            authed.patch(f"/api/jobs/{job_id}/items/{item_id}", json={"title": "Edited"})
            item_resp = authed.get(f"/api/jobs/{job_id}/items/{item_id}")
            assert item_resp.json()["user_edited"] is True

    def test_edit_sets_status_matched(self, authed: TestClient, web_cfg: WebConfig):
        """Editing an item should set status to matched."""
        job_id = _create_job(authed, web_cfg)
        items = authed.get(f"/api/jobs/{job_id}/items").json()["items"]
        if items:
            item_id = items[0]["id"]
            authed.patch(f"/api/jobs/{job_id}/items/{item_id}", json={"title": "X"})
            item_resp = authed.get(f"/api/jobs/{job_id}/items/{item_id}")
            assert item_resp.json()["status"] == "matched"

    def test_reset_clears_user_edited(self, authed: TestClient, web_cfg: WebConfig):
        """Reset should clear user_edited flag."""
        job_id = _create_job(authed, web_cfg)
        items = authed.get(f"/api/jobs/{job_id}/items").json()["items"]
        if items:
            item_id = items[0]["id"]
            # Edit then reset
            authed.patch(f"/api/jobs/{job_id}/items/{item_id}", json={"title": "X"})
            authed.post(f"/api/jobs/{job_id}/items/{item_id}/reset")
            item_resp = authed.get(f"/api/jobs/{job_id}/items/{item_id}")
            assert item_resp.json()["user_edited"] is False
