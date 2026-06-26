"""SQLite database for video summary knowledge base.

Stores structured metadata, full markdown content, user annotations (tags,
notes, ratings), and Feishu sync status.  Uses FTS5 for full-text search.
"""

from __future__ import annotations

import json
import sqlite3
import sys
from contextlib import contextmanager
from dataclasses import dataclass, field
from pathlib import Path
from typing import Generator, Optional

DB_DIR = Path.home() / ".bili-summary"
DB_PATH = DB_DIR / "knowledge.db"


# ---------------------------------------------------------------------------
# Data class
# ---------------------------------------------------------------------------

@dataclass
class SummaryRecord:
    """A single summary row from the database."""

    id: int
    bvid: str
    title: str
    owner: str
    duration: str
    pic_url: str = ""
    desc_text: str = ""
    markdown_content: str = ""
    char_count: int = 0
    research_rating: str = ""
    investment_conclusion: str = ""
    tags: list[str] = field(default_factory=list)
    notes: str = ""
    feishu_doc_id: str = ""
    feishu_record_id: str = ""
    synced_at: Optional[str] = None
    created_at: str = ""
    updated_at: str = ""


# ---------------------------------------------------------------------------
# Connection management
# ---------------------------------------------------------------------------

def _get_conn() -> sqlite3.Connection:
    """Open (or create) the knowledge database."""
    DB_DIR.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


@contextmanager
def _txn(conn: sqlite3.Connection) -> Generator[sqlite3.Connection, None, None]:
    """Context manager that commits or rolls back a transaction."""
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise


# ---------------------------------------------------------------------------
# Schema initialisation
# ---------------------------------------------------------------------------

def init_db() -> None:
    """Create tables and FTS5 index if they don't exist."""
    conn = _get_conn()
    try:
        with _txn(conn):
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS summaries (
                    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
                    bvid                TEXT UNIQUE NOT NULL,
                    title               TEXT NOT NULL,
                    owner               TEXT NOT NULL,
                    duration            TEXT NOT NULL,
                    pic_url             TEXT DEFAULT '',
                    desc_text           TEXT DEFAULT '',
                    markdown_content    TEXT NOT NULL,
                    char_count          INTEGER DEFAULT 0,
                    research_rating     TEXT DEFAULT '',
                    investment_conclusion TEXT DEFAULT '',
                    tags                TEXT DEFAULT '[]',
                    notes               TEXT DEFAULT '',
                    feishu_doc_id       TEXT DEFAULT '',
                    feishu_record_id    TEXT DEFAULT '',
                    synced_at           TEXT DEFAULT NULL,
                    created_at          TEXT NOT NULL DEFAULT (datetime('now','localtime')),
                    updated_at          TEXT NOT NULL DEFAULT (datetime('now','localtime'))
                )
                """
            )
            # FTS5 full-text search index (content-sync mode)
            conn.execute(
                """
                CREATE VIRTUAL TABLE IF NOT EXISTS summaries_fts USING fts5(
                    title,
                    owner,
                    markdown_content,
                    content=summaries,
                    content_rowid=id
                )
                """
            )
            # Triggers to keep FTS in sync
            conn.execute(
                """
                CREATE TRIGGER IF NOT EXISTS summaries_ai AFTER INSERT ON summaries BEGIN
                    INSERT INTO summaries_fts(rowid, title, owner, markdown_content)
                    VALUES (new.id, new.title, new.owner, new.markdown_content);
                END
                """
            )
            conn.execute(
                """
                CREATE TRIGGER IF NOT EXISTS summaries_ad AFTER DELETE ON summaries BEGIN
                    INSERT INTO summaries_fts(summaries_fts, rowid, title, owner, markdown_content)
                    VALUES ('delete', old.id, old.title, old.owner, old.markdown_content);
                END
                """
            )
            conn.execute(
                """
                CREATE TRIGGER IF NOT EXISTS summaries_au AFTER UPDATE ON summaries BEGIN
                    INSERT INTO summaries_fts(summaries_fts, rowid, title, owner, markdown_content)
                    VALUES ('delete', old.id, old.title, old.owner, old.markdown_content);
                    INSERT INTO summaries_fts(rowid, title, owner, markdown_content)
                    VALUES (new.id, new.title, new.owner, new.markdown_content);
                END
                """
            )
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# Row → dataclass
# ---------------------------------------------------------------------------

def _row_to_record(row: sqlite3.Row) -> SummaryRecord:
    """Convert a database row to a SummaryRecord."""
    tags_raw = row["tags"]
    try:
        tags = json.loads(tags_raw) if tags_raw else []
    except (json.JSONDecodeError, TypeError):
        tags = []

    return SummaryRecord(
        id=row["id"],
        bvid=row["bvid"],
        title=row["title"],
        owner=row["owner"],
        duration=row["duration"],
        pic_url=row["pic_url"] or "",
        desc_text=row["desc_text"] or "",
        markdown_content=row["markdown_content"],
        char_count=row["char_count"] or 0,
        research_rating=row["research_rating"] or "",
        investment_conclusion=row["investment_conclusion"] or "",
        tags=tags,
        notes=row["notes"] or "",
        feishu_doc_id=row["feishu_doc_id"] or "",
        feishu_record_id=row["feishu_record_id"] or "",
        synced_at=row["synced_at"] or None,
        created_at=row["created_at"] or "",
        updated_at=row["updated_at"] or "",
    )


# ---------------------------------------------------------------------------
# CRUD
# ---------------------------------------------------------------------------

def save_summary(
    bvid: str,
    title: str,
    owner: str,
    duration: str,
    markdown_content: str,
    pic_url: str = "",
    desc_text: str = "",
) -> int:
    """Insert or update a summary.  Returns the row id."""
    conn = _get_conn()
    try:
        char_count = len(markdown_content)
        with _txn(conn):
            existing = conn.execute(
                "SELECT id FROM summaries WHERE bvid = ?", (bvid,)
            ).fetchone()

            if existing:
                conn.execute(
                    """
                    UPDATE summaries
                    SET title = ?, owner = ?, duration = ?, pic_url = ?,
                        desc_text = ?, markdown_content = ?, char_count = ?,
                        updated_at = datetime('now','localtime')
                    WHERE bvid = ?
                    """,
                    (
                        title, owner, duration, pic_url,
                        desc_text, markdown_content, char_count,
                        bvid,
                    ),
                )
                return existing["id"]
            else:
                cursor = conn.execute(
                    """
                    INSERT INTO summaries
                        (bvid, title, owner, duration, pic_url, desc_text,
                         markdown_content, char_count)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        bvid, title, owner, duration, pic_url,
                        desc_text, markdown_content, char_count,
                    ),
                )
                return cursor.lastrowid
    finally:
        conn.close()


def list_summaries(
    search: str = "",
    tag: str = "",
    rating: str = "",
    limit: int = 50,
    offset: int = 0,
) -> tuple[list[SummaryRecord], int]:
    """Return (records, total_count) with optional filters.

    ``search`` uses FTS5 full-text search.
    ``tag`` filters by a single tag (JSON contains match).
    ``rating`` filters by research_rating (A/B/C/D).
    """
    conn = _get_conn()
    try:
        where_parts = []
        params: list = []

        if search:
            where_parts.append("s.id IN (SELECT rowid FROM summaries_fts WHERE summaries_fts MATCH ?)")
            params.append(search)

        if rating:
            where_parts.append("s.research_rating = ?")
            params.append(rating)

        if tag:
            # Simple JSON contains match — works for single-word tags
            where_parts.append("s.tags LIKE ?")
            params.append(f'%"{tag}"%')

        where_clause = ("WHERE " + " AND ".join(where_parts)) if where_parts else ""

        # Total count
        count_row = conn.execute(
            f"SELECT COUNT(*) FROM summaries s {where_clause}", params
        ).fetchone()
        total = count_row[0] if count_row else 0

        # Page
        rows = conn.execute(
            f"""
            SELECT s.* FROM summaries s
            {where_clause}
            ORDER BY s.created_at DESC
            LIMIT ? OFFSET ?
            """,
            params + [limit, offset],
        ).fetchall()

        return [_row_to_record(r) for r in rows], total
    finally:
        conn.close()


def get_summary(summary_id: int) -> Optional[SummaryRecord]:
    """Get a single summary by id."""
    conn = _get_conn()
    try:
        row = conn.execute(
            "SELECT * FROM summaries WHERE id = ?", (summary_id,)
        ).fetchone()
        return _row_to_record(row) if row else None
    finally:
        conn.close()


def get_summary_by_bvid(bvid: str) -> Optional[SummaryRecord]:
    """Get a single summary by BV号."""
    conn = _get_conn()
    try:
        row = conn.execute(
            "SELECT * FROM summaries WHERE bvid = ?", (bvid,)
        ).fetchone()
        return _row_to_record(row) if row else None
    finally:
        conn.close()


def update_summary(
    summary_id: int,
    *,
    tags: Optional[list[str]] = None,
    notes: Optional[str] = None,
    research_rating: Optional[str] = None,
    investment_conclusion: Optional[str] = None,
) -> bool:
    """Update user-editable fields.  Returns True if a row was updated."""
    conn = _get_conn()
    try:
        with _txn(conn):
            sets = []
            params: list = []

            if tags is not None:
                sets.append("tags = ?")
                params.append(json.dumps(tags, ensure_ascii=False))
            if notes is not None:
                sets.append("notes = ?")
                params.append(notes)
            if research_rating is not None:
                sets.append("research_rating = ?")
                params.append(research_rating)
            if investment_conclusion is not None:
                sets.append("investment_conclusion = ?")
                params.append(investment_conclusion)

            if not sets:
                return False

            sets.append("updated_at = datetime('now','localtime')")
            params.append(summary_id)

            cur = conn.execute(
                f"UPDATE summaries SET {', '.join(sets)} WHERE id = ?",
                params,
            )
            return cur.rowcount > 0
    finally:
        conn.close()


def delete_summary(summary_id: int) -> bool:
    """Delete a summary.  Returns True if deleted."""
    conn = _get_conn()
    try:
        with _txn(conn):
            cur = conn.execute("DELETE FROM summaries WHERE id = ?", (summary_id,))
            return cur.rowcount > 0
    finally:
        conn.close()


def update_sync_status(
    summary_id: int,
    feishu_doc_id: str = "",
    feishu_record_id: str = "",
) -> bool:
    """Mark a summary as synced to Feishu."""
    conn = _get_conn()
    try:
        with _txn(conn):
            cur = conn.execute(
                """
                UPDATE summaries
                SET feishu_doc_id = ?,
                    feishu_record_id = ?,
                    synced_at = datetime('now','localtime'),
                    updated_at = datetime('now','localtime')
                WHERE id = ?
                """,
                (feishu_doc_id, feishu_record_id, summary_id),
            )
            return cur.rowcount > 0
    finally:
        conn.close()


def get_stats() -> dict:
    """Return aggregate statistics."""
    conn = _get_conn()
    try:
        total = conn.execute("SELECT COUNT(*) FROM summaries").fetchone()[0]
        owner_count = conn.execute(
            "SELECT COUNT(DISTINCT owner) FROM summaries"
        ).fetchone()[0]
        rating_dist = {}
        for row in conn.execute(
            "SELECT research_rating, COUNT(*) as cnt FROM summaries "
            "WHERE research_rating != '' GROUP BY research_rating"
        ).fetchall():
            rating_dist[row["research_rating"]] = row["cnt"]
        recent = conn.execute(
            "SELECT COUNT(*) FROM summaries "
            "WHERE created_at >= datetime('now','-7 days','localtime')"
        ).fetchone()[0]

        return {
            "total": total,
            "owners": owner_count,
            "rating_distribution": rating_dist,
            "recent_7d": recent,
            "db_path": str(DB_PATH),
        }
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# Init on import (safe — CREATE IF NOT EXISTS)
# ---------------------------------------------------------------------------
init_db()
print(f"📚 知识库已就绪: {DB_PATH}", file=sys.stderr)
