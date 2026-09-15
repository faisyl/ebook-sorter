"""Path confinement and auth guards for the web app."""
from __future__ import annotations

from pathlib import Path

from fastapi import HTTPException, Request
from itsdangerous import BadSignature, SignatureExpired, TimestampSigner

from ebook_sorter.web.config import WebConfig


def resolve_in_root(root: str | bytes | Path, rel_path: str) -> Path:
    """Resolve a user-supplied relative path against root, rejecting escapes.

    Used by browse, job creation, and output-dir selection. Blocks '..',
    symlink escape, and absolute paths (X10).
    """
    root_path = Path(root).resolve()
    # Absolute paths are confined to root (safe behavior per spec sec 7)
    if rel_path.startswith("/"):
        return root_path
    rel_path = (rel_path or "").lstrip("/")
    if not rel_path or rel_path == ".":
        return root_path
    resolved = (root_path / rel_path).resolve()
    if root_path != resolved and not resolved.is_relative_to(root_path):
        raise HTTPException(
            status_code=400,
            detail="Path escapes the allowed root",
        )
    return resolved


def make_session(cfg: WebConfig, username: str) -> str:
    """Create a signed session cookie value."""
    signer = TimestampSigner(cfg.secret)
    return signer.sign(username.encode()).decode()


def verify_session(cfg: WebConfig, request: Request) -> str:
    """Verify the session cookie and return the username, or raise 401."""
    token = request.cookies.get("session")
    if not token:
        raise HTTPException(status_code=401, detail="Not authenticated")
    signer = TimestampSigner(cfg.secret)
    try:
        # Max age 7 days
        username = signer.unsign(token, max_age=604_800)
        return username.decode()
    except (BadSignature, SignatureExpired):
        raise HTTPException(status_code=401, detail="Invalid or expired session")


def require_auth(cfg: WebConfig, request: Request) -> str:
    """FastAPI dependency: returns the username if authenticated."""
    return verify_session(cfg, request)
