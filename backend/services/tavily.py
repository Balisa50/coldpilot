"""
Tavily web search API client for company research.
Free tier: 1000 searches/month.

Search strategy:
  Query 1 — news/events (advanced depth, more content per result)
  Query 2 — hiring/updates/challenges (basic depth)
  Query 3 — company's own website via site:{domain} (basic depth)

Each query is independently wrapped so a single Tavily failure doesn't
kill the whole research pass. Local/small companies with no press coverage
can still be researched via their own website content.
"""
from __future__ import annotations

import os
import asyncio

import httpx

TAVILY_BASE = "https://api.tavily.com"


def _api_key() -> str:
    key = os.getenv("TAVILY_API_KEY", "")
    if not key:
        raise RuntimeError("TAVILY_API_KEY not set")
    return key


async def search(
    query: str,
    max_results: int = 5,
    search_depth: str = "basic",
) -> list[dict]:
    """
    Search the web via Tavily.
    Returns list of {title, url, content, score}.
    Raises on HTTP error but does NOT swallow exceptions — callers wrap individually.
    """
    payload = {
        "api_key": _api_key(),
        "query": query,
        "max_results": max_results,
        "search_depth": search_depth,
        "include_answer": False,  # We do our own summarisation
    }

    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.post(f"{TAVILY_BASE}/search", json=payload)
        resp.raise_for_status()
        data = resp.json()

    results = data.get("results", [])
    return [
        {
            "title": r.get("title", ""),
            "url": r.get("url", ""),
            "content": r.get("content", ""),
            "score": r.get("score", 0),
        }
        for r in results
    ]


async def _safe_search(
    query: str,
    max_results: int = 5,
    search_depth: str = "basic",
    label: str = "",
) -> list[dict]:
    """
    Like search() but returns [] on any failure instead of raising.
    Lets us run 3 queries independently — one failure doesn't abort the rest.
    """
    try:
        return await search(query, max_results=max_results, search_depth=search_depth)
    except Exception:
        return []


async def research_company(
    company_name: str,
    company_domain: str | None = None,
    context: str = "",
) -> dict:
    """
    Research a company using three independent search passes:

    1. Press/news query (advanced) — finds specific recent events, funding,
       launches, partnerships. Most useful for well-known companies.
    2. Hiring/challenges query (basic) — finds job posts, blog posts,
       product updates. Often works for mid-size companies.
    3. Website query (basic, site:{domain}) — fetches the company's OWN
       pages. Critical for local/small companies with no press coverage.
       Falls back to a general "about/services" query if no domain given.

    Returns structured research notes including a `website_snippets` list
    so the researcher can label them as the company's own description.
    """
    domain_hint = f" site:{company_domain}" if company_domain else ""

    # Run all 3 queries concurrently
    news_query = (
        f'"{company_name}" 2024 2025 news announcement launch '
        f'partnership funding award{domain_hint}'
    )
    update_query = f'"{company_name}" 2025 hiring product update challenge problem'

    if company_domain:
        website_query = f"site:{company_domain}"
    else:
        website_query = f'"{company_name}" about company services products what we do'

    news_results, update_results, website_results = await asyncio.gather(
        _safe_search(news_query,    max_results=5, search_depth="advanced", label="news"),
        _safe_search(update_query,  max_results=4, search_depth="basic",    label="updates"),
        _safe_search(website_query, max_results=4, search_depth="basic",    label="website"),
    )

    # Merge and deduplicate by URL, preserving source order
    # (news results first — they're highest signal for recent events)
    seen_urls: set[str] = set()
    unique: list[dict] = []
    for r in news_results + update_results:
        if r["url"] not in seen_urls:
            seen_urls.add(r["url"])
            unique.append(r)

    # Website results kept separate so researcher can label them
    unique_website: list[dict] = []
    for r in website_results:
        if r["url"] not in seen_urls:
            seen_urls.add(r["url"])
            unique_website.append(r)
            unique.append(r)

    # Use longer snippets (600 chars) — 300 often cuts off before the
    # key fact (e.g. "QMoney raises $5M…" gets cut before the amount)
    return {
        "company": company_name,
        "results": unique[:8],
        "summary_snippets": [r["content"][:600] for r in unique[:6]],
        "website_snippets": [r["content"][:600] for r in unique_website[:3]],
    }
