"""Smoke tests for the web backend."""
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from ebook_sorter.web.app import create_app
from ebook_sorter.web.config import WebConfig


@pytest.fixture
def client(tmp_path: Path) -> TestClient:
    books = tmp_path / "books"
    books.mkdir()
    output = tmp_path / "output"
    output.mkdir()
    data = tmp_path / "data"
    data.mkdir()

    web_cfg = WebConfig(
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
    app = create_app(web_cfg=web_cfg)
    return TestClient(app)


def test_login_success(client: TestClient) -> None:
    resp = client.post("/api/login", json={"username": "admin", "password": "secret123"})
    assert resp.status_code == 200
    assert "session" in resp.cookies


def test_login_failure(client: TestClient) -> None:
    resp = client.post("/api/login", json={"username": "admin", "password": "wrong"})
    assert resp.status_code == 401


def test_browse_requires_auth(client: TestClient) -> None:
    resp = client.get("/api/browse?root=books&path=")
    assert resp.status_code == 401


def test_browse_success(client: TestClient, tmp_path: Path) -> None:
    client.post("/api/login", json={"username": "admin", "password": "secret123"})
    (tmp_path / "books" / "testdir").mkdir()

    resp = client.get("/api/browse?root=books&path=")
    assert resp.status_code == 200
    data = resp.json()
    assert "entries" in data
    names = [e["name"] for e in data["entries"]]
    assert "testdir" in names


def test_path_traversal_blocked(client: TestClient) -> None:
    client.post("/api/login", json={"username": "admin", "password": "secret123"})
    resp = client.get("/api/browse?root=books&path=../../../etc/passwd")
    assert resp.status_code == 400


def test_create_job(client: TestClient, tmp_path: Path) -> None:
    client.post("/api/login", json={"username": "admin", "password": "secret123"})
    (tmp_path / "books" / "sub").mkdir()
    (tmp_path / "books" / "sub" / "test.epub").write_text("dummy")

    resp = client.post("/api/jobs", json={
        "name": "Test Job",
        "input_root": "",
        "subdirs": ["sub"],
        "output_dir": "",
        "options": {},
    })
    assert resp.status_code == 200
    data = resp.json()
    assert "id" in data
    assert data["status"] == "created"


def test_list_jobs(client: TestClient, tmp_path: Path) -> None:
    client.post("/api/login", json={"username": "admin", "password": "secret123"})
    (tmp_path / "books" / "sub").mkdir()
    (tmp_path / "books" / "sub" / "test.epub").write_text("dummy")
    client.post("/api/jobs", json={
        "name": "Test Job", "input_root": "",
        "subdirs": ["sub"], "output_dir": "", "options": {},
    })

    resp = client.get("/api/jobs")
    assert resp.status_code == 200
    assert len(resp.json()) >= 1


def test_job_detail(client: TestClient, tmp_path: Path) -> None:
    client.post("/api/login", json={"username": "admin", "password": "secret123"})
    (tmp_path / "books" / "sub").mkdir()
    (tmp_path / "books" / "sub" / "test.epub").write_text("dummy")

    resp = client.post("/api/jobs", json={
        "name": "Test Job", "input_root": "",
        "subdirs": ["sub"], "output_dir": "", "options": {},
    })
    job_id = resp.json()["id"]

    resp = client.get(f"/api/jobs/{job_id}")
    assert resp.status_code == 200
    assert resp.json()["id"] == job_id
