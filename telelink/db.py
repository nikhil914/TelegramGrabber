"""
TeleLink — SQLite Persistence Layer
All queries use parameterised statements (no string formatting).
"""
import sqlite3
from pathlib import Path
from datetime import datetime

import pandas as pd


# ── Schema ────────────────────────────────────────────────────────────

_SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS messages (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    message_id   INTEGER NOT NULL,
    channel_name TEXT    NOT NULL,
    sender_id    INTEGER,
    message_text TEXT,
    message_date TEXT,
    has_link     INTEGER DEFAULT 0,
    scraped_at   TEXT    DEFAULT (datetime('now')),
    UNIQUE(channel_name, message_id)
);

CREATE TABLE IF NOT EXISTS links (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    url          TEXT NOT NULL,
    domain       TEXT,
    anchor_text  TEXT,
    source       TEXT,
    message_id   INTEGER,
    message_date TEXT,
    channel_name TEXT,
    forward_from TEXT,
    first_seen   TEXT DEFAULT (datetime('now')),
    UNIQUE(channel_name, message_id, url)
);

CREATE TABLE IF NOT EXISTS channels (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    channel_name    TEXT UNIQUE,
    display_name    TEXT,
    member_count    INTEGER,
    last_scraped    TEXT,
    message_count   INTEGER DEFAULT 0,
    link_count      INTEGER DEFAULT 0
);
"""


def init_db(db_path: Path | str | None = None) -> sqlite3.Connection:
    """Create / open DB and ensure tables exist. Returns connection."""
    if db_path is None:
        from config import DB_PATH
        db_path = DB_PATH
    conn = sqlite3.connect(str(db_path), check_same_thread=False)
    conn.executescript(_SCHEMA_SQL)
    conn.commit()
    return conn


# ── CRUD helpers ──────────────────────────────────────────────────────

def save_messages(conn: sqlite3.Connection, messages: list[dict]) -> int:
    """INSERT OR IGNORE a batch of message dicts. Returns rows inserted."""
    sql = """
        INSERT OR IGNORE INTO messages
            (message_id, channel_name, sender_id, message_text,
             message_date, has_link)
        VALUES (?, ?, ?, ?, ?, ?)
    """
    rows = [
        (
            m["message_id"],
            m["channel_name"],
            m.get("sender_id"),
            m.get("text", ""),
            m.get("date", ""),
            1 if m.get("has_link") else 0,
        )
        for m in messages
    ]
    cur = conn.executemany(sql, rows)
    conn.commit()
    return cur.rowcount


def save_links(conn: sqlite3.Connection, links: list) -> int:
    """INSERT OR IGNORE a batch of LinkRecord objects. Returns rows inserted."""
    sql = """
        INSERT OR IGNORE INTO links
            (url, domain, anchor_text, source, message_id,
             message_date, channel_name, forward_from)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """
    rows = [
        (
            lr.url,
            lr.domain,
            lr.anchor_text,
            lr.source,
            lr.message_id,
            str(lr.message_date) if lr.message_date else "",
            lr.channel_name,
            getattr(lr, "forward_from", None),
        )
        for lr in links
    ]
    cur = conn.executemany(sql, rows)
    conn.commit()
    return cur.rowcount


def upsert_channel(conn: sqlite3.Connection, channel_info: dict):
    """Insert or update channel metadata."""
    sql = """
        INSERT INTO channels (channel_name, display_name, member_count,
                              last_scraped, message_count, link_count)
        VALUES (?, ?, ?, ?, ?, ?)
        ON CONFLICT(channel_name) DO UPDATE SET
            display_name = excluded.display_name,
            member_count = excluded.member_count,
            last_scraped = excluded.last_scraped,
            message_count = excluded.message_count,
            link_count    = excluded.link_count
    """
    conn.execute(sql, (
        channel_info.get("channel_name", ""),
        channel_info.get("display_name", ""),
        channel_info.get("member_count", 0),
        channel_info.get("last_scraped", datetime.now().isoformat()),
        channel_info.get("message_count", 0),
        channel_info.get("link_count", 0),
    ))
    conn.commit()


# ── Query helpers ─────────────────────────────────────────────────────

def get_messages(
    conn: sqlite3.Connection,
    channel: str | None = None,
    keyword: str | None = None,
    has_link: bool | None = None,
) -> pd.DataFrame:
    """Return messages as a DataFrame with optional filters."""
    clauses: list[str] = []
    params: list = []

    if channel and channel != "All":
        clauses.append("channel_name = ?")
        params.append(channel)
    if keyword:
        clauses.append("message_text LIKE ?")
        params.append(f"%{keyword}%")
    if has_link is True:
        clauses.append("has_link = 1")
    elif has_link is False:
        clauses.append("has_link = 0")

    where = ("WHERE " + " AND ".join(clauses)) if clauses else ""
    sql = f"SELECT * FROM messages {where} ORDER BY message_date DESC"
    return pd.read_sql_query(sql, conn, params=params)


def get_links(
    conn: sqlite3.Connection,
    channel: str | None = None,
    domain: str | None = None,
    unique_only: bool = False,
    search: str | None = None,
) -> pd.DataFrame:
    """Return links as a DataFrame with optional filters."""
    clauses: list[str] = []
    params: list = []

    if channel and channel != "All":
        clauses.append("channel_name = ?")
        params.append(channel)
    if domain and domain != "All":
        clauses.append("domain = ?")
        params.append(domain)
    if search:
        clauses.append("url LIKE ?")
        params.append(f"%{search}%")

    where = ("WHERE " + " AND ".join(clauses)) if clauses else ""

    if unique_only:
        sql = f"""
            SELECT url, domain, anchor_text, source, channel_name,
                   MIN(message_date) AS message_date, message_id
            FROM links {where}
            GROUP BY url
            ORDER BY message_date DESC
        """
    else:
        sql = f"SELECT * FROM links {where} ORDER BY message_date DESC"

    return pd.read_sql_query(sql, conn, params=params)


def get_channel_stats(conn: sqlite3.Connection) -> pd.DataFrame:
    """Return per-channel statistics."""
    sql = "SELECT * FROM channels ORDER BY last_scraped DESC"
    return pd.read_sql_query(sql, conn)


def get_domain_list(conn: sqlite3.Connection) -> list[str]:
    """Return sorted list of unique domains."""
    cur = conn.execute(
        "SELECT DISTINCT domain FROM links WHERE domain IS NOT NULL ORDER BY domain"
    )
    return [row[0] for row in cur.fetchall()]


def get_channel_list(conn: sqlite3.Connection) -> list[str]:
    """Return sorted list of unique channel names."""
    cur = conn.execute(
        "SELECT DISTINCT channel_name FROM channels ORDER BY channel_name"
    )
    return [row[0] for row in cur.fetchall()]


def get_last_message_id(conn: sqlite3.Connection, channel_name: str) -> int:
    """Return the max scraped message_id for a channel (for incremental scraping)."""
    cur = conn.execute(
        "SELECT COALESCE(MAX(message_id), 0) FROM messages WHERE channel_name = ?",
        (channel_name,),
    )
    return cur.fetchone()[0]


def clear_channel(conn: sqlite3.Connection, channel_name: str):
    """Delete ALL data for a given channel from every table."""
    for table in ("messages", "links", "channels"):
        conn.execute(f"DELETE FROM {table} WHERE channel_name = ?", (channel_name,))
    conn.commit()
