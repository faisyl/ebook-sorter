"""SQLite job store for the web app."""
from __future__ import annotations

import json
import sqlite3
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path

_DB_SCHEMA = """
CREATE TABLE IF NOT EXISTS job (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    input_root TEXT NOT NULL,
    subdirs_json TEXT NOT NULL DEFAULT '[]',
    output_dir TEXT NOT NULL,
    options_json TEXT NOT NULL DEFAULT '{}',
    status TEXT NOT NULL DEFAULT 'created',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    total INTEGER NOT NULL DEFAULT 0,
    matched INTEGER NOT NULL DEFAULT 0,
    uncertain INTEGER NOT NULL DEFAULT 0,
    error INTEGER NOT NULL DEFAULT 0,
    moved INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS item (
    id TEXT PRIMARY KEY,
    job_id TEXT NOT NULL,
    source_path TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'pending',
    meta_json TEXT NOT NULL DEFAULT '{}',
    planned_dest TEXT,
    actual_dest TEXT,
    error TEXT,
    user_edited INTEGER NOT NULL DEFAULT 0,
    updated_at TEXT NOT NULL,
    FOREIGN KEY (job_id) REFERENCES job(id)
);

CREATE INDEX IF NOT EXISTS idx_item_job ON item(job_id);
CREATE INDEX IF NOT EXISTS idx_item_status ON item(status);
"""


class JobStore:
    def __init__(self, db_path: Path) -> None:
        self.db_path = db_path
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_schema()

    @contextmanager
    def _conn(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        finally:
            conn.close()

    def _init_schema(self) -> None:
        with self._conn() as conn:
            conn.executescript(_DB_SCHEMA)

    @staticmethod
    def _now() -> str:
        return datetime.now(timezone.utc).isoformat()

    # ── Job CRUD ─────────────────────────────────────────────────────

    def create_job(
        self,
        name: str,
        input_root: str,
        subdirs: list[str],
        output_dir: str,
        options: dict,
    ) -> str:
        job_id = str(uuid.uuid4())
        now = self._now()
        with self._conn() as conn:
            conn.execute(
                """INSERT INTO job
                   (id, name, input_root, subdirs_json, output_dir, options_json,
                    status, created_at, updated_at)
                   VALUES (?, ?, ?, ?, ?, ?, 'created', ?, ?)""",
                (
                    job_id,
                    name,
                    input_root,
                    json.dumps(subdirs),
                    output_dir,
                    json.dumps(options),
                    now,
                    now,
                ),
            )
        return job_id

    def get_job(self, job_id: str) -> dict | None:
        with self._conn() as conn:
            row = conn.execute(
                "SELECT * FROM job WHERE id = ?", (job_id,)
            ).fetchone()
        if not row:
            return None
        return self._row_to_job(row)

    def list_jobs(self) -> list[dict]:
        with self._conn() as conn:
            rows = conn.execute(
                "SELECT * FROM job ORDER BY created_at DESC"
            ).fetchall()
        return [self._row_to_job(r) for r in rows]

    def update_job_status(self, job_id: str, status: str) -> None:
        with self._conn() as conn:
            conn.execute(
                "UPDATE job SET status = ?, updated_at = ? WHERE id = ?",
                (status, self._now(), job_id),
            )

    def update_job_counts(
        self,
        job_id: str,
        total: int | None = None,
        matched: int | None = None,
        uncertain: int | None = None,
        error: int | None = None,
        moved: int | None = None,
    ) -> None:
        fields = []
        values = []
        for name, val in [
            ("total", total),
            ("matched", matched),
            ("uncertain", uncertain),
            ("error", error),
            ("moved", moved),
        ]:
            if val is not None:
                fields.append(f"{name} = ?")
                values.append(val)
        if not fields:
            return
        values.extend([self._now(), job_id])
        with self._conn() as conn:
            conn.execute(
                f"UPDATE job SET {', '.join(fields)}, updated_at = ? WHERE id = ?",
                values,
            )

    def set_job_flag(self, job_id: str, field: str, value: int) -> None:
        """Set a job flag field. X11: field is allowlisted to prevent SQL injection."""
        _ALLOWED_FLAGS = {"total", "matched", "uncertain", "error", "moved"}
        if field not in _ALLOWED_FLAGS:
            raise ValueError(f"Invalid flag field: {field}")
        with self._conn() as conn:
            conn.execute(
                f"UPDATE job SET {field} = ?, updated_at = ? WHERE id = ?",
                (value, self._now(), job_id),
            )

    # ── Item CRUD ────────────────────────────────────────────────────

    def create_item(self, job_id: str, source_path: str) -> str:
        item_id = str(uuid.uuid4())
        now = self._now()
        with self._conn() as conn:
            conn.execute(
                """INSERT INTO item
                   (id, job_id, source_path, status, meta_json, updated_at)
                   VALUES (?, ?, ?, 'pending', '{}', ?)""",
                (item_id, job_id, source_path, now),
            )
        return item_id

    def get_item(self, item_id: str) -> dict | None:
        with self._conn() as conn:
            row = conn.execute(
                "SELECT * FROM item WHERE id = ?", (item_id,)
            ).fetchone()
        if not row:
            return None
        return self._row_to_item(row)

    def list_items(
        self,
        job_id: str,
        status: str | None = None,
        cursor: str | None = None,
        limit: int = 100,
    ) -> tuple[list[dict], str | None]:
        """Return (items, next_cursor). Cursor is an opaque item id."""
        query = "SELECT * FROM item WHERE job_id = ?"
        params: list = [job_id]
        if status:
            query += " AND status = ?"
            params.append(status)

        with self._conn() as conn:
            if cursor:
                # Opaque cursor: last seen item id. If that item was since
                # deleted, "rowid > (SELECT ...)" evaluates to NULL and
                # matches nothing, silently emptying the page (X17) — so
                # only apply the cursor when it still resolves to a row.
                cursor_row = conn.execute(
                    "SELECT rowid FROM item WHERE id = ?", (cursor,)
                ).fetchone()
                if cursor_row is not None:
                    query += " AND rowid > ?"
                    params.append(cursor_row["rowid"])
            query += f" ORDER BY rowid LIMIT {int(limit)}"
            rows = conn.execute(query, params).fetchall()

        items = [self._row_to_item(r) for r in rows]
        next_cursor = items[-1]["id"] if len(items) == limit else None
        return items, next_cursor

    def count_items_by_status(self, job_id: str) -> dict[str, int]:
        with self._conn() as conn:
            rows = conn.execute(
                "SELECT status, COUNT(*) AS c FROM item WHERE job_id = ? GROUP BY status",
                (job_id,),
            ).fetchall()
        return {r["status"]: r["c"] for r in rows}

    def update_item(
        self,
        item_id: str,
        **kwargs,
    ) -> None:
        allowed = {
            "status",
            "meta",
            "planned_dest",
            "actual_dest",
            "error",
            "user_edited",
        }
        fields = []
        values = []
        for key, val in kwargs.items():
            if key not in allowed:
                continue
            if key == "meta":
                fields.append("meta_json = ?")
                values.append(json.dumps(val))
            elif key == "user_edited":
                fields.append("user_edited = ?")
                values.append(1 if val else 0)
            else:
                fields.append(f"{key} = ?")
                values.append(val)
        if not fields:
            return
        fields.append("updated_at = ?")
        values.append(self._now())
        values.append(item_id)
        with self._conn() as conn:
            conn.execute(
                f"UPDATE item SET {', '.join(fields)} WHERE id = ?",
                values,
            )

    # ── Helpers ──────────────────────────────────────────────────────

    @staticmethod
    def _row_to_job(row: sqlite3.Row) -> dict:
        return {
            "id": row["id"],
            "name": row["name"],
            "input_root": row["input_root"],
            "subdirs": json.loads(row["subdirs_json"]),
            "output_dir": row["output_dir"],
            "options": json.loads(row["options_json"]),
            "status": row["status"],
            "created_at": row["created_at"],
            "updated_at": row["updated_at"],
            "total": row["total"],
            "matched": row["matched"],
            "uncertain": row["uncertain"],
            "error": row["error"],
            "moved": row["moved"],
        }

    @staticmethod
    def _row_to_item(row: sqlite3.Row) -> dict:
        return {
            "id": row["id"],
            "job_id": row["job_id"],
            "source_path": row["source_path"],
            "status": row["status"],
            "meta": json.loads(row["meta_json"]),
            "planned_dest": row["planned_dest"],
            "actual_dest": row["actual_dest"],
            "error": row["error"],
            "user_edited": bool(row["user_edited"]),
            "updated_at": row["updated_at"],
        }
