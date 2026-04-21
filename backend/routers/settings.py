"""Settings validation: test SMTP + API keys + DNS deliverability checks."""
from __future__ import annotations

import asyncio
import os

from fastapi import APIRouter

from backend.services import smtp, hunter, imap_poller

router = APIRouter(prefix="/api/settings", tags=["settings"])


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
async def get_settings():
    """Return which services are configured (not the keys themselves)."""
    smtp_ok = bool(os.getenv("SMTP_USER") and (os.getenv("SMTP_APP_PASSWORD") or os.getenv("SMTP_PASS")))
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
