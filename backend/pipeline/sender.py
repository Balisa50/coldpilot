"""
Stage 5: Send emails via SMTP, respecting daily limits and spacing.

Before every send we inject:
  - An unsubscribe footer (plain text + HTML) — CAN-SPAM / Gmail 2024 required

Open tracking (pixel) and click tracking (link wrapping) have been removed:
  - Pixels are blocked by default in Gmail, Outlook, and Apple Mail.
    Apple Mail pre-loads all images — every email looks "opened". Unreliable.
  - Click-wrapping rewrites every href through the backend. Spam filters flag
    this pattern and recipients see suspicious redirect URLs. Not worth it.

Replied tracking is handled via IMAP polling — that's real, reliable signal.
"""
from __future__ import annotations

import asyncio
import os
import random

from backend import db
from backend.services import smtp


def _inject_footer(
    body_html: str,
    body_text: str,
    prospect_id: str,
) -> tuple[str, str]:
    """Append unsubscribe footer to outgoing email.

    The stored email record stays clean; only the bytes sent over SMTP are modified.
    """
    backend     = os.getenv("BACKEND_URL", "http://localhost:8000").rstrip("/")
    sender_name = os.getenv("SENDER_NAME", "").strip()
    sender_co   = os.getenv("SENDER_COMPANY", "").strip()
    sender_web  = os.getenv("SENDER_WEBSITE", "").strip()

    unsub_url = f"{backend}/unsubscribe/{prospect_id}"

    # ── Signature block ────────────────────────────────────────────────────
    sig_parts: list[str] = []
    if sender_name:
        sig_parts.append(sender_name)
    if sender_co:
        sig_parts.append(sender_co)
    if sender_web:
        sig_parts.append(sender_web)

    sig_text = "\n\n" + "\n".join(sig_parts) if sig_parts else ""
    sig_html = (
        "<br><br>" + "".join(f"<div>{p}</div>" for p in sig_parts)
        if sig_parts else ""
    )

    # ── Plain-text footer ──────────────────────────────────────────────────
    new_text = body_text + sig_text + "\n\n---\n" + f"To unsubscribe: {unsub_url}"

    # ── HTML footer ────────────────────────────────────────────────────────
    footer_html = (
        '<p style="color:#9ca3af;font-size:11px;margin-top:24px;">'
        f'<a href="{unsub_url}" style="color:#9ca3af;">Unsubscribe</a>'
        "</p>"
    )
    new_html = body_html + sig_html + footer_html

    return new_html, new_text


async def can_send() -> bool:
    """Check if we're under today's daily limit."""
    sent, limit = await db.get_daily_send_count()
    return sent < limit


async def send_email(
    email_record: dict,
    prospect: dict,
    in_reply_to: str | None = None,
    user_smtp: dict | None = None,
) -> dict:
    """
    Send one email. Returns {success, error?, bounce?}.
    Enforces daily limit and records the send.

    Pass ``in_reply_to`` (the original email's Message-ID) to thread
    follow-ups into the same conversation in Gmail / Outlook / Apple Mail.
    """
    if not await can_send():
        return {"success": False, "error": "Daily send limit reached", "bounce": False}

    to = prospect.get("contact_email")
    if not to:
        return {"success": False, "error": "No email address", "bounce": False}

    backend     = os.getenv("BACKEND_URL", "http://localhost:8000").rstrip("/")
    sender_name = (
        (user_smtp.get("sender_name") if user_smtp else None)
        or os.getenv("SENDER_NAME", "").strip()
        or None
    )
    unsub_url   = f"{backend}/unsubscribe/{prospect['id']}"

    # Inject unsubscribe footer right before sending.
    # The DB record stays clean; only the bytes over the wire are augmented.
    body_html, body_text = _inject_footer(
        email_record["body_html"],
        email_record["body_text"],
        prospect["id"],
    )

    result = await smtp.send_email(
        to_email=to,
        subject=email_record["subject"],
        body_html=body_html,
        body_text=body_text,
        from_name=sender_name,
        list_unsubscribe=unsub_url,
        in_reply_to=in_reply_to,
        references=in_reply_to,
        smtp_user=user_smtp.get("smtp_user") if user_smtp else None,
        smtp_password=user_smtp.get("smtp_app_password") if user_smtp else None,
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
