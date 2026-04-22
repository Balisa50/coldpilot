"""
Email tracking endpoints.

Open and click tracking have been removed:
  - Open pixels are blocked by default in Gmail, Outlook, Apple Mail.
    Apple Mail pre-loads all images, making every email look "opened" —
    the data is noise, not signal.
  - Click-wrapping rewrites every link through the backend, which is a
    strong spam filter signal and breaks link trust for recipients.

What remains:
  /unsubscribe/{prospect_id}   — HTML unsubscribe page (CAN-SPAM required)
  /api/unsubscribe/{prospect_id} — JSON API version for programmatic opt-out

Replied tracking is handled separately via IMAP polling — that's real signal.
"""
from __future__ import annotations

import logging

from fastapi import APIRouter
from fastapi.responses import HTMLResponse, Response

from backend import db

logger = logging.getLogger(__name__)

router = APIRouter(tags=["tracking"])


# ─── Unsubscribe ──────────────────────────────────────────────────────────────

@router.get("/unsubscribe/{prospect_id}", response_class=HTMLResponse)
async def unsubscribe_page(prospect_id: str) -> HTMLResponse:
    """One-click unsubscribe: marks the prospect opted_out, returns HTML confirmation."""
    name = "there"
    try:
        prospect = await db.get_prospect(prospect_id)
        if prospect:
            name = prospect.get("contact_name") or "there"
            if prospect.get("status") != "opted_out":
                await db.mark_unsubscribed(prospect_id)
                await db.log_action(
                    "unsubscribed",
                    campaign_id=prospect.get("campaign_id"),
                    prospect_id=prospect_id,
                )
    except Exception as exc:
        logger.error("unsubscribe_page failed for %s: %s", prospect_id, exc)

    first_name = name.split()[0] if name and name != "there" else name
    return HTMLResponse(f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Unsubscribed</title>
  <style>
    *, *::before, *::after {{ box-sizing: border-box; }}
    body {{
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
      background: #f9fafb;
      display: flex;
      align-items: center;
      justify-content: center;
      min-height: 100vh;
      margin: 0;
      padding: 24px;
    }}
    .card {{
      background: #fff;
      border-radius: 12px;
      box-shadow: 0 1px 3px rgba(0,0,0,.08), 0 4px 12px rgba(0,0,0,.06);
      max-width: 480px;
      width: 100%;
      padding: 48px 40px;
      text-align: center;
    }}
    .icon {{ font-size: 2.5rem; margin-bottom: 16px; }}
    h1 {{ font-size: 1.4rem; color: #111; margin: 0 0 12px; font-weight: 600; }}
    p {{ color: #555; line-height: 1.65; margin: 0 0 10px; font-size: 0.95rem; }}
    .muted {{ color: #aaa; font-size: 0.82rem; margin-top: 20px; }}
  </style>
</head>
<body>
  <div class="card">
    <div class="icon">✓</div>
    <h1>You've been unsubscribed.</h1>
    <p>Hi {first_name} — you won't receive any more emails from us. This takes effect immediately.</p>
    <p>If this was a mistake, just reply directly to any email you received and we'll add you back.</p>
    <p class="muted">This page is safe to close.</p>
  </div>
</body>
</html>""")


@router.post("/api/unsubscribe/{prospect_id}")
async def unsubscribe_api(prospect_id: str) -> dict:
    """JSON API to opt a prospect out programmatically."""
    try:
        prospect = await db.get_prospect(prospect_id)
        if not prospect:
            return {"ok": False, "error": "Prospect not found"}
        await db.mark_unsubscribed(prospect_id)
        await db.log_action(
            "unsubscribed",
            campaign_id=prospect.get("campaign_id"),
            prospect_id=prospect_id,
        )
        return {"ok": True}
    except Exception as exc:
        logger.error("unsubscribe_api failed for %s: %s", prospect_id, exc)
        return {"ok": False, "error": str(exc)}
