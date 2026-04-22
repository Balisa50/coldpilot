"""
Tavily web search API client for company research.
Free tier: 1000 searches/month.

Search strategy (4 concurrent queries):
  Query 1 — news/events (advanced depth) — press, funding, launches
  Query 2 — hiring/updates/challenges (basic depth)
  Query 3 — LinkedIn company page (basic depth) — most reliable for local/
             small companies with no press coverage. LinkedIn company pages
             contain: about, industry, size, location, recent posts, jobs.
  Query 4 — company's own website via site:{domain} (basic depth),
             or a generic "about" query if no domain given

Each query is independently wrapped so a single Tavily failure doesn't
kill the whole research pass.
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
    Raises on HTTP error — callers use _safe_search to wrap individually.
    """
    payload = {
        "api_key": _api_key(),
        "query": query,
        "max_results": max_results,
        "search_depth": search_depth,
        "include_answer": False,  # We do our own summarisation via Groq
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
) -> list[dict]:
    """
    Like search() but returns [] on any failure instead of raising.
    Allows 4 queries to run concurrently — one failure doesn't abort the rest.
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
    Research a company using four independent concurrent search passes.

    For well-known companies (international press, Crunchbase, etc.):
      queries 1 & 2 return the best signal.

    For local/small companies (e.g. Gambian fintechs, regional businesses):
      query 3 (LinkedIn) is the PRIMARY source — almost every company has a
      LinkedIn page with their description, industry, size, location and
      recent posts even if they have zero press coverage.
      query 4 (their own website) provides additional product/service detail.

    Returns:
      summary_snippets  — all useful content, used for LLM summarisation
      linkedin_snippets — LinkedIn-only content, labelled separately
      website_snippets  — company's own website content, labelled separately
      results           — raw result list with titles and URLs
    """
    domain_hint = f" site:{company_domain}" if company_domain else ""

    # Query 1: press, funding, launches, partnerships
    news_query = (
        f'"{company_name}" 2024 2025 news announcement launch '
        f'partnership funding award{domain_hint}'
    )

    # Query 2: hiring, blog posts, product updates, challenges
    update_query = (
        f'"{company_name}" 2025 hiring product update challenge problem'
    )

    # Query 3: LinkedIn company page — most reliable for local companies
    # Prioritise the /company/ path for maximum signal
    linkedin_query = (
        f'site:linkedin.com/company "{company_name}"'
    )

    # Query 4: company's own website (if domain known) or generic about page
    if company_domain:
        website_query = f"site:{company_domain}"
    else:
        website_query = f'"{company_name}" about company services products'

    # Fire all 4 concurrently
    news_results, update_results, linkedin_results, website_results = (
        await asyncio.gather(
            _safe_search(news_query,     max_results=5, search_depth="advanced"),
            _safe_search(update_query,   max_results=4, search_depth="basic"),
            _safe_search(linkedin_query, max_results=4, search_depth="basic"),
            _safe_search(website_query,  max_results=4, search_depth="basic"),
        )
    )

    # Deduplicate across all sources, preserving priority order:
    # news > updates > linkedin > website
    seen_urls: set[str] = set()
    unique: list[dict] = []

    for r in news_results + update_results:
        if r["url"] not in seen_urls:
            seen_urls.add(r["url"])
            unique.append(r)

    unique_linkedin: list[dict] = []
    for r in linkedin_results:
        if r["url"] not in seen_urls:
            seen_urls.add(r["url"])
            unique_linkedin.append(r)
            unique.append(r)

    unique_website: list[dict] = []
    for r in website_results:
        if r["url"] not in seen_urls:
            seen_urls.add(r["url"])
            unique_website.append(r)
            unique.append(r)

    # Use 600-char snippets — 300 often cuts off before the key fact
    # (e.g. "QMoney raises $5M…" gets truncated before the amount)
    return {
        "company": company_name,
        "results": unique[:10],
        "summary_snippets":  [r["content"][:600] for r in unique[:7]],
        "linkedin_snippets": [r["content"][:600] for r in unique_linkedin[:3]],
        "website_snippets":  [r["content"][:600] for r in unique_website[:3]],
    }
