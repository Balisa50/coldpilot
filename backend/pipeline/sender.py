"""
Stage 5: Send emails via SMTP, respecting daily limits and spacing.

Before every send we inject:
  - An unsubscribe footer (plain text + HTML) — CAN-SPAM compliance
  - A 1×1 open-tracking pixel (HTML only)
"""
from __future__ import annotations

import asyncio
import os
import random
import re
from urllib.parse import quote as _url_quote

from backend import db
from backend.services import smtp


def _inject_tracking(
    body_html: str,
    body_text: str,
    email_id: str,
    prospect_id: str,
) -> tuple[str, str]:
    """Append unsubscribe footer and open-tracking pixel to outgoing email.

    The stored email record stays clean; only the bytes sent over SMTP are modified.
    """
    backend     = os.getenv("BACKEND_URL", "http://localhost:8000").rstrip("/")
    sender_name = os.getenv("SENDER_NAME", "").strip()
    sender_co   = os.getenv("SENDER_COMPANY", "").strip()
    sender_web  = os.getenv("SENDER_WEBSITE", "").strip()

    unsub_url  = f"{backend}/unsubscribe/{prospect_id}"
    pixel_url  = f"{backend}/track/open/{email_id}"

    # ── Signature block (appended only if SENDER_NAME is configured) ──────
    sig_parts: list[str] = []
    if sender_name:
        sig_parts.append(sender_name)
    if sender_co:
        sig_parts.append(sender_co)
    if sender_web:
        sig_parts.append(sender_web)

    sig_text = "\n\n" + "\n".join(sig_parts) if sig_parts else ""
    sig_html = (
        "<br><br>"
        + "".join(f"<div>{p}</div>" for p in sig_parts)
        if sig_parts else ""
    )

    # ── Plain-text footer ──────────────────────────────────────────────────
    new_text = body_text + sig_text + (
        "\n\n"
        "---\n"
        f"To unsubscribe from future emails: {unsub_url}"
    )

    # ── Wrap links in the HTML body with click tracking ─────────────────────
    # Must happen on body_html BEFORE appending the footer (which contains
    # the unsubscribe link — we don't want that wrapped).
    def _wrap_link(m: re.Match) -> str:
        url = m.group(1)
        # Don't wrap: unsubscribe, mailto, tel, anchors, already-tracked links
        if (not url or url.startswith(("mailto:", "tel:", "#", f"{backend}/"))
                or "unsubscribe" in url):
            return m.group(0)
        tracked = f"{backend}/track/click/{email_id}?url={_url_quote(url, safe='')}"
        return f'href="{tracked}"'

    tracked_body = re.sub(r'href="([^"]*)"', _wrap_link, body_html)

    # ── HTML footer + invisible tracking pixel ─────────────────────────────
    footer_html = (
        '<p style="color:#9ca3af;font-size:11px;margin-top:28px;'
        'border-top:1px solid #e5e7eb;padding-top:14px;line-height:1.5">'
        "You received this message because your organisation was identified as a "
        "potential fit for our outreach. "
        f'<a href="{unsub_url}" style="color:#9ca3af;text-decoration:underline">'
        "Unsubscribe</a>"
        "</p>"
        f'<img src="{pixel_url}" width="1" height="1" '
        'alt="" style="display:block;width:1px;height:1px;opacity:0">'
    )
    new_html = tracked_body + sig_html + footer_html

    return new_html, new_text


async def can_send() -> bool:
    """Check if we're under today's daily limit."""
    sent, limit = await db.get_daily_send_count()
    return sent < limit


async def send_email(
    email_record: dict,
    prospect: dict,
    in_reply_to: str | None = None,
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

    # Inject tracking pixel + unsubscribe footer right before sending.
    # The DB record stores the clean body; only the bytes over the wire are augmented.
    body_html, body_text = _inject_tracking(
        email_record["body_html"],
        email_record["body_text"],
        email_record["id"],
        prospect["id"],
    )

    result = await smtp.send_email(
        to_email=to,
        subject=email_record["subject"],
        body_html=body_html,
        body_text=body_text,
        in_reply_to=in_reply_to,
        references=in_reply_to,  # RFC 2822: References == full chain; for 2-hop it's the same
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
