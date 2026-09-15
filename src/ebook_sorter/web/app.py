"""FastAPI application for the ebook-sorter web backend."""
from __future__ import annotations

import asyncio
import json
import logging
import shutil
from pathlib import Path
from typing import Any

from fastapi import (
    Depends,
    FastAPI,
    HTTPException,
    Request,
    WebSocket,
    WebSocketDisconnect,
)
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

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
    resolve_in_root,
    verify_session,
)
from ebook_sorter.web.store import JobStore

logger = logging.getLogger(__name__)

_EBOOK_EXTS = {
    ".pdf", ".epub", ".mobi", ".azw", ".azw3",
    ".djvu", ".cbr", ".cbz", ".chm", ".doc", ".docx", ".odt",
}


# ── Pydantic model for PATCH validation (X6) ─────────────────────────

class ItemEdit(BaseModel):
    """Whitelisted editable fields for PATCH /items/{id}."""
    title: str | None = None
    authors: list[str] | None = None
    series: str | None = None
    series_index: float | None = None
    isbn_10: str | None = None
    isbn_13: str | None = None
    year: int | None = None
    language: str | None = None
    publisher: str | None = None


# ── Dependencies ─────────────────────────────────────────────────────

def _get_web_cfg(request: Request) -> WebConfig:
    return request.app.state.web_cfg


def _get_current_user(request: Request) -> str:
    return verify_session(request.app.state.web_cfg, request)


def _ensure_store(request: Request) -> JobStore:
    """Lazily create the JobStore on first use (avoids mkdir at import time)."""
    store = request.app.state._store
    if store is None:
        web_cfg = request.app.state.web_cfg
        store = JobStore(web_cfg.data_dir / "jobs.db")
        request.app.state._store = store
    return store


async def _ws_emit(app: FastAPI, job_id: str, event: dict) -> None:
    """Publish a WS event to all connected clients for this job."""
    conns = app.state._ws_connections.get(job_id, [])
    for ws in list(conns):
        try:
            await ws.send_json(event)
        except Exception:
            pass


def create_app(web_cfg: WebConfig | None = None) -> FastAPI:
    """Create the FastAPI app. Accepts an optional WebConfig for testing."""
    if web_cfg is None:
        web_cfg = load_web_config()
    cfg = load_config(Path("ebook-sorter.toml"))

    app = FastAPI(title="ebook-sorter web")
    app.state.web_cfg = web_cfg
    app.state.cfg = cfg
    app.state._store = None  # lazy-initialized on first request
    app.state._ws_connections = {}  # job_id -> [WebSocket]

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
                entries.append({
                    "name": child.name,
                    "is_dir": child.is_dir(),
                    "rel": str(rel),
                })
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
        store = _ensure_store(request)
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
        return _ensure_store(request).list_jobs()

    @app.get("/api/jobs/{job_id}")
    async def get_job(
        job_id: str,
        request: Request,
        user: str = Depends(_get_current_user),
    ) -> dict:
        store = _ensure_store(request)
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
        store = _ensure_store(request)
        items, next_cursor = store.list_items(
            job_id, status=status_filter, cursor=cursor, limit=limit,
        )
        return {"items": items, "next_cursor": next_cursor}

    @app.post("/api/jobs/{job_id}/preview")
    async def start_preview(
        job_id: str,
        request: Request,
        user: str = Depends(_get_current_user),
    ) -> dict:
        store = _ensure_store(request)
        store.update_job_status(job_id, "previewing")
        asyncio.create_task(_run_preview(job_id, request.app))
        return {"status": "previewing"}

    @app.post("/api/jobs/{job_id}/apply")
    async def start_apply(
        job_id: str,
        request: Request,
        user: str = Depends(_get_current_user),
    ) -> dict:
        store = _ensure_store(request)
        store.update_job_status(job_id, "applying")
        asyncio.create_task(_run_apply(job_id, request.app))
        return {"status": "applying"}

    @app.post("/api/jobs/{job_id}/pause")
    async def pause_job(
        job_id: str,
        request: Request,
        user: str = Depends(_get_current_user),
    ) -> dict:
        _ensure_store(request).update_job_status(job_id, "paused")
        return {"status": "paused"}

    @app.post("/api/jobs/{job_id}/resume")
    async def resume_job(
        job_id: str,
        request: Request,
        user: str = Depends(_get_current_user),
    ) -> dict:
        _ensure_store(request).update_job_status(job_id, "running")
        return {"status": "running"}

    @app.post("/api/jobs/{job_id}/cancel")
    async def cancel_job(
        job_id: str,
        request: Request,
        user: str = Depends(_get_current_user),
    ) -> dict:
        _ensure_store(request).update_job_status(job_id, "cancelled")
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
        app.state._ws_connections.setdefault(job_id, []).append(websocket)
        try:
            while True:
                await websocket.receive_text()
        except WebSocketDisconnect:
            pass
        app.state._ws_connections.get(job_id, []).remove(websocket)

    # ── Item review endpoints ───────────────────────────────────────

    @app.get("/api/jobs/{job_id}/items/{item_id}")
    async def get_item(
        job_id: str,
        item_id: str,
        request: Request,
        user: str = Depends(_get_current_user),
    ) -> dict:
        store = _ensure_store(request)
        item = store.get_item(item_id)
        if not item or item["job_id"] != job_id:
            raise HTTPException(status_code=404, detail="Item not found")
        return {**item, "candidates": []}

    @app.patch("/api/jobs/{job_id}/items/{item_id}")
    async def edit_item(
        job_id: str,
        item_id: str,
        body: ItemEdit,
        request: Request,
        user: str = Depends(_get_current_user),
    ) -> dict:
        store = _ensure_store(request)
        item = store.get_item(item_id)
        if not item or item["job_id"] != job_id:
            raise HTTPException(status_code=404, detail="Item not found")
        # Merge only whitelisted, validated fields (X6)
        updates = body.model_dump(exclude_unset=True)
        meta = {**item["meta"], **updates}
        # Recompute planned_dest after edit (X12)
        job = store.get_job(job_id)
        planned = _render_dest_from_meta(meta, job) if job else item.get("planned_dest")
        store.update_item(
            item_id, meta=meta, planned_dest=planned,
            user_edited=True, status="matched",
        )
        return {"status": "ok"}

    @app.post("/api/jobs/{job_id}/items/{item_id}/relookup")
    async def relookup_item(
        job_id: str,
        item_id: str,
        body: dict,
        request: Request,
        user: str = Depends(_get_current_user),
    ) -> dict:
        # TODO: re-run lookup with overrides from body
        return {"candidates": []}

    @app.post("/api/jobs/{job_id}/items/{item_id}/apply")
    async def apply_item(
        job_id: str,
        item_id: str,
        request: Request,
        user: str = Depends(_get_current_user),
    ) -> dict:
        """Per-item apply: actually move/copy the file (X2, X3)."""
        wcfg = _get_web_cfg(request)
        store = _ensure_store(request)
        item = store.get_item(item_id)
        if not item or item["job_id"] != job_id:
            raise HTTPException(status_code=404, detail="Item not found")
        job = store.get_job(job_id)
        mode = job.get("options", {}).get("mode", "move") if job else "move"

        src = resolve_in_root(wcfg.books_root, item["source_path"])
        dest_str = item.get("planned_dest") or ""
        dest = resolve_in_root(wcfg.output_root, dest_str)
        dest.parent.mkdir(parents=True, exist_ok=True)

        try:
            if mode == "copy":
                shutil.copy2(str(src), str(dest))
            else:
                shutil.move(str(src), str(dest))
            store.update_item(
                item_id=item["id"], actual_dest=dest_str, status="moved",
            )
            return {"status": "moved", "actual_dest": dest_str}
        except Exception as e:
            store.update_item(item_id=item["id"], status="error", error=str(e))
            raise HTTPException(status_code=500, detail=str(e))

    @app.post("/api/jobs/{job_id}/items/{item_id}/reset")
    async def reset_item(
        job_id: str,
        item_id: str,
        request: Request,
        user: str = Depends(_get_current_user),
    ) -> dict:
        _ensure_store(request).update_item(
            item_id, user_edited=False, status="pending",
        )
        return {"status": "ok"}

    return app


# ── Job runner tasks ─────────────────────────────────────────────────

async def _run_preview(job_id: str, app: FastAPI) -> None:
    """Preview runner with pause/cancel (X1), WS events (X4),
    thread-offloaded pipeline (X5), and crash handling (X7)."""
    wcfg = app.state.web_cfg
    store = JobStore(wcfg.data_dir / "jobs.db")
    cfg: Config = app.state.cfg

    def _emit(event: dict) -> None:
        """Schedule emit on the event loop thread-safely."""
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                loop.call_soon_threadsafe(
                    asyncio.create_task, _ws_emit(app, job_id, event),
                )
        except RuntimeError:
            pass

    try:
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
        matched = uncertain = errors = 0

        for p in files:
            # Check pause/cancel between files (X1)
            current = store.get_job(job_id)
            if current and current["status"] == "cancelled":
                return
            while current and current["status"] == "paused":
                await asyncio.sleep(0.5)
                current = store.get_job(job_id)
                if current and current["status"] == "cancelled":
                    return
                if current and current["status"] != "paused":
                    break

            rel = str(p.relative_to(wcfg.books_root))
            item_id = store.create_item(job_id, rel)
            try:
                # Run blocking pipeline in thread (X5)
                meta = await asyncio.to_thread(pipeline.process, p)
                planned = _render_dest(meta, job)
                cls = _classify(
                    meta,
                    job["options"].get("confidence_threshold", cfg.confidence_threshold),
                )
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

            # Emit WS event per item (X4)
            _emit({
                "type": "item_update",
                "item_id": item_id,
                "counts": {"matched": matched, "uncertain": uncertain, "error": errors},
            })

        store.update_job_counts(
            job_id, matched=matched, uncertain=uncertain, error=errors,
        )
        store.update_job_status(job_id, "preview_ready")
        _emit({"type": "job_update", "status": "preview_ready"})

    except Exception as e:
        logger.exception("Preview job %s failed", job_id)
        store.update_job_status(job_id, "failed")
        _emit({"type": "job_update", "status": "failed", "error": str(e)})


async def _run_apply(job_id: str, app: FastAPI) -> None:
    """Apply runner with pause/cancel (X1), copy/mode support (X3),
    WS events (X4), and crash handling (X7)."""
    wcfg = app.state.web_cfg
    store = JobStore(wcfg.data_dir / "jobs.db")

    def _emit(event: dict) -> None:
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                loop.call_soon_threadsafe(
                    asyncio.create_task, _ws_emit(app, job_id, event),
                )
        except RuntimeError:
            pass

    try:
        job = store.get_job(job_id)
        if not job:
            return
        mode = job.get("options", {}).get("mode", "move")
        items, _ = store.list_items(job_id)
        moved = 0

        for item in items:
            # Check pause/cancel between files (X1)
            current = store.get_job(job_id)
            if current and current["status"] == "cancelled":
                return
            while current and current["status"] == "paused":
                await asyncio.sleep(0.5)
                current = store.get_job(job_id)
                if current and current["status"] == "cancelled":
                    return
                if current and current["status"] != "paused":
                    break

            if item["status"] != "matched":
                continue
            src = resolve_in_root(wcfg.books_root, item["source_path"])
            dest_str = item.get("planned_dest") or ""
            dest = resolve_in_root(wcfg.output_root, dest_str)
            dest.parent.mkdir(parents=True, exist_ok=True)

            if mode == "copy":
                shutil.copy2(str(src), str(dest))
            else:
                shutil.move(str(src), str(dest))
            store.update_item(
                item_id=item["id"], actual_dest=dest_str, status="moved",
            )
            moved += 1

            _emit({
                "type": "item_update",
                "item_id": item["id"],
                "moved": moved,
            })

        store.update_job_counts(job_id, moved=moved)
        store.update_job_status(job_id, "completed")
        _emit({"type": "job_update", "status": "completed"})

    except Exception as e:
        logger.exception("Apply job %s failed", job_id)
        store.update_job_status(job_id, "failed")
        _emit({"type": "job_update", "status": "failed", "error": str(e)})


# ── Module-level helpers ────────────────────────────────────────────

def _build_pipeline(cfg: Config, web_cfg: WebConfig) -> Pipeline:
    extractors: list[BaseExtractor] = [
        FilenameExtractor(),
        EmbeddedExtractor(),
        TextContentExtractor(cfg.ocr_first_pages, cfg.ocr_last_pages),
    ]
    lookups = [
        OpenLibraryLookup(),
        GoogleBooksLookup(
            api_key=web_cfg.google_books_api_key or cfg.google_books_api_key,
        ),
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


def _render_dest_from_meta(meta_dict: dict, job: dict) -> str | None:
    """Recompute planned_dest from an edited metadata dict (X12)."""
    title = meta_dict.get("title")
    if not title:
        return None
    options = job.get("options", {})
    cfg = Config(
        output_dir=Path("/output"),
        filename_template=options.get("filename_template", "{title}.{ext}"),
        folder_template=options.get("folder_template", ""),
        confidence_threshold=options.get("confidence_threshold", 0.7),
    )
    meta = BookMetadata(
        title=title,
        authors=meta_dict.get("authors", []),
        series=meta_dict.get("series"),
        series_index=meta_dict.get("series_index"),
        isbn_10=meta_dict.get("isbn_10"),
        isbn_13=meta_dict.get("isbn_13"),
        year=meta_dict.get("year"),
        language=meta_dict.get("language"),
        publisher=meta_dict.get("publisher"),
        author_sort=meta_dict.get("author_sort"),
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
