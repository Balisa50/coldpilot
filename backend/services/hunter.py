"""
Hunter.io API client for contact finding.
Free tier: 25 searches/month + 50 verifications/month.
"""
from __future__ import annotations

import os

import httpx

HUNTER_BASE = "https://api.hunter.io/v2"


def _api_key() -> str:
    key = os.getenv("HUNTER_API_KEY", "")
    if not key:
        raise RuntimeError("HUNTER_API_KEY not set")
    return key


async def domain_search(
    domain: str,
    role: str | None = None,
    limit: int = 10,
) -> list[dict]:
    """
    Search for email addresses at a domain.
    Returns list of {email, first_name, last_name, position, confidence}.
    """
    params = {
        "domain": domain,
        "api_key": _api_key(),
        "limit": limit,
    }
    if role:
        # Hunter's seniority filter: senior, executive, etc.
        # We'll use department instead for better targeting
        params["department"] = role

    async with httpx.AsyncClient(timeout=15) as client:
        resp = await client.get(f"{HUNTER_BASE}/domain-search", params=params)
        resp.raise_for_status()
        data = resp.json()

    emails = data.get("data", {}).get("emails", [])
    return [
        {
            "email": e.get("value"),
            "first_name": e.get("first_name"),
            "last_name": e.get("last_name"),
            "position": e.get("position", ""),
            "confidence": e.get("confidence", 0),
        }
        for e in emails
        if e.get("value")
    ]


async def email_finder(
    domain: str,
    first_name: str,
    last_name: str,
) -> dict | None:
    """
    Find the email for a specific person at a domain.
    Returns {email, confidence} or None.
    """
    params = {
        "domain": domain,
        "first_name": first_name,
        "last_name": last_name,
        "api_key": _api_key(),
    }

    async with httpx.AsyncClient(timeout=15) as client:
        resp = await client.get(f"{HUNTER_BASE}/email-finder", params=params)
        if resp.status_code == 404:
            return None
        resp.raise_for_status()
        data = resp.json()

    email = data.get("data", {}).get("email")
    if not email:
        return None
    return {
        "email": email,
        "confidence": data.get("data", {}).get("confidence", 0),
    }


async def verify_email(email: str) -> dict:
    """
    Verify if an email address is deliverable.
    Returns {status, result} where result is 'deliverable', 'undeliverable', 'risky', or 'unknown'.
    """
    params = {
        "email": email,
        "api_key": _api_key(),
    }

    async with httpx.AsyncClient(timeout=15) as client:
        resp = await client.get(f"{HUNTER_BASE}/email-verifier", params=params)
        resp.raise_for_status()
        data = resp.json()

    return {
        "status": data.get("data", {}).get("status", "unknown"),
        "result": data.get("data", {}).get("result", "unknown"),
    }


async def check_quota() -> dict:
    """Check remaining Hunter.io API quota."""
    params = {"api_key": _api_key()}
    async with httpx.AsyncClient(timeout=10) as client:
        resp = await client.get(f"{HUNTER_BASE}/account", params=params)
        resp.raise_for_status()
        data = resp.json()
    calls = data.get("data", {}).get("calls", {})
    return {
        "searches_used": calls.get("used", 0),
        "searches_available": calls.get("available", 0),
    }
