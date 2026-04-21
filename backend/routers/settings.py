"""Settings validation: test SMTP + API keys."""
from __future__ import annotations

import os

from fastapi import APIRouter

from backend.services import smtp, hunter, imap_poller

router = APIRouter(prefix="/api/settings", tags=["settings"])


@router.get("")
async def get_settings():
    """Return which services are configured (not the keys themselves)."""
    smtp_ok = bool(os.getenv("SMTP_USER") and os.getenv("SMTP_APP_PASSWORD"))
    return {
        "smtp_configured": smtp_ok,
        # IMAP uses same credentials as SMTP — if SMTP is configured, IMAP is too
        "imap_configured": smtp_ok,
        "smtp_user": os.getenv("SMTP_USER", ""),
        "hunter_configured": bool(os.getenv("HUNTER_API_KEY")),
        "tavily_configured": bool(os.getenv("TAVILY_API_KEY")),
        "groq_configured": bool(os.getenv("GROQ_API_KEY")),
    }


@router.post("/validate-smtp")
async def validate_smtp():
    return await smtp.test_connection()


@router.post("/validate-imap")
async def validate_imap():
    return await imap_poller.test_imap_connection()


@router.post("/validate-keys")
async def validate_keys():
    results = {}

    # Hunter
    try:
        quota = await hunter.check_quota()
        results["hunter"] = {"ok": True, **quota}
    except Exception as e:
        results["hunter"] = {"ok": False, "error": str(e)}

    # Tavily — just check that the key format is right
    tavily_key = os.getenv("TAVILY_API_KEY", "")
    results["tavily"] = {"ok": bool(tavily_key and len(tavily_key) > 10)}

    # Groq — same
    groq_key = os.getenv("GROQ_API_KEY", "")
    results["groq"] = {"ok": bool(groq_key and len(groq_key) > 10)}

    return results
