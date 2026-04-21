"""
SQLite database layer. All DB access goes through this module.
Uses aiosqlite for async access from FastAPI.
"""
from __future__ import annotations

import json
import sqlite3
import uuid
from datetime import datetime, date
from pathlib import Path
from typing import Any

import aiosqlite

ROOT = Path(__file__).resolve().parent.parent
DB_PATH = ROOT / "data" / "coldpilot.db"
SCHEMA_PATH = Path(__file__).resolve().parent / "schema.sql"


def new_id() -> str:
    return uuid.uuid4().hex[:12]


def now_iso() -> str:
    return datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")


def today_str() -> str:
    return date.today().isoformat()


async def get_db() -> aiosqlite.Connection:
    db = await aiosqlite.connect(str(DB_PATH))
    db.row_factory = aiosqlite.Row
    await db.execute("PRAGMA journal_mode=WAL")
    await db.execute("PRAGMA foreign_keys=ON")
    return db


async def init_db() -> None:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    schema = SCHEMA_PATH.read_text(encoding="utf-8")
    db = await get_db()
    try:
        await db.executescript(schema)
        await db.commit()
        # Migrations for existing databases
        await _migrate(db)
    finally:
        await db.close()


async def _migrate(db: aiosqlite.Connection) -> None:
    """Apply schema migrations to existing databases without dropping data."""
    cols = await db.execute_fetchall("PRAGMA table_info(emails)")
    col_names = {row["name"] for row in cols}
    if "message_id" not in col_names:
        await db.execute("ALTER TABLE emails ADD COLUMN message_id TEXT")
        await db.commit()


# ─── Campaigns ───────────────────────────────────────────────

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
                cv_text, desired_role)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (cid, data["mode"], data.get("autonomy", "copilot"), data["name"],
             1 if data.get("dry_run") else 0,
             data.get("company_name"), data.get("company_url"),
             data.get("company_description"), icp,
             data.get("cv_text"), data.get("desired_role")),
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


async def list_campaigns() -> list[dict]:
    db = await get_db()
    try:
        rows = await db.execute_fetchall(
            "SELECT * FROM campaigns ORDER BY created_at DESC"
        )
        return [dict(r) for r in rows]
    finally:
        await db.close()


async def update_campaign(cid: str, updates: dict) -> dict | None:
    db = await get_db()
    try:
        sets = []
        vals = []
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
        cursor = await db.execute("DELETE FROM campaigns WHERE id = ?", (cid,))
        await db.commit()
        return cursor.rowcount > 0
    finally:
        await db.close()


# ─── Prospects ───────────────────────────────────────────────

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
        sets = []
        vals = []
        for key in ("contact_name", "contact_email", "contact_role",
                     "email_source", "email_verified", "research_notes", "status"):
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


# ─── Emails ──────────────────────────────────────────────────

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
        sets = []
        vals = []
        for key in ("status", "sent_at", "replied_at", "bounce_reason",
                     "subject", "body_html", "body_text", "personalisation_points",
                     "message_id"):
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
    """Return all sent emails (with or without message_id) — broader reply matching fallback."""
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
    """Mark an email and its prospect as replied. Idempotent."""
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
        # Cancel any pending follow-ups for this prospect
        await db.execute(
            "UPDATE followup_schedule SET status = 'cancelled' WHERE prospect_id = ? AND status = 'pending'",
            (prospect_id,),
        )
        await db.commit()
    finally:
        await db.close()


# ─── Follow-up Schedule ─────────────────────────────────────

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
        rows = await db.execute_fetchall(
            """SELECT * FROM followup_schedule
               WHERE status = 'pending' AND scheduled_for <= datetime('now')
               ORDER BY scheduled_for""",
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


# ─── Action Log ──────────────────────────────────────────────

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


# ─── Daily Send Log ─────────────────────────────────────────

async def get_daily_send_count() -> tuple[int, int]:
    """Returns (sent_today, limit_for_today)."""
    db = await get_db()
    try:
        today = today_str()
        rows = await db.execute_fetchall(
            "SELECT count, limit_for_day FROM daily_send_log WHERE date = ?",
            (today,),
        )
        if rows:
            return rows[0]["count"], rows[0]["limit_for_day"]
        # First send ever or new day — insert with default limit
        await db.execute(
            "INSERT OR IGNORE INTO daily_send_log (date, count, limit_for_day) VALUES (?, 0, 5)",
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
            """INSERT INTO daily_send_log (date, count, limit_for_day)
               VALUES (?, 1, 5)
               ON CONFLICT(date) DO UPDATE SET count = count + 1""",
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
            """INSERT INTO daily_send_log (date, count, limit_for_day)
               VALUES (?, 0, ?)
               ON CONFLICT(date) DO UPDATE SET limit_for_day = ?""",
            (today, limit, limit),
        )
        await db.commit()
    finally:
        await db.close()


# ─── Stats ───────────────────────────────────────────────────

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
