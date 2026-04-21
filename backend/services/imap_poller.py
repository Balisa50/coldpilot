"""
IMAP reply poller.

Connects to Gmail (or any IMAP server) every 5 minutes, scans the inbox
for messages that are replies to emails ColdPilot sent, and marks the
corresponding prospect + email as replied. Pending follow-ups for that
prospect are automatically cancelled in mark_replied().

Matching strategy (in priority order):
  1. In-Reply-To header matches our stored Message-ID  (most reliable)
  2. References header contains our stored Message-ID  (thread continuation)
  3. Normalised subject match (Re: stripped) when only one sent email had that subject

Only runs if SMTP_USER and SMTP_APP_PASSWORD are set in .env — same
credentials used for sending, so no extra config needed for Gmail.
"""
from __future__ import annotations

import asyncio
import imaplib
import logging
import os
import re
from datetime import datetime, timedelta
from email import message_from_bytes
from email.header import decode_header as _decode_header

from backend import db

logger = logging.getLogger(__name__)


# ─── Config ──────────────────────────────────────────────────────────────────

def _imap_cfg() -> dict:
    return {
        "host":     os.getenv("IMAP_HOST", "imap.gmail.com"),
        "port":     int(os.getenv("IMAP_PORT", "993")),
        "user":     os.getenv("SMTP_USER", ""),
        "password": os.getenv("SMTP_APP_PASSWORD", ""),
    }


# ─── Public entry point ───────────────────────────────────────────────────────

async def poll_for_replies() -> int:
    """
    Scan inbox for replies to ColdPilot emails.
    Returns the number of new replies detected.
    """
    cfg = _imap_cfg()
    if not cfg["user"] or not cfg["password"]:
        logger.debug("IMAP not configured — skipping reply poll")
        return 0

    sent = await db.list_all_sent_emails()
    if not sent:
        return 0

    # Build lookup tables for matching
    by_msgid:   dict[str, dict] = {}
    by_subject: dict[str, list[dict]] = {}

    for e in sent:
        if e.get("message_id"):
            by_msgid[e["message_id"].strip()] = e
        norm = _norm_subject(e.get("subject", ""))
        if norm:
            by_subject.setdefault(norm, []).append(e)

    loop = asyncio.get_event_loop()
    try:
        matches = await loop.run_in_executor(
            None, _scan_inbox, cfg, by_msgid, by_subject
        )
    except Exception as exc:
        logger.error("IMAP poll error: %s", exc)
        return 0

    count = 0
    for email_id, prospect_id in matches:
        try:
            await db.mark_replied(email_id, prospect_id)
            await db.log_action(
                "reply_detected",
                prospect_id=prospect_id,
                email_id=email_id,
            )
            count += 1
            logger.info("Reply detected: email=%s prospect=%s", email_id, prospect_id)
        except Exception as exc:
            logger.error("Failed to mark reply: %s", exc)

    return count


async def test_imap_connection() -> dict:
    """Test IMAP login without scanning. Returns {ok, message}."""
    cfg = _imap_cfg()
    try:
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, _test_login, cfg)
        return {"ok": True, "message": f"Connected to {cfg['host']} as {cfg['user']}"}
    except Exception as exc:
        return {"ok": False, "message": str(exc)}


# ─── Synchronous IMAP scan (runs in thread executor) ─────────────────────────

def _scan_inbox(
    cfg: dict,
    by_msgid: dict[str, dict],
    by_subject: dict[str, list[dict]],
) -> list[tuple[str, str]]:
    """
    Open IMAP, fetch recent inbox headers, return list of (email_id, prospect_id)
    that are new replies (not already marked replied_at).
    """
    results: list[tuple[str, str]] = []

    try:
        imap = imaplib.IMAP4_SSL(cfg["host"], cfg["port"])
        imap.login(cfg["user"], cfg["password"])
        imap.select("INBOX", readonly=True)

        # Search emails received in the last 30 days
        since = (datetime.now() - timedelta(days=30)).strftime("%d-%b-%Y")
        _, data = imap.search(None, "SINCE", since)
        msg_nums = data[0].split() if data and data[0] else []

        for num in msg_nums:
            try:
                _, raw_data = imap.fetch(num, "(RFC822.HEADER)")
                if not raw_data or not raw_data[0]:
                    continue

                header_bytes = raw_data[0][1]
                msg = message_from_bytes(header_bytes)

                in_reply_to = (msg.get("In-Reply-To") or "").strip()
                references   = (msg.get("References")   or "").strip()
                subject      = _decode_val(msg.get("Subject", ""))

                matched: dict | None = None

                # 1. In-Reply-To
                if in_reply_to and in_reply_to in by_msgid:
                    matched = by_msgid[in_reply_to]

                # 2. References (space-separated list of message-ids)
                if not matched and references:
                    for ref in references.split():
                        if ref in by_msgid:
                            matched = by_msgid[ref]
                            break

                # 3. Subject fallback (only if exactly one sent email has that subject)
                if not matched and subject:
                    norm = _norm_subject(subject)
                    candidates = by_subject.get(norm, [])
                    if len(candidates) == 1:
                        matched = candidates[0]

                if matched and not matched.get("replied_at"):
                    pair = (matched["id"], matched["prospect_id"])
                    if pair not in results:
                        results.append(pair)

            except Exception:
                continue

        imap.logout()

    except imaplib.IMAP4.error as exc:
        logger.error("IMAP authentication/connection error: %s", exc)
    except Exception as exc:
        logger.error("IMAP scan failed: %s", exc)

    return results


def _test_login(cfg: dict) -> None:
    imap = imaplib.IMAP4_SSL(cfg["host"], cfg["port"])
    imap.login(cfg["user"], cfg["password"])
    imap.logout()


# ─── Helpers ─────────────────────────────────────────────────────────────────

_RE_PREFIX = re.compile(r"^\s*(re|fwd?)\s*:\s*", re.IGNORECASE)


def _norm_subject(s: str) -> str:
    """Strip Re:/Fwd: prefixes and normalise for matching."""
    s = _decode_val(s).lower().strip()
    while True:
        new = _RE_PREFIX.sub("", s).strip()
        if new == s:
            break
        s = new
    return s


def _decode_val(val: str) -> str:
    """Decode RFC2047-encoded email header value."""
    if not val:
        return ""
    parts = []
    for chunk, charset in _decode_header(val):
        if isinstance(chunk, bytes):
            parts.append(chunk.decode(charset or "utf-8", errors="replace"))
        else:
            parts.append(chunk)
    return " ".join(parts)
