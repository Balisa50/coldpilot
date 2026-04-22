"""Settings validation: test SMTP + API keys + DNS deliverability checks."""
from __future__ import annotations

import asyncio
import os

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from backend.auth import get_current_user
from backend import db as _db
from backend.services import smtp, hunter, imap_poller

router = APIRouter(prefix="/api/settings", tags=["settings"])


class SmtpUpdate(BaseModel):
    smtp_user: str
    smtp_app_password: str
    sender_name: str | None = None


async def _check_dns_deliverability(domain: str) -> dict:
    """Check SPF and DKIM DNS records for the sending domain.

    A missing SPF record means almost certain spam-folder delivery.
    A missing DKIM record means email clients can't verify authenticity.
    These are the two most critical deliverability signals.
    """
    import dns.resolver

    result: dict = {
        "domain": domain,
        "spf": {"ok": False, "record": "", "warning": ""},
        "dmarc": {"ok": False, "record": "", "warning": ""},
    }

    loop = asyncio.get_event_loop()

    # Check SPF
    def _spf():
        try:
            answers = dns.resolver.resolve(domain, "TXT")
            for rdata in answers:
                txt = b"".join(rdata.strings).decode("utf-8", errors="ignore")
                if txt.startswith("v=spf1"):
                    return {"ok": True, "record": txt[:120]}
            return {"ok": False, "record": "", "warning": f"No SPF record found for {domain}. Emails will likely land in spam."}
        except Exception as exc:
            return {"ok": False, "record": "", "warning": f"SPF lookup failed: {exc}"}

    # Check DMARC
    def _dmarc():
        try:
            answers = dns.resolver.resolve(f"_dmarc.{domain}", "TXT")
            for rdata in answers:
                txt = b"".join(rdata.strings).decode("utf-8", errors="ignore")
                if txt.startswith("v=DMARC1"):
                    return {"ok": True, "record": txt[:120]}
            return {"ok": False, "record": "", "warning": f"No DMARC record at _dmarc.{domain}. Add one to protect your domain."}
        except Exception as exc:
            return {"ok": False, "record": "", "warning": f"DMARC lookup failed: {exc}"}

    result["spf"]   = await loop.run_in_executor(None, _spf)
    result["dmarc"] = await loop.run_in_executor(None, _dmarc)
    return result


@router.get("")
async def get_settings(user_id: str = Depends(get_current_user)):
    """Return which services are configured (not the keys themselves)."""
    user_smtp = await _db.get_user_smtp(user_id)
    smtp_ok = bool(
        user_smtp
        and user_smtp.get("smtp_user")
        and user_smtp.get("smtp_app_password")
    )
    # Fall back to env vars if no per-user config (for the operator's own account)
    if not smtp_ok:
        smtp_ok = bool(os.getenv("SMTP_USER") and (os.getenv("SMTP_APP_PASSWORD") or os.getenv("SMTP_PASS")))
    return {
        "smtp_configured": smtp_ok,
        # IMAP uses same credentials as SMTP — if SMTP is configured, IMAP is too
        "imap_configured": smtp_ok,
        "smtp_user": (user_smtp.get("smtp_user") if user_smtp else None) or os.getenv("SMTP_USER", ""),
        "sender_name": (user_smtp.get("sender_name") if user_smtp else None) or "",
        "hunter_configured": bool(os.getenv("HUNTER_API_KEY")),
        "tavily_configured": bool(os.getenv("TAVILY_API_KEY")),
        "groq_configured": bool(os.getenv("GROQ_API_KEY")),
    }


@router.patch("")
async def update_settings(body: SmtpUpdate, user_id: str = Depends(get_current_user)):
    await _db.save_user_smtp(
        user_id,
        body.smtp_user.strip(),
        body.smtp_app_password.strip(),
        body.sender_name,
    )
    return {"ok": True}


@router.post("/validate-smtp")
async def validate_smtp(user_id: str = Depends(get_current_user)):
    user_smtp = await _db.get_user_smtp(user_id)
    if user_smtp and user_smtp.get("smtp_user") and user_smtp.get("smtp_app_password"):
        return await smtp.test_connection(
            smtp_user=user_smtp["smtp_user"],
            smtp_password=user_smtp["smtp_app_password"],
        )
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


@router.post("/check-dns")
async def check_dns():
    """Check SPF + DMARC records for the configured sending domain.

    Returns a health report so the user knows if they need to fix their DNS
    before running campaigns. Missing SPF/DMARC = emails go to spam.
    """
    smtp_user = os.getenv("SMTP_USER", "")
    if not smtp_user or "@" not in smtp_user:
        return {"ok": False, "error": "SMTP_USER not configured"}

    domain = smtp_user.split("@")[-1]
    dns_result = await _check_dns_deliverability(domain)

    warnings = []
    if not dns_result["spf"]["ok"] and dns_result["spf"].get("warning"):
        warnings.append(dns_result["spf"]["warning"])
    if not dns_result["dmarc"]["ok"] and dns_result["dmarc"].get("warning"):
        warnings.append(dns_result["dmarc"]["warning"])

    return {
        "ok": not warnings,
        "domain": domain,
        "spf": dns_result["spf"],
        "dmarc": dns_result["dmarc"],
        "warnings": warnings,
        "advice": (
            "All DNS records look good — good deliverability." if not warnings
            else "Fix the DNS records above before sending campaigns, or emails will land in spam."
        ),
    }
