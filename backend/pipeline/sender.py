"""
Stage 5: Send emails via SMTP, respecting daily limits and spacing.
"""
from __future__ import annotations

import asyncio
import random

from backend import db
from backend.services import smtp


async def can_send() -> bool:
    """Check if we're under today's daily limit."""
    sent, limit = await db.get_daily_send_count()
    return sent < limit


async def send_email(email_record: dict, prospect: dict) -> dict:
    """
    Send one email. Returns {success, error?, bounce?}.
    Enforces daily limit and records the send.
    """
    if not await can_send():
        return {"success": False, "error": "Daily send limit reached", "bounce": False}

    to = prospect.get("contact_email")
    if not to:
        return {"success": False, "error": "No email address", "bounce": False}

    result = await smtp.send_email(
        to_email=to,
        subject=email_record["subject"],
        body_html=email_record["body_html"],
        body_text=email_record["body_text"],
    )

    if result["success"]:
        await db.increment_daily_count()
        sent_updates: dict = {"status": "sent", "sent_at": db.now_iso()}
        if result.get("message_id"):
            sent_updates["message_id"] = result["message_id"]
        await db.update_email(email_record["id"], sent_updates)
        await db.update_prospect(prospect["id"], {"status": "email_sent"})
        await db.log_action(
            "email_sent",
            campaign_id=email_record["campaign_id"],
            prospect_id=prospect["id"],
            email_id=email_record["id"],
            detail={"to": to, "subject": email_record["subject"]},
        )
    elif result.get("bounce"):
        await db.update_email(email_record["id"], {
            "status": "bounced",
            "bounce_reason": result.get("error", ""),
        })
        await db.update_prospect(prospect["id"], {"status": "bounced"})
        await db.log_action(
            "bounce_detected",
            campaign_id=email_record["campaign_id"],
            prospect_id=prospect["id"],
            email_id=email_record["id"],
            detail={"error": result.get("error", "")},
        )
    else:
        await db.update_email(email_record["id"], {"status": "failed"})
        await db.log_action(
            "send_failed",
            campaign_id=email_record["campaign_id"],
            prospect_id=prospect["id"],
            email_id=email_record["id"],
            detail={"error": result.get("error", "")},
        )

    return result


async def spacing_delay() -> None:
    """Random delay between sends to avoid spam detection."""
    delay = random.uniform(45, 120)
    await asyncio.sleep(delay)
