"""
db.py — Local SQLite persistence layer for the BASU Biometric Agent.

Stores the user roster (biometric_number, user_id, name, fingerprint status)
so the dashboard can display data instantly without hitting the device, and
so enrollment status can be synced to the server even when the server is
temporarily unreachable (fp_sync_pending retry queue).

Thread safety: each thread gets its own sqlite3 connection (threading.local).
WAL journal mode is enabled so reader threads never block the writer thread.
"""

import logging
import sqlite3
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import config

logger = logging.getLogger(__name__)

DB_PATH: Path = config.DB_PATH

_local = threading.local()


def _get_conn() -> sqlite3.Connection:
    conn: Optional[sqlite3.Connection] = getattr(_local, "conn", None)
    if conn is None:
        conn = sqlite3.connect(str(DB_PATH), check_same_thread=False)
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA foreign_keys=ON")
        conn.row_factory = sqlite3.Row
        _local.conn = conn
    return conn


def init_db() -> None:
    """Create the database and tables if they do not exist yet."""
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = _get_conn()
    conn.execute("""
        CREATE TABLE IF NOT EXISTS users (
            biometric_number     INTEGER PRIMARY KEY,
            user_id              TEXT    UNIQUE NOT NULL,
            name                 TEXT    NOT NULL,
            fingerprint_registered   INTEGER NOT NULL DEFAULT 0,
            is_registered_on_device  INTEGER NOT NULL DEFAULT 0,
            fp_sync_pending          INTEGER NOT NULL DEFAULT 0,
            created_at           TEXT    NOT NULL,
            updated_at           TEXT    NOT NULL
        )
    """)
    conn.commit()
    logger.info("DB initialised at %s", DB_PATH)


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def upsert_user(
    biometric_number: int,
    user_id: str,
    name: str,
    is_registered_on_device: bool,
    fingerprint_registered: bool,
    fp_sync_pending: Optional[bool] = None,
) -> None:
    """
    Insert or update a user row.

    If fp_sync_pending is None the existing value is preserved on UPDATE,
    or set to 0 on INSERT.  Pass an explicit True/False to force-set it.
    """
    conn = _get_conn()
    now = _now_iso()
    if fp_sync_pending is None:
        # On conflict: preserve existing fp_sync_pending
        conn.execute(
            """
            INSERT INTO users
                (biometric_number, user_id, name,
                 fingerprint_registered, is_registered_on_device, fp_sync_pending,
                 created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, 0, ?, ?)
            ON CONFLICT(biometric_number) DO UPDATE SET
                user_id = excluded.user_id,
                name    = excluded.name,
                fingerprint_registered   = excluded.fingerprint_registered,
                is_registered_on_device  = excluded.is_registered_on_device,
                updated_at               = excluded.updated_at
            """,
            (
                biometric_number,
                user_id,
                name,
                int(fingerprint_registered),
                int(is_registered_on_device),
                now,
                now,
            ),
        )
    else:
        conn.execute(
            """
            INSERT INTO users
                (biometric_number, user_id, name,
                 fingerprint_registered, is_registered_on_device, fp_sync_pending,
                 created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(biometric_number) DO UPDATE SET
                user_id = excluded.user_id,
                name    = excluded.name,
                fingerprint_registered   = excluded.fingerprint_registered,
                is_registered_on_device  = excluded.is_registered_on_device,
                fp_sync_pending          = excluded.fp_sync_pending,
                updated_at               = excluded.updated_at
            """,
            (
                biometric_number,
                user_id,
                name,
                int(fingerprint_registered),
                int(is_registered_on_device),
                int(fp_sync_pending),
                now,
                now,
            ),
        )
    conn.commit()


def get_all_users() -> list[dict]:
    """Return all users ordered by biometric_number."""
    conn = _get_conn()
    rows = conn.execute(
        "SELECT * FROM users ORDER BY biometric_number"
    ).fetchall()
    return [dict(r) for r in rows]


def get_fp_pending_users() -> list[dict]:
    """Return users whose fingerprint was enrolled but not yet ACKed to the server."""
    conn = _get_conn()
    rows = conn.execute(
        "SELECT * FROM users WHERE fp_sync_pending = 1"
    ).fetchall()
    return [dict(r) for r in rows]


def clear_fp_pending(user_ids: list[str]) -> None:
    """Clear the fp_sync_pending flag for a list of server CUIDs after successful PATCH."""
    if not user_ids:
        return
    conn = _get_conn()
    placeholders = ",".join("?" * len(user_ids))
    conn.execute(
        f"UPDATE users SET fp_sync_pending = 0, updated_at = ? WHERE user_id IN ({placeholders})",
        [_now_iso()] + list(user_ids),
    )
    conn.commit()


def update_fp_status(biometric_number: int, fingerprint_registered: bool, fp_sync_pending: bool) -> None:
    """Update fingerprint status for a single user (called when device enrollment is detected)."""
    conn = _get_conn()
    conn.execute(
        """
        UPDATE users
        SET fingerprint_registered = ?, fp_sync_pending = ?, updated_at = ?
        WHERE biometric_number = ?
        """,
        (int(fingerprint_registered), int(fp_sync_pending), _now_iso(), biometric_number),
    )
    conn.commit()


def delete_user(biometric_number: int) -> None:
    """Remove a user from the local DB (called after successful device deletion)."""
    conn = _get_conn()
    conn.execute("DELETE FROM users WHERE biometric_number = ?", (biometric_number,))
    conn.commit()


def count_stats() -> dict:
    """Return {total, fingerprinted, not_enrolled} for the Overview page stat cards."""
    conn = _get_conn()
    row = conn.execute(
        """
        SELECT
            COUNT(*)                                AS total,
            SUM(fingerprint_registered)             AS fingerprinted,
            SUM(1 - fingerprint_registered)         AS not_enrolled
        FROM users
        """
    ).fetchone()
    if row is None:
        return {"total": 0, "fingerprinted": 0, "not_enrolled": 0}
    return {
        "total":       row["total"]       or 0,
        "fingerprinted": row["fingerprinted"] or 0,
        "not_enrolled":  row["not_enrolled"]  or 0,
    }
