"""FastAPI application for the ebook-sorter web backend."""
from __future__ import annotations

import asyncio
import json
import logging
import shutil
from pathlib import Path
from typing import Annotated, Any

from fastapi import (
    Depends,
    FastAPI,
    HTTPException,
    Request,
    WebSocket,
    WebSocketDisconnect,
)
from fastapi.responses import JSONResponse

from ebook_sorter.config import Config, load_config
from ebook_sorter.extractors.base import BaseExtractor
from ebook_sorter.extractors.embedded import EmbeddedExtractor
from ebook_sorter.extractors.filename import FilenameExtractor
from ebook_sorter.extractors.text_content import TextContentExtractor
from ebook_sorter.lookup.calibre import CalibreLookup
from ebook_sorter.lookup.google_books import GoogleBooksLookup
from ebook_sorter.lookup.openlibrary import OpenLibraryLookup
from ebook_sorter.models import BookMetadata
from ebook_sorter.organizer import Organizer
from ebook_sorter.pipeline import Pipeline
from ebook_sorter.web.config import WebConfig, load_web_config
from ebook_sorter.web.security import (
    make_session,
    require_auth,
    resolve_in_root,
    verify_session,
)
from ebook_sorter.web.store import JobStore

logger = logging.getLogger(__name__)

_EBOOK_EXTS = {
    ".pdf", ".epub", ".mobi", ".azw", ".azw3",
    ".djvu", ".cbr", ".cbz", ".chm", ".doc", ".docx", ".odt",
}


def _get_web_cfg(request: Request) -> WebConfig:
    return request.app.state.web_cfg


def _get_store(request: Request) -> JobStore:
    return request.app.state.store


def _get_current_user(request: Request) -> str:
    return verify_session(request.app.state.web_cfg, request)


def create_app(web_cfg: WebConfig | None = None) -> FastAPI:
    """Create the FastAPI app. Accepts an optional WebConfig for testing."""
    if web_cfg is None:
        web_cfg = load_web_config()
    cfg = load_config(Path("ebook-sorter.toml"))
    store = JobStore(web_cfg.data_dir / "jobs.db")

    app = FastAPI(title="ebook-sorter web")
    app.state.web_cfg = web_cfg
    app.state.cfg = cfg
    app.state.store = store

    _ws_connections: dict[str, list[WebSocket]] = {}

    async def emit(job_id: str, event: dict) -> None:
        for ws in list(_ws_connections.get(job_id, [])):
            try:
                await ws.send_json(event)
            except Exception:
                pass

    # ── Auth endpoints ──────────────────────────────────────────────

    @app.post("/api/login")
    async def login(request: Request) -> JSONResponse:
        body = await request.json()
        username = body.get("username", "")
        password = body.get("password", "")
        wcfg = _get_web_cfg(request)
        if username == wcfg.user and password == wcfg.password:
            token = make_session(wcfg, username)
            response = JSONResponse({"status": "ok"})
            response.set_cookie(
                "session", token, httponly=True, samesite="lax", max_age=604_800,
            )
            return response
        raise HTTPException(status_code=401, detail="Invalid credentials")

    @app.post("/api/logout")
    async def logout() -> JSONResponse:
        response = JSONResponse({"status": "ok"})
        response.delete_cookie("session")
        return response

    @app.get("/api/me")
    async def me(user: str = Depends(_get_current_user)) -> dict:
        return {"username": user}

    # ── Browse endpoints ────────────────────────────────────────────

    @app.get("/api/browse")
    async def browse(
        request: Request,
        root: str = "books",
        path: str = "",
        user: str = Depends(_get_current_user),
    ) -> dict:
        wcfg = _get_web_cfg(request)
        if root == "books":
            base = wcfg.books_root
        elif root == "output":
            base = wcfg.output_root
        else:
            raise HTTPException(status_code=400, detail=f"Unknown root: {root}")

        resolved = resolve_in_root(base, path)
        if not resolved.exists():
            raise HTTPException(status_code=404, detail="Path not found")

        entries = []
        for child in sorted(resolved.iterdir()):
            try:
                rel = child.relative_to(base)
                entries.append({"name": child.name, "is_dir": child.is_dir(), "rel": str(rel)})
            except ValueError:
                continue
        return {"entries": entries}

    # ── Job endpoints ───────────────────────────────────────────────

    @app.post("/api/jobs")
    async def create_job(
        request: Request,
        user: str = Depends(_get_current_user),
    ) -> dict:
        body = await request.json()
        store = _get_store(request)
        job_id = store.create_job(
            name=body.get("name", "Untitled"),
            input_root=body.get("input_root", ""),
            subdirs=body.get("subdirs", []),
            output_dir=body.get("output_dir", ""),
            options=body.get("options", {}),
        )
        store.update_job_status(job_id, "created")
        return {"id": job_id, "status": "created"}

    @app.get("/api/jobs")
    async def list_jobs(
        request: Request,
        user: str = Depends(_get_current_user),
    ) -> list[dict]:
        return _get_store(request).list_jobs()

    @app.get("/api/jobs/{job_id}")
    async def get_job(
        job_id: str,
        request: Request,
        user: str = Depends(_get_current_user),
    ) -> dict:
        store = _get_store(request)
        job = store.get_job(job_id)
        if not job:
            raise HTTPException(status_code=404, detail="Job not found")
        counts = store.count_items_by_status(job_id)
        return {**job, "counts": counts}

    @app.get("/api/jobs/{job_id}/items")
    async def list_items(
        job_id: str,
        request: Request,
        status_filter: str | None = None,
        cursor: str | None = None,
        limit: int = 100,
        user: str = Depends(_get_current_user),
    ) -> dict:
        store = _get_store(request)
        items, next_cursor = store.list_items(
            job_id, status=status_filter, cursor=cursor, limit=limit
        )
        return {"items": items, "next_cursor": next_cursor}

    @app.post("/api/jobs/{job_id}/preview")
    async def start_preview(
        job_id: str,
        request: Request,
        user: str = Depends(_get_current_user),
    ) -> dict:
        store = _get_store(request)
        store.update_job_status(job_id, "previewing")
        asyncio.create_task(_run_preview(job_id, request.app))
        return {"status": "previewing"}

    @app.post("/api/jobs/{job_id}/apply")
    async def start_apply(
        job_id: str,
        request: Request,
        user: str = Depends(_get_current_user),
    ) -> dict:
        store = _get_store(request)
        store.update_job_status(job_id, "applying")
        asyncio.create_task(_run_apply(job_id, request.app))
        return {"status": "applying"}

    @app.post("/api/jobs/{job_id}/pause")
    async def pause_job(
        job_id: str,
        request: Request,
        user: str = Depends(_get_current_user),
    ) -> dict:
        _get_store(request).update_job_status(job_id, "paused")
        return {"status": "paused"}

    @app.post("/api/jobs/{job_id}/resume")
    async def resume_job(
        job_id: str,
        request: Request,
        user: str = Depends(_get_current_user),
    ) -> dict:
        _get_store(request).update_job_status(job_id, "running")
        return {"status": "running"}

    @app.post("/api/jobs/{job_id}/cancel")
    async def cancel_job(
        job_id: str,
        request: Request,
        user: str = Depends(_get_current_user),
    ) -> dict:
        _get_store(request).update_job_status(job_id, "cancelled")
        return {"status": "cancelled"}

    # ── WebSocket ───────────────────────────────────────────────────

    @app.websocket("/api/jobs/{job_id}/events")
    async def ws_events(websocket: WebSocket, job_id: str) -> None:
        wcfg = websocket.app.state.web_cfg
        try:
            verify_session(wcfg, websocket)
        except HTTPException:
            await websocket.close(code=4001)
            return
        await websocket.accept()
        _ws_connections.setdefault(job_id, []).append(websocket)
        try:
            while True:
                await websocket.receive_text()
        except WebSocketDisconnect:
            pass
        _ws_connections.get(job_id, []).remove(websocket)

    # ── Item review endpoints ───────────────────────────────────────

    @app.get("/api/jobs/{job_id}/items/{item_id}")
    async def get_item(
        job_id: str,
        item_id: str,
        request: Request,
        user: str = Depends(_get_current_user),
    ) -> dict:
        store = _get_store(request)
        item = store.get_item(item_id)
        if not item or item["job_id"] != job_id:
            raise HTTPException(status_code=404, detail="Item not found")
        return {**item, "candidates": []}

    @app.patch("/api/jobs/{job_id}/items/{item_id}")
    async def edit_item(
        job_id: str,
        item_id: str,
        body: dict,
        request: Request,
        user: str = Depends(_get_current_user),
    ) -> dict:
        store = _get_store(request)
        item = store.get_item(item_id)
        if not item or item["job_id"] != job_id:
            raise HTTPException(status_code=404, detail="Item not found")
        meta = {**item["meta"], **body}
        store.update_item(item_id, meta=meta, user_edited=True, status="matched")
        return {"status": "ok"}

    @app.post("/api/jobs/{job_id}/items/{item_id}/relookup")
    async def relookup_item(
        job_id: str,
        item_id: str,
        body: dict,
        request: Request,
        user: str = Depends(_get_current_user),
    ) -> dict:
        return {"candidates": []}

    @app.post("/api/jobs/{job_id}/items/{item_id}/apply")
    async def apply_item(
        job_id: str,
        item_id: str,
        request: Request,
        user: str = Depends(_get_current_user),
    ) -> dict:
        store = _get_store(request)
        item = store.get_item(item_id)
        if not item or item["job_id"] != job_id:
            raise HTTPException(status_code=404, detail="Item not found")
        store.update_item(item_id=item_id, status="moved")
        return {"status": "moved"}

    @app.post("/api/jobs/{job_id}/items/{item_id}/reset")
    async def reset_item(
        job_id: str,
        item_id: str,
        request: Request,
        user: str = Depends(_get_current_user),
    ) -> dict:
        _get_store(request).update_item(item_id, user_edited=False, status="pending")
        return {"status": "ok"}

    return app


# ── Job runner tasks ─────────────────────────────────────────────────

async def _run_preview(job_id: str, app: FastAPI) -> None:
    wcfg = app.state.web_cfg
    store: JobStore = app.state.store
    cfg: Config = app.state.cfg
    job = store.get_job(job_id)
    if not job:
        return
    pipeline = _build_pipeline(cfg, wcfg)
    input_root = resolve_in_root(wcfg.books_root, job["input_root"])

    files: list[Path] = []
    for subdir in job["subdirs"]:
        sub_path = resolve_in_root(input_root, subdir)
        for p in sorted(sub_path.rglob("*")):
            if p.is_file() and p.suffix.lower() in _EBOOK_EXTS:
                files.append(p)

    store.update_job_counts(job_id, total=len(files))
    matched = 0
    uncertain = 0
    errors = 0

    for p in files:
        rel = str(p.relative_to(wcfg.books_root))
        item_id = store.create_item(job_id, rel)
        try:
            meta = pipeline.process(p)
            planned = _render_dest(meta, job)
            cls = _classify(meta, job["options"].get("confidence_threshold", cfg.confidence_threshold))
            store.update_item(
                item_id,
                meta=_meta_to_dict(meta),
                planned_dest=planned,
                status=cls,
            )
            if cls == "matched":
                matched += 1
            else:
                uncertain += 1
        except Exception as e:
            store.update_item(item_id, status="error", error=str(e))
            errors += 1

    store.update_job_counts(job_id, matched=matched, uncertain=uncertain, error=errors)
    store.update_job_status(job_id, "preview_ready")


async def _run_apply(job_id: str, app: FastAPI) -> None:
    wcfg = app.state.web_cfg
    store: JobStore = app.state.store
    job = store.get_job(job_id)
    if not job:
        return
    items, _ = store.list_items(job_id)
    moved = 0
    for item in items:
        if item["status"] != "matched":
            continue
        src = resolve_in_root(wcfg.books_root, item["source_path"])
        dest_str = item.get("planned_dest") or ""
        dest = resolve_in_root(wcfg.output_root, dest_str)
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(src), str(dest))
        store.update_item(item_id=item["id"], actual_dest=dest_str, status="moved")
        moved += 1
    store.update_job_counts(job_id, moved=moved)
    store.update_job_status(job_id, "completed")


# ── Module-level helpers ────────────────────────────────────────────

def _build_pipeline(cfg: Config, web_cfg: WebConfig) -> Pipeline:
    extractors: list[BaseExtractor] = [
        FilenameExtractor(),
        EmbeddedExtractor(),
        TextContentExtractor(cfg.ocr_first_pages, cfg.ocr_last_pages),
    ]
    lookups = [
        OpenLibraryLookup(),
        GoogleBooksLookup(api_key=web_cfg.google_books_api_key or cfg.google_books_api_key),
        CalibreLookup(),
    ]
    return Pipeline(extractors=extractors, lookups=lookups)


def _classify(meta: BookMetadata, threshold: float) -> str:
    if meta.confidence >= threshold and meta.title:
        return "matched"
    return "uncertain"


def _render_dest(meta: BookMetadata, job: dict) -> str | None:
    if not meta.title:
        return None
    options = job.get("options", {})
    cfg = Config(
        output_dir=Path("/output"),
        filename_template=options.get("filename_template", "{title}.{ext}"),
        folder_template=options.get("folder_template", ""),
        confidence_threshold=options.get("confidence_threshold", 0.7),
    )
    organizer = Organizer(
        output_dir=cfg.output_dir,
        filename_template=cfg.filename_template,
        folder_template=cfg.folder_template,
    )
    try:
        dest = organizer.render_path(meta)
        return str(dest.relative_to("/output"))
    except Exception:
        return None


def _meta_to_dict(meta: BookMetadata) -> dict[str, Any]:
    return {
        "title": meta.title,
        "authors": meta.authors,
        "series": meta.series,
        "series_index": meta.series_index,
        "isbn_10": meta.isbn_10,
        "isbn_13": meta.isbn_13,
        "year": meta.year,
        "language": meta.language,
        "publisher": meta.publisher,
        "source": meta.source,
        "confidence": meta.confidence,
        "author_sort": meta.author_sort,
    }


app = create_app()
