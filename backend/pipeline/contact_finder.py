"""
Stage 1: Find the right person to contact at each target company.

Hunter mode: finds decision-makers matching the ideal customer profile.
Seeker mode: finds hiring managers, dept heads, or HR contacts.

Falls back to email pattern guessing when Hunter.io quota runs out.
"""
from __future__ import annotations

import asyncio
import dns.resolver
from backend.services import hunter
from backend import db


# Common email patterns for fallback guessing
PATTERNS = [
    "{first}.{last}@{domain}",
    "{first}{last}@{domain}",
    "{f}{last}@{domain}",
    "{first}@{domain}",
    "{first}_{last}@{domain}",
]


def _domain_has_mx(domain: str) -> bool:
    """Check if the domain has MX records (can receive email)."""
    try:
        dns.resolver.resolve(domain, "MX")
        return True
    except Exception:
        return False


def _guess_emails(first: str, last: str, domain: str) -> list[str]:
    """Generate probable email addresses from name + domain."""
    first = first.lower().strip()
    last = last.lower().strip()
    f = first[0] if first else ""
    return [
        p.format(first=first, last=last, f=f, domain=domain)
        for p in PATTERNS
    ]


async def find_contacts_hunter_mode(
    prospect_id: str,
    company_domain: str,
    target_roles: list[str],
) -> dict | None:
    """
    Hunter mode: search the domain for people in target roles.
    Returns the best match or None.
    """
    try:
        results = await hunter.domain_search(company_domain, limit=10)
    except Exception:
        results = []

    if not results:
        return None

    # Score: prefer people whose position matches a target role keyword
    role_keywords = [r.lower() for r in target_roles]

    def score(person: dict) -> int:
        pos = (person.get("position") or "").lower()
        s = person.get("confidence", 0)
        for kw in role_keywords:
            if kw in pos:
                s += 100
        return s

    results.sort(key=score, reverse=True)
    best = results[0]

    return {
        "contact_name": f"{best.get('first_name', '')} {best.get('last_name', '')}".strip(),
        "contact_email": best["email"],
        "contact_role": best.get("position", ""),
        "email_source": "hunter",
        "email_verified": 1 if best.get("confidence", 0) >= 80 else 0,
    }


async def find_contacts_seeker_mode(
    prospect_id: str,
    company_domain: str,
    desired_role: str,
) -> dict | None:
    """
    Seeker mode: find someone in hiring/HR or the relevant department.
    """
    # Try department-specific search first
    dept_map = {
        "engineer": "engineering",
        "developer": "engineering",
        "software": "engineering",
        "data": "engineering",
        "design": "design",
        "product": "management",
        "marketing": "marketing",
        "sales": "sales",
        "finance": "finance",
    }
    department = None
    for keyword, dept in dept_map.items():
        if keyword in desired_role.lower():
            department = dept
            break

    try:
        # First try to find someone in the relevant department
        results = await hunter.domain_search(
            company_domain,
            role=department or "management",
            limit=10,
        )
    except Exception:
        results = []

    if not results:
        # Fall back to generic search
        try:
            results = await hunter.domain_search(company_domain, limit=5)
        except Exception:
            results = []

    if not results:
        return None

    # Prefer: hiring manager > dept head > HR > anyone senior
    hiring_keywords = ["recruit", "talent", "hiring", "hr", "human resource", "people"]
    dept_keywords = [desired_role.lower(), department or ""]
    senior_keywords = ["head", "director", "vp", "chief", "lead", "manager", "senior"]

    def score(person: dict) -> int:
        pos = (person.get("position") or "").lower()
        s = person.get("confidence", 0)
        for kw in hiring_keywords:
            if kw in pos:
                s += 200
        for kw in dept_keywords:
            if kw and kw in pos:
                s += 150
        for kw in senior_keywords:
            if kw in pos:
                s += 50
        return s

    results.sort(key=score, reverse=True)
    best = results[0]

    return {
        "contact_name": f"{best.get('first_name', '')} {best.get('last_name', '')}".strip(),
        "contact_email": best["email"],
        "contact_role": best.get("position", ""),
        "email_source": "hunter",
        "email_verified": 1 if best.get("confidence", 0) >= 80 else 0,
    }


async def find_contact_fallback(
    prospect_id: str,
    company_domain: str,
    contact_name: str | None = None,
) -> dict | None:
    """
    Fallback: guess email patterns. Only works if we have a name.
    """
    if not contact_name or not company_domain:
        return None

    if not _domain_has_mx(company_domain):
        return None

    parts = contact_name.strip().split()
    if len(parts) < 2:
        return None

    first, last = parts[0], parts[-1]
    guesses = _guess_emails(first, last, company_domain)

    # We can't verify without actually sending (SMTP RCPT TO is widely blocked).
    # Return the most common pattern as best guess.
    return {
        "contact_email": guesses[0],  # first.last@domain
        "email_source": "pattern_guess",
        "email_verified": 0,
    }


async def find_contact(
    prospect: dict,
    campaign: dict,
) -> dict | None:
    """
    Main entry point. Tries Hunter.io first, falls back to pattern guessing.
    Returns contact info dict or None.
    """
    domain = prospect.get("company_domain")
    if not domain:
        return None

    result = None

    if campaign["mode"] == "hunter":
        # Parse target roles from ICP
        import json
        icp = campaign.get("ideal_customer_profile") or "{}"
        if isinstance(icp, str):
            icp = json.loads(icp)
        roles = icp.get("roles", ["CEO", "CTO", "VP", "Director", "Manager"])
        result = await find_contacts_hunter_mode(prospect["id"], domain, roles)
    else:
        result = await find_contacts_seeker_mode(
            prospect["id"], domain, campaign.get("desired_role", "")
        )

    # Fallback to pattern guessing if Hunter found nothing
    if not result and prospect.get("contact_name"):
        result = await find_contact_fallback(
            prospect["id"], domain, prospect["contact_name"]
        )

    return result
