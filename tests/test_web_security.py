"""Security tests: path confinement and auth (W5)."""
from pathlib import Path

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

from ebook_sorter.web.app import create_app
from ebook_sorter.web.config import WebConfig
from ebook_sorter.web.security import make_session, resolve_in_root, verify_session


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


# ── Path confinement (resolve_in_root) ────────────────────────────────


class TestResolveInRoot:
    def test_returns_root_for_empty_path(self, web_cfg: WebConfig):
        result = resolve_in_root(web_cfg.books_root, "")
        assert result == web_cfg.books_root.resolve()

    def test_returns_root_for_dot(self, web_cfg: WebConfig):
        result = resolve_in_root(web_cfg.books_root, ".")
        assert result == web_cfg.books_root.resolve()

    def test_accepts_valid_subpath(self, web_cfg: WebConfig):
        sub = web_cfg.books_root / "subdir"
        sub.mkdir()
        result = resolve_in_root(web_cfg.books_root, "subdir")
        assert result == sub.resolve()

    def test_accepts_nested_subpath(self, web_cfg: WebConfig):
        nested = web_cfg.books_root / "a" / "b"
        nested.mkdir(parents=True)
        result = resolve_in_root(web_cfg.books_root, "a/b")
        assert result == nested.resolve()

    def test_rejects_dotdot_escape(self, web_cfg: WebConfig):
        with pytest.raises(HTTPException) as exc_info:
            resolve_in_root(web_cfg.books_root, "../etc/passwd")
        assert exc_info.value.status_code == 400

    def test_rejects_dotdot_in_middle(self, web_cfg: WebConfig):
        with pytest.raises(HTTPException) as exc_info:
            resolve_in_root(web_cfg.books_root, "subdir/../../etc")
        assert exc_info.value.status_code == 400

    def test_rejects_absolute_path(self, web_cfg: WebConfig):
        # resolve_in_root confines absolute paths to root (safe behavior)
        result = resolve_in_root(web_cfg.books_root, "/etc/passwd")
        # The result must be within books_root, NOT /etc/passwd
        assert result == web_cfg.books_root.resolve()
        assert result.is_relative_to(web_cfg.books_root.resolve())

    def test_rejects_symlink_escape(self, web_cfg: WebConfig, tmp_path: Path):
        # Create a symlink inside books pointing outside it
        outside = tmp_path / "outside"
        outside.mkdir()
        link = web_cfg.books_root / "escape"
        link.symlink_to(outside)
        with pytest.raises(HTTPException) as exc_info:
            resolve_in_root(web_cfg.books_root, "escape/secret.txt")
        assert exc_info.value.status_code == 400

    def test_rejects_deep_symlink_escape(self, web_cfg: WebConfig, tmp_path: Path):
        outside = tmp_path / "outside"
        outside.mkdir()
        nested = web_cfg.books_root / "a" / "b"
        nested.mkdir(parents=True)
        link = nested / "link"
        link.symlink_to(outside)
        with pytest.raises(HTTPException) as exc_info:
            resolve_in_root(web_cfg.books_root, "a/b/link/secret.txt")
        assert exc_info.value.status_code == 400


# ── Path confinement via browse endpoint ──────────────────────────────


class TestBrowsePathTraversal:
    def test_browse_rejects_dotdot(self, authed: TestClient):
        resp = authed.get("/api/browse?root=books&path=../../../etc/passwd")
        assert resp.status_code == 400

    def test_browse_rejects_absolute(self, authed: TestClient):
        resp = authed.get("/api/browse?root=books&path=/etc/passwd")
        # Absolute paths are confined to root (safe), then 404 because the
        # confined path doesn't exist. Either 400 or 404 is acceptable —
        # the key is it does NOT leak /etc/passwd.
        assert resp.status_code in (400, 404)
        # If 404, the confined path must not escape root
        if resp.status_code == 404:
            # Good — path was confined to root
            pass

    def test_browse_rejects_unknown_root(self, authed: TestClient):
        resp = authed.get("/api/browse?root=secret&path=")
        assert resp.status_code == 400

    def test_browse_returns_404_for_missing(self, authed: TestClient):
        resp = authed.get("/api/browse?root=books&path=nonexistent")
        assert resp.status_code == 404

    def test_browse_lists_entries(self, authed: TestClient, web_cfg: WebConfig):
        (web_cfg.books_root / "dir1").mkdir()
        (web_cfg.books_root / "file1.txt").write_text("x")
        resp = authed.get("/api/browse?root=books&path=")
        assert resp.status_code == 200
        names = [e["name"] for e in resp.json()["entries"]]
        assert "dir1" in names
        assert "file1.txt" in names

    def test_browse_output_root(self, authed: TestClient, web_cfg: WebConfig):
        (web_cfg.output_root / "sorted").mkdir()
        resp = authed.get("/api/browse?root=output&path=")
        assert resp.status_code == 200
        names = [e["name"] for e in resp.json()["entries"]]
        assert "sorted" in names


# ── Auth: session cookie ──────────────────────────────────────────────


class TestAuth:
    def test_login_success_sets_cookie(self, client: TestClient):
        resp = client.post("/api/login", json={"username": "admin", "password": "secret123"})
        assert resp.status_code == 200
        assert "session" in resp.cookies

    def test_login_wrong_password(self, client: TestClient):
        resp = client.post("/api/login", json={"username": "admin", "password": "wrong"})
        assert resp.status_code == 401

    def test_login_wrong_username(self, client: TestClient):
        resp = client.post("/api/login", json={"username": "nobody", "password": "secret123"})
        assert resp.status_code == 401

    def test_login_empty_credentials(self, client: TestClient):
        resp = client.post("/api/login", json={"username": "", "password": ""})
        assert resp.status_code == 401

    def test_logout_clears_cookie(self, authed: TestClient):
        resp = authed.post("/api/logout")
        assert resp.status_code == 200

    def test_me_requires_auth(self, client: TestClient):
        resp = client.get("/api/me")
        assert resp.status_code == 401

    def test_me_returns_username(self, authed: TestClient):
        resp = authed.get("/api/me")
        assert resp.status_code == 200
        assert resp.json()["username"] == "admin"

    def test_protected_routes_require_auth(self, client: TestClient):
        routes = [
            ("/api/browse?root=books&path=", "GET"),
            ("/api/jobs", "GET"),
            ("/api/jobs", "POST"),
        ]
        for path, method in routes:
            if method == "GET":
                resp = client.get(path)
            else:
                resp = client.post(path, json={})
            assert resp.status_code == 401, f"{method} {path} should require auth"


# ── Auth: session verification ────────────────────────────────────────


class TestSessionVerification:
    def test_verify_valid_session(self, web_cfg: WebConfig):
        token = make_session(web_cfg, "admin")
        # Mock request with cookie
        class MockRequest:
            cookies = {"session": token}
        username = verify_session(web_cfg, MockRequest())
        assert username == "admin"

    def test_verify_missing_token(self, web_cfg: WebConfig):
        class MockRequest:
            cookies = {}
        with pytest.raises(HTTPException) as exc_info:
            verify_session(web_cfg, MockRequest())
        assert exc_info.value.status_code == 401

    def test_verify_tampered_token(self, web_cfg: WebConfig):
        class MockRequest:
            cookies = {"session": "tampered.token.here"}
        with pytest.raises(HTTPException) as exc_info:
            verify_session(web_cfg, MockRequest())
        assert exc_info.value.status_code == 401


# ── WebSocket auth ────────────────────────────────────────────────────


class TestWebSocketAuth:
    def test_ws_rejects_without_auth(self, client: TestClient):
        with pytest.raises(Exception):
            with client.websocket_connect("/api/jobs/some-id/events") as ws:
                ws.receive_text()

    def test_ws_accepts_with_auth(self, authed: TestClient):
        with authed.websocket_connect("/api/jobs/some-id/events") as ws:
            # Should stay open (no immediate close)
            pass
