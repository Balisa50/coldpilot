"""
Database layer — supports SQLite (local/dev) and PostgreSQL (production).

Set DATABASE_URL env var to use PostgreSQL (e.g. a free Supabase connection string).
Without DATABASE_URL, falls back to SQLite at data/coldpilot.db.
"""
from __future__ import annotations

import json
import os
import re
import socket
import uuid
from datetime import datetime, date, timedelta
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

# ─── Backend detection ───────────────────────────────────────────────────────
DATABASE_URL: str = os.getenv("DATABASE_URL", "")
USE_PG: bool = bool(DATABASE_URL)

if USE_PG:
    import asyncpg as _asyncpg  # type: ignore
    _pg_pool: Any = None          # asyncpg.Pool, typed as Any to avoid import issues
else:
    import aiosqlite as _aiosqlite  # type: ignore

ROOT = Path(__file__).resolve().parent.parent
DB_PATH = ROOT / "data" / "coldpilot.db"
SCHEMA_PATH = Path(__file__).resolve().parent / "schema.sql"


def new_id() -> str:
    return uuid.uuid4().hex[:12]


def now_iso() -> str:
    return datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")


def today_str() -> str:
    return date.today().isoformat()


# ─── PostgreSQL schema ───────────────────────────────────────────────────────
# TEXT for all timestamp columns so the format matches SQLite's datetime('now').
# DEFAULT uses to_char(NOW() AT TIME ZONE 'UTC', ...) to produce the same
# 'YYYY-MM-DD HH24:MI:SS' string that now_iso() and SQLite datetime('now') use.
_PG_SCHEMA = """\
CREATE TABLE IF NOT EXISTS campaigns (
    id TEXT PRIMARY KEY,
    mode TEXT NOT NULL CHECK(mode IN ('hunter','seeker')),
    autonomy TEXT NOT NULL DEFAULT 'copilot'
        CHECK(autonomy IN ('copilot','supervised','full_auto')),
    name TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'draft'
        CHECK(status IN ('draft','active','paused','completed')),
    dry_run INTEGER NOT NULL DEFAULT 0,
    company_name TEXT,
    company_url TEXT,
    company_description TEXT,
    ideal_customer_profile TEXT,
    cv_text TEXT,
    desired_role TEXT,
    created_at TEXT NOT NULL DEFAULT to_char(NOW() AT TIME ZONE 'UTC','YYYY-MM-DD HH24:MI:SS'),
    updated_at TEXT NOT NULL DEFAULT to_char(NOW() AT TIME ZONE 'UTC','YYYY-MM-DD HH24:MI:SS')
);

CREATE TABLE IF NOT EXISTS prospects (
    id TEXT PRIMARY KEY,
    campaign_id TEXT NOT NULL REFERENCES campaigns(id) ON DELETE CASCADE,
    company_name TEXT NOT NULL,
    company_domain TEXT,
    contact_name TEXT,
    contact_email TEXT,
    contact_role TEXT,
    email_source TEXT CHECK(email_source IN ('hunter','pattern_guess','manual')),
    email_verified INTEGER DEFAULT 0,
    research_notes TEXT,
    unsubscribed_at TEXT,
    status TEXT NOT NULL DEFAULT 'pending'
        CHECK(status IN ('pending','researching','contact_found',
                         'email_drafted','email_approved','email_sent',
                         'replied','bounced','opted_out','failed')),
    created_at TEXT NOT NULL DEFAULT to_char(NOW() AT TIME ZONE 'UTC','YYYY-MM-DD HH24:MI:SS'),
    updated_at TEXT NOT NULL DEFAULT to_char(NOW() AT TIME ZONE 'UTC','YYYY-MM-DD HH24:MI:SS')
);

CREATE TABLE IF NOT EXISTS emails (
    id TEXT PRIMARY KEY,
    prospect_id TEXT NOT NULL REFERENCES prospects(id) ON DELETE CASCADE,
    campaign_id TEXT NOT NULL REFERENCES campaigns(id) ON DELETE CASCADE,
    email_type TEXT NOT NULL CHECK(email_type IN ('initial','followup_1','followup_2')),
    subject TEXT NOT NULL,
    body_html TEXT NOT NULL,
    body_text TEXT NOT NULL,
    personalisation_points TEXT,
    status TEXT NOT NULL DEFAULT 'draft'
        CHECK(status IN ('draft','pending_approval','approved','sent','bounced','failed')),
    dismissed INTEGER NOT NULL DEFAULT 0,
    message_id TEXT,
    sent_at TEXT,
    replied_at TEXT,
    opened_at TEXT,
    clicked_at TEXT,
    bounce_reason TEXT,
    created_at TEXT NOT NULL DEFAULT to_char(NOW() AT TIME ZONE 'UTC','YYYY-MM-DD HH24:MI:SS')
);

CREATE TABLE IF NOT EXISTS followup_schedule (
    id TEXT PRIMARY KEY,
    email_id TEXT NOT NULL REFERENCES emails(id) ON DELETE CASCADE,
    prospect_id TEXT NOT NULL REFERENCES prospects(id) ON DELETE CASCADE,
    campaign_id TEXT NOT NULL REFERENCES campaigns(id) ON DELETE CASCADE,
    scheduled_for TEXT NOT NULL,
    followup_number INTEGER NOT NULL CHECK(followup_number IN (1,2)),
    status TEXT NOT NULL DEFAULT 'pending'
        CHECK(status IN ('pending','sent','cancelled')),
    created_at TEXT NOT NULL DEFAULT to_char(NOW() AT TIME ZONE 'UTC','YYYY-MM-DD HH24:MI:SS')
);

CREATE TABLE IF NOT EXISTS action_log (
    id TEXT PRIMARY KEY,
    campaign_id TEXT REFERENCES campaigns(id),
    prospect_id TEXT REFERENCES prospects(id),
    email_id TEXT REFERENCES emails(id),
    action TEXT NOT NULL,
    detail TEXT,
    created_at TEXT NOT NULL DEFAULT to_char(NOW() AT TIME ZONE 'UTC','YYYY-MM-DD HH24:MI:SS')
);

CREATE TABLE IF NOT EXISTS daily_send_log (
    date TEXT PRIMARY KEY,
    "count" INTEGER NOT NULL DEFAULT 0,
    limit_for_day INTEGER NOT NULL DEFAULT 5
);

CREATE INDEX IF NOT EXISTS idx_prospects_campaign ON prospects(campaign_id);
CREATE INDEX IF NOT EXISTS idx_prospects_status ON prospects(status);
CREATE INDEX IF NOT EXISTS idx_emails_prospect ON emails(prospect_id);
CREATE INDEX IF NOT EXISTS idx_emails_campaign ON emails(campaign_id);
CREATE INDEX IF NOT EXISTS idx_emails_status ON emails(status);
CREATE INDEX IF NOT EXISTS idx_followup_scheduled ON followup_schedule(scheduled_for, status);
CREATE INDEX IF NOT EXISTS idx_followup_campaign ON followup_schedule(campaign_id);
CREATE INDEX IF NOT EXISTS idx_action_log_campaign ON action_log(campaign_id);
CREATE INDEX IF NOT EXISTS idx_action_log_created ON action_log(created_at);

CREATE TABLE IF NOT EXISTS user_smtp_settings (
    user_id TEXT PRIMARY KEY,
    smtp_user TEXT,
    smtp_app_password TEXT,
    sender_name TEXT,
    smtp_host TEXT NOT NULL DEFAULT 'smtp.gmail.com',
    smtp_port INTEGER NOT NULL DEFAULT 587,
    created_at TEXT NOT NULL DEFAULT to_char(NOW() AT TIME ZONE 'UTC','YYYY-MM-DD HH24:MI:SS'),
    updated_at TEXT NOT NULL DEFAULT to_char(NOW() AT TIME ZONE 'UTC','YYYY-MM-DD HH24:MI:SS')
)\
"""


# ─── Unified connection adapter ──────────────────────────────────────────────

class _ExecResult:
    """Minimal cursor-like result from _Conn.execute(), exposing rowcount."""
    __slots__ = ("rowcount",)

    def __init__(self, rowcount: int = -1) -> None:
        self.rowcount = rowcount


class _Conn:
    """
    Wraps either an aiosqlite.Connection or an asyncpg.Connection and exposes
    a single unified interface used by every function in this module.

    Differences handled transparently:
    - ``?`` placeholders  →  ``$1 $2 ...``  (asyncpg)
    - ``INSERT OR IGNORE``  →  ``INSERT … ON CONFLICT DO NOTHING``  (asyncpg)
    - ``datetime('now')``  →  ``CURRENT_TIMESTAMP``  (asyncpg)
    - ``execute_fetchall``  →  ``fetch``  (asyncpg)
    - ``commit()`` is a no-op for asyncpg (autocommit mode)
    """

    def __init__(self, conn: Any, is_pg: bool) -> None:
        self._conn = conn
        self._is_pg = is_pg

    # ── SQL adaptation ────────────────────────────────────────────────────────

    @staticmethod
    def _adapt(sql: str, params: tuple) -> tuple[str, list]:
        """Convert SQLite-style SQL + ? params into asyncpg $n form."""
        # 1. Replace ? with $1, $2, …
        out: list[str] = []
        n = 0
        for ch in sql:
            if ch == "?":
                n += 1
                out.append(f"${n}")
            else:
                out.append(ch)
        sql = "".join(out)

        # 2. INSERT OR IGNORE  →  INSERT … ON CONFLICT DO NOTHING
        if re.search(r"\bINSERT\s+OR\s+IGNORE\b", sql, re.IGNORECASE):
            sql = re.sub(r"\bINSERT\s+OR\s+IGNORE\b", "INSERT", sql, flags=re.IGNORECASE)
            sql = sql.rstrip().rstrip(";") + " ON CONFLICT DO NOTHING"

        # 3. datetime('now')  →  CURRENT_TIMESTAMP
        sql = sql.replace("datetime('now')", "CURRENT_TIMESTAMP")

        return sql, list(params)

    # ── Core methods ──────────────────────────────────────────────────────────

    async def execute(self, sql: str, params: tuple | list = ()) -> _ExecResult:
        if self._is_pg:
            sql, params = self._adapt(sql, tuple(params))
            status: str = await self._conn.execute(sql, *params)
            try:
                rowcount = int(status.split()[-1])
            except (ValueError, IndexError):
                rowcount = -1
            return _ExecResult(rowcount)
        else:
            cursor = await self._conn.execute(sql, params)
            return _ExecResult(cursor.rowcount)

    async def execute_fetchall(self, sql: str, params: tuple | list = ()) -> list:
        if self._is_pg:
            sql, params = self._adapt(sql, tuple(params))
            rows = await self._conn.fetch(sql, *params)
            return [dict(r) for r in rows]
        else:
            return await self._conn.execute_fetchall(sql, params)

    async def executescript(self, script: str) -> None:
        """Run multiple SQL statements at once. SQLite only — used by init_db."""
        if not self._is_pg:
            await self._conn.executescript(script)

    async def commit(self) -> None:
        """Persist writes. No-op for asyncpg which uses autocommit."""
        if not self._is_pg:
            await self._conn.commit()

    async def close(self) -> None:
        if self._is_pg:
            await _pg_pool.release(self._conn)
        else:
            await self._conn.close()


# ─── Connection factory ───────────────────────────────────────────────────────

def _pg_connect_kwargs() -> dict:
    """
    Build asyncpg connection kwargs from DATABASE_URL.

    Forces IPv4 so Render (no IPv6) can reach Supabase.
    Supabase direct hosts sometimes resolve to IPv6 first — asyncpg then gets
    'Network is unreachable' because Render's network has no IPv6 route.
    """
    parsed = urlparse(DATABASE_URL)
    hostname = parsed.hostname or ""
    port     = parsed.port or 5432

    # Resolve hostname to an IPv4 address; fall back to the raw hostname if
    # resolution fails (e.g. in local dev where IPv6 works fine).
    ipv4_host = hostname
    try:
        infos = socket.getaddrinfo(hostname, port, socket.AF_INET)
        if infos:
            ipv4_host = infos[0][4][0]
    except Exception:
        pass

    kwargs: dict = {
        "host":     ipv4_host,
        "port":     port,
        "user":     parsed.username or "postgres",
        "password": parsed.password or "",
        "database": (parsed.path or "/postgres").lstrip("/") or "postgres",
        "ssl":      "require",
        "min_size": 1,
        "max_size": 5,
    }
    # PgBouncer (Supabase pooler port 6543) doesn't support prepared statements
    if "pgbouncer" in DATABASE_URL.lower() or ":6543/" in DATABASE_URL:
        kwargs["statement_cache_size"] = 0
    return kwargs


async def _ensure_pool() -> None:
    """Lazily initialise the asyncpg connection pool (called before every PG op)."""
    global _pg_pool
    if _pg_pool is None:
        _pg_pool = await _asyncpg.create_pool(**_pg_connect_kwargs())


async def get_db() -> _Conn:
    if USE_PG:
        await _ensure_pool()
        conn = await _pg_pool.acquire()
        return _Conn(conn, is_pg=True)
    else:
        raw = await _aiosqlite.connect(str(DB_PATH))
        raw.row_factory = _aiosqlite.Row
        await raw.execute("PRAGMA journal_mode=WAL")
        await raw.execute("PRAGMA foreign_keys=ON")
        return _Conn(raw, is_pg=False)


async def init_db() -> None:
    if USE_PG:
        await _init_pg()
        return
    # SQLite path
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    schema = SCHEMA_PATH.read_text(encoding="utf-8")
    db = await get_db()
    try:
        await db.executescript(schema)
        await db.commit()
        await _migrate(db)
    finally:
        await db.close()


async def _init_pg() -> None:
    """Create Postgres tables if they don't exist + run idempotent migrations."""
    await _ensure_pool()
    conn = await _pg_pool.acquire()
    try:
        for stmt in _PG_SCHEMA.split(";"):
            stmt = stmt.strip()
            if stmt:
                await conn.execute(stmt)
        # Idempotent column additions — safe to re-run on each startup
        for sql in (
            "ALTER TABLE emails ADD COLUMN IF NOT EXISTS message_id TEXT",
            "ALTER TABLE emails ADD COLUMN IF NOT EXISTS opened_at TEXT",
            "ALTER TABLE emails ADD COLUMN IF NOT EXISTS clicked_at TEXT",
            "ALTER TABLE emails ADD COLUMN IF NOT EXISTS dismissed INTEGER NOT NULL DEFAULT 0",
            "ALTER TABLE prospects ADD COLUMN IF NOT EXISTS unsubscribed_at TEXT",
            "ALTER TABLE campaigns ADD COLUMN IF NOT EXISTS user_id TEXT",
        ):
            try:
                await conn.execute(sql)
            except Exception:
                pass  # Column already exists — that's fine
    finally:
        await _pg_pool.release(conn)


async def _migrate(db: _Conn) -> None:
    """Apply schema migrations to existing SQLite DBs without dropping data."""
    if USE_PG:
        return  # Handled by _init_pg
    email_cols = {row["name"] for row in await db.execute_fetchall("PRAGMA table_info(emails)")}
    prospect_cols = {row["name"] for row in await db.execute_fetchall("PRAGMA table_info(prospects)")}
    campaign_cols = {row["name"] for row in await db.execute_fetchall("PRAGMA table_info(campaigns)")}

    migrations: list[str] = []
    if "message_id" not in email_cols:
        migrations.append("ALTER TABLE emails ADD COLUMN message_id TEXT")
    if "opened_at" not in email_cols:
        migrations.append("ALTER TABLE emails ADD COLUMN opened_at TEXT")
    if "clicked_at" not in email_cols:
        migrations.append("ALTER TABLE emails ADD COLUMN clicked_at TEXT")
    if "dismissed" not in email_cols:
        migrations.append("ALTER TABLE emails ADD COLUMN dismissed INTEGER NOT NULL DEFAULT 0")
    if "unsubscribed_at" not in prospect_cols:
        migrations.append("ALTER TABLE prospects ADD COLUMN unsubscribed_at TEXT")
    if "user_id" not in campaign_cols:
        migrations.append("ALTER TABLE campaigns ADD COLUMN user_id TEXT")

    for sql in migrations:
        await db.execute(sql)
    if migrations:
        await db.commit()


# ─── Campaigns ───────────────────────────────────────────────────────────────

async def create_campaign(data: dict) -> dict:
    db = await get_db()
    try:
        cid = new_id()
        icp = data.get("ideal_customer_profile")
        if isinstance(icp, dict):
            icp = json.dumps(icp)
        await db.execute(
            """INSERT INTO campaigns
               (id, mode, autonomy, name, dry_run,
                company_name, company_url, company_description, ideal_customer_profile,
                cv_text, desired_role, user_id)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (cid, data["mode"], data.get("autonomy", "copilot"), data["name"],
             1 if data.get("dry_run") else 0,
             data.get("company_name"), data.get("company_url"),
             data.get("company_description"), icp,
             data.get("cv_text"), data.get("desired_role"),
             data.get("user_id")),
        )
        await db.commit()
        return await get_campaign(cid)
    finally:
        await db.close()


async def get_campaign(cid: str) -> dict | None:
    db = await get_db()
    try:
        row = await db.execute_fetchall("SELECT * FROM campaigns WHERE id = ?", (cid,))
        return dict(row[0]) if row else None
    finally:
        await db.close()


async def list_campaigns(user_id: str | None = None) -> list[dict]:
    db = await get_db()
    try:
        if user_id:
            rows = await db.execute_fetchall(
                "SELECT * FROM campaigns WHERE user_id = ? ORDER BY created_at DESC",
                (user_id,),
            )
        else:
            rows = await db.execute_fetchall(
                "SELECT * FROM campaigns ORDER BY created_at DESC"
            )
        return [dict(r) for r in rows]
    finally:
        await db.close()


async def update_campaign(cid: str, updates: dict) -> dict | None:
    db = await get_db()
    try:
        sets: list[str] = []
        vals: list = []
        for key in ("name", "autonomy", "status", "dry_run",
                    "company_name", "company_url", "company_description",
                    "ideal_customer_profile", "cv_text", "desired_role"):
            if key in updates:
                val = updates[key]
                if key == "ideal_customer_profile" and isinstance(val, dict):
                    val = json.dumps(val)
                sets.append(f"{key} = ?")
                vals.append(val)
        if not sets:
            return await get_campaign(cid)
        sets.append("updated_at = ?")
        vals.append(now_iso())
        vals.append(cid)
        await db.execute(
            f"UPDATE campaigns SET {', '.join(sets)} WHERE id = ?", vals
        )
        await db.commit()
        return await get_campaign(cid)
    finally:
        await db.close()


async def delete_campaign(cid: str) -> bool:
    db = await get_db()
    try:
        result = await db.execute("DELETE FROM campaigns WHERE id = ?", (cid,))
        await db.commit()
        return result.rowcount > 0
    finally:
        await db.close()


# ─── Global suppression checks ───────────────────────────────────────────────

async def is_opted_out(email: str) -> bool:
    """Return True if this address has ever opted out from any campaign."""
    db = await get_db()
    try:
        rows = await db.execute_fetchall(
            "SELECT id FROM prospects WHERE LOWER(contact_email) = LOWER(?) AND status = 'opted_out' LIMIT 1",
            (email,),
        )
        return len(rows) > 0
    finally:
        await db.close()


async def was_recently_contacted(email: str, within_days: int = 30) -> bool:
    """Return True if we sent an email to this address within the last N days."""
    db = await get_db()
    try:
        # Pre-compute threshold in Python — avoids SQLite/Postgres datetime function differences
        threshold = (datetime.utcnow() - timedelta(days=within_days)).strftime("%Y-%m-%d %H:%M:%S")
        rows = await db.execute_fetchall(
            """SELECT e.id FROM emails e
               JOIN prospects p ON p.id = e.prospect_id
               WHERE LOWER(p.contact_email) = LOWER(?)
                 AND e.status = 'sent'
                 AND e.sent_at >= ?
               LIMIT 1""",
            (email, threshold),
        )
        return len(rows) > 0
    finally:
        await db.close()


# ─── Prospects ───────────────────────────────────────────────────────────────

async def create_prospect(data: dict) -> dict:
    db = await get_db()
    try:
        pid = new_id()
        await db.execute(
            """INSERT INTO prospects
               (id, campaign_id, company_name, company_domain, contact_name,
                contact_email, contact_role, email_source, email_verified)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (pid, data["campaign_id"], data["company_name"],
             data.get("company_domain"), data.get("contact_name"),
             data.get("contact_email"), data.get("contact_role"),
             data.get("email_source"), data.get("email_verified", 0)),
        )
        await db.commit()
        return await get_prospect(pid)
    finally:
        await db.close()


async def get_prospect(pid: str) -> dict | None:
    db = await get_db()
    try:
        row = await db.execute_fetchall("SELECT * FROM prospects WHERE id = ?", (pid,))
        return dict(row[0]) if row else None
    finally:
        await db.close()


async def list_prospects(campaign_id: str) -> list[dict]:
    db = await get_db()
    try:
        rows = await db.execute_fetchall(
            "SELECT * FROM prospects WHERE campaign_id = ? ORDER BY created_at",
            (campaign_id,),
        )
        return [dict(r) for r in rows]
    finally:
        await db.close()


async def update_prospect(pid: str, updates: dict) -> dict | None:
    db = await get_db()
    try:
        sets: list[str] = []
        vals: list = []
        for key in ("contact_name", "contact_email", "contact_role",
                    "email_source", "email_verified", "research_notes",
                    "unsubscribed_at", "status"):
            if key in updates:
                val = updates[key]
                if key == "research_notes" and isinstance(val, dict):
                    val = json.dumps(val)
                sets.append(f"{key} = ?")
                vals.append(val)
        if not sets:
            return await get_prospect(pid)
        sets.append("updated_at = ?")
        vals.append(now_iso())
        vals.append(pid)
        await db.execute(
            f"UPDATE prospects SET {', '.join(sets)} WHERE id = ?", vals
        )
        await db.commit()
        return await get_prospect(pid)
    finally:
        await db.close()


# ─── Emails ──────────────────────────────────────────────────────────────────

async def create_email(data: dict) -> dict:
    db = await get_db()
    try:
        eid = new_id()
        pp = data.get("personalisation_points")
        if isinstance(pp, list):
            pp = json.dumps(pp)
        await db.execute(
            """INSERT INTO emails
               (id, prospect_id, campaign_id, email_type, subject,
                body_html, body_text, personalisation_points, status)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (eid, data["prospect_id"], data["campaign_id"],
             data.get("email_type", "initial"), data["subject"],
             data["body_html"], data["body_text"], pp,
             data.get("status", "draft")),
        )
        await db.commit()
        return await get_email(eid)
    finally:
        await db.close()


async def get_email(eid: str) -> dict | None:
    db = await get_db()
    try:
        row = await db.execute_fetchall("SELECT * FROM emails WHERE id = ?", (eid,))
        return dict(row[0]) if row else None
    finally:
        await db.close()


async def list_emails(campaign_id: str) -> list[dict]:
    db = await get_db()
    try:
        rows = await db.execute_fetchall(
            "SELECT * FROM emails WHERE campaign_id = ? ORDER BY created_at",
            (campaign_id,),
        )
        return [dict(r) for r in rows]
    finally:
        await db.close()


async def list_emails_by_status(status: str) -> list[dict]:
    db = await get_db()
    try:
        rows = await db.execute_fetchall(
            "SELECT * FROM emails WHERE status = ? ORDER BY created_at",
            (status,),
        )
        return [dict(r) for r in rows]
    finally:
        await db.close()


async def update_email(eid: str, updates: dict) -> dict | None:
    db = await get_db()
    try:
        sets: list[str] = []
        vals: list = []
        for key in ("status", "sent_at", "replied_at", "opened_at", "clicked_at",
                    "bounce_reason", "subject", "body_html", "body_text",
                    "personalisation_points", "message_id", "dismissed"):
            if key in updates:
                val = updates[key]
                if key == "personalisation_points" and isinstance(val, list):
                    val = json.dumps(val)
                sets.append(f"{key} = ?")
                vals.append(val)
        if not sets:
            return await get_email(eid)
        vals.append(eid)
        await db.execute(
            f"UPDATE emails SET {', '.join(sets)} WHERE id = ?", vals
        )
        await db.commit()
        return await get_email(eid)
    finally:
        await db.close()


async def dismiss_email(eid: str, dismissed: bool = True) -> None:
    """Mark an email as dismissed (hidden from inbox) or restore it."""
    await update_email(eid, {"dismissed": 1 if dismissed else 0})


async def list_sent_emails_with_message_ids() -> list[dict]:
    """Return all sent emails that have a message_id — used for reply matching."""
    db = await get_db()
    try:
        rows = await db.execute_fetchall(
            """SELECT e.id, e.prospect_id, e.campaign_id, e.subject,
                      e.message_id, e.replied_at
               FROM emails e
               WHERE e.status = 'sent' AND e.message_id IS NOT NULL""",
        )
        return [dict(r) for r in rows]
    finally:
        await db.close()


async def list_all_sent_emails() -> list[dict]:
    """Return all sent emails (with or without message_id) — broader reply-matching fallback."""
    db = await get_db()
    try:
        rows = await db.execute_fetchall(
            """SELECT e.id, e.prospect_id, e.campaign_id, e.subject,
                      e.message_id, e.replied_at
               FROM emails e
               WHERE e.status = 'sent'""",
        )
        return [dict(r) for r in rows]
    finally:
        await db.close()


async def mark_replied(email_id: str, prospect_id: str) -> None:
    """Mark an email and its prospect as replied. Cancels pending follow-ups. Idempotent."""
    db = await get_db()
    try:
        ts = now_iso()
        await db.execute(
            "UPDATE emails SET replied_at = ? WHERE id = ? AND replied_at IS NULL",
            (ts, email_id),
        )
        await db.execute(
            "UPDATE prospects SET status = 'replied', updated_at = ? WHERE id = ?",
            (ts, prospect_id),
        )
        await db.execute(
            "UPDATE followup_schedule SET status = 'cancelled' WHERE prospect_id = ? AND status = 'pending'",
            (prospect_id,),
        )
        await db.commit()
    finally:
        await db.close()


async def mark_unsubscribed(prospect_id: str) -> None:
    """Mark a prospect as opted out. Cancels pending follow-ups."""
    db = await get_db()
    try:
        ts = now_iso()
        await db.execute(
            "UPDATE prospects SET status = 'opted_out', unsubscribed_at = ?, updated_at = ? WHERE id = ?",
            (ts, ts, prospect_id),
        )
        await db.execute(
            "UPDATE followup_schedule SET status = 'cancelled' WHERE prospect_id = ? AND status = 'pending'",
            (prospect_id,),
        )
        await db.commit()
    finally:
        await db.close()


# ─── Follow-up Schedule ──────────────────────────────────────────────────────

async def create_followup(data: dict) -> dict:
    db = await get_db()
    try:
        fid = new_id()
        await db.execute(
            """INSERT INTO followup_schedule
               (id, email_id, prospect_id, campaign_id, scheduled_for, followup_number)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (fid, data["email_id"], data["prospect_id"], data["campaign_id"],
             data["scheduled_for"], data["followup_number"]),
        )
        await db.commit()
        row = await db.execute_fetchall(
            "SELECT * FROM followup_schedule WHERE id = ?", (fid,)
        )
        return dict(row[0])
    finally:
        await db.close()


async def get_due_followups() -> list[dict]:
    db = await get_db()
    try:
        # Use Python-computed now() to avoid SQLite/Postgres datetime function differences
        now = now_iso()
        rows = await db.execute_fetchall(
            """SELECT * FROM followup_schedule
               WHERE status = 'pending' AND scheduled_for <= ?
               ORDER BY scheduled_for""",
            (now,),
        )
        return [dict(r) for r in rows]
    finally:
        await db.close()


async def update_followup(fid: str, status: str) -> None:
    db = await get_db()
    try:
        await db.execute(
            "UPDATE followup_schedule SET status = ? WHERE id = ?",
            (status, fid),
        )
        await db.commit()
    finally:
        await db.close()


# ─── Action Log ──────────────────────────────────────────────────────────────

async def log_action(
    action: str,
    campaign_id: str | None = None,
    prospect_id: str | None = None,
    email_id: str | None = None,
    detail: Any = None,
) -> None:
    db = await get_db()
    try:
        await db.execute(
            """INSERT INTO action_log (id, campaign_id, prospect_id, email_id, action, detail)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (new_id(), campaign_id, prospect_id, email_id, action,
             json.dumps(detail) if detail else None),
        )
        await db.commit()
    finally:
        await db.close()


async def list_actions(
    campaign_id: str | None = None,
    limit: int = 100,
    offset: int = 0,
) -> list[dict]:
    db = await get_db()
    try:
        if campaign_id:
            rows = await db.execute_fetchall(
                """SELECT * FROM action_log WHERE campaign_id = ?
                   ORDER BY created_at DESC LIMIT ? OFFSET ?""",
                (campaign_id, limit, offset),
            )
        else:
            rows = await db.execute_fetchall(
                """SELECT * FROM action_log
                   ORDER BY created_at DESC LIMIT ? OFFSET ?""",
                (limit, offset),
            )
        return [dict(r) for r in rows]
    finally:
        await db.close()


# ─── Daily Send Log ──────────────────────────────────────────────────────────

async def get_daily_send_count() -> tuple[int, int]:
    """Returns (sent_today, limit_for_today)."""
    db = await get_db()
    try:
        today = today_str()
        rows = await db.execute_fetchall(
            'SELECT "count", limit_for_day FROM daily_send_log WHERE date = ?',
            (today,),
        )
        if rows:
            return rows[0]["count"], rows[0]["limit_for_day"]
        # First send ever or new day — insert with default limit (INSERT OR IGNORE
        # is converted to ON CONFLICT DO NOTHING by _Conn._adapt for Postgres)
        await db.execute(
            'INSERT OR IGNORE INTO daily_send_log (date, "count", limit_for_day) VALUES (?, 0, 5)',
            (today,),
        )
        await db.commit()
        return 0, 5
    finally:
        await db.close()


async def increment_daily_count() -> None:
    db = await get_db()
    try:
        today = today_str()
        await db.execute(
            """INSERT INTO daily_send_log (date, "count", limit_for_day)
               VALUES (?, 1, 5)
               ON CONFLICT(date) DO UPDATE SET "count" = daily_send_log."count" + 1""",
            (today,),
        )
        await db.commit()
    finally:
        await db.close()


async def set_daily_limit(limit: int) -> None:
    db = await get_db()
    try:
        today = today_str()
        await db.execute(
            """INSERT INTO daily_send_log (date, "count", limit_for_day)
               VALUES (?, 0, ?)
               ON CONFLICT(date) DO UPDATE SET limit_for_day = ?""",
            (today, limit, limit),
        )
        await db.commit()
    finally:
        await db.close()


# ─── Stats ───────────────────────────────────────────────────────────────────

# ─── User SMTP Settings ──────────────────────────────────────────────────────

async def get_user_smtp(user_id: str) -> dict | None:
    """Return the user's saved SMTP settings, or None if not configured."""
    db = await get_db()
    try:
        rows = await db.execute_fetchall(
            "SELECT * FROM user_smtp_settings WHERE user_id = ?", (user_id,)
        )
        return dict(rows[0]) if rows else None
    finally:
        await db.close()


async def save_user_smtp(
    user_id: str,
    smtp_user: str,
    smtp_app_password: str,
    sender_name: str | None = None,
) -> None:
    """Upsert the user's SMTP credentials."""
    db = await get_db()
    try:
        await db.execute(
            """INSERT INTO user_smtp_settings (user_id, smtp_user, smtp_app_password, sender_name)
               VALUES (?, ?, ?, ?)
               ON CONFLICT(user_id) DO UPDATE SET
                 smtp_user = ?,
                 smtp_app_password = ?,
                 sender_name = ?,
                 updated_at = ?""",
            (user_id, smtp_user, smtp_app_password, sender_name,
             smtp_user, smtp_app_password, sender_name, now_iso()),
        )
        await db.commit()
    finally:
        await db.close()


# ─── Stats ───────────────────────────────────────────────────────────────────

async def get_stats() -> dict:
    db = await get_db()
    try:
        sent_today, limit_today = await get_daily_send_count()
        total_sent = (await db.execute_fetchall(
            "SELECT COUNT(*) as c FROM emails WHERE status = 'sent'"
        ))[0]["c"]
        total_replied = (await db.execute_fetchall(
            "SELECT COUNT(*) as c FROM emails WHERE replied_at IS NOT NULL"
        ))[0]["c"]
        total_bounced = (await db.execute_fetchall(
            "SELECT COUNT(*) as c FROM emails WHERE status = 'bounced'"
        ))[0]["c"]
        pending_approval = (await db.execute_fetchall(
            "SELECT COUNT(*) as c FROM emails WHERE status = 'pending_approval'"
        ))[0]["c"]
        active_campaigns = (await db.execute_fetchall(
            "SELECT COUNT(*) as c FROM campaigns WHERE status = 'active'"
        ))[0]["c"]
        return {
            "sent_today": sent_today,
            "limit_today": limit_today,
            "total_sent": total_sent,
            "total_replied": total_replied,
            "total_bounced": total_bounced,
            "reply_rate": round(total_replied / max(total_sent, 1) * 100, 1),
            "bounce_rate": round(total_bounced / max(total_sent, 1) * 100, 1),
            "pending_approval": pending_approval,
            "active_campaigns": active_campaigns,
        }
    finally:
        await db.close()
