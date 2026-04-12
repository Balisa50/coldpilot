"""
Tavily web search API client for company research.
Free tier: 1000 searches/month.
"""
from __future__ import annotations

import os

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
    """
    payload = {
        "api_key": _api_key(),
        "query": query,
        "max_results": max_results,
        "search_depth": search_depth,
        "include_answer": True,
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


async def research_company(
    company_name: str,
    company_domain: str | None = None,
    context: str = "",
) -> dict:
    """
    Research a company: recent news, challenges, hiring, culture.
    Returns structured research notes.
    """
    domain_hint = f" site:{company_domain}" if company_domain else ""
    queries = [
        f'"{company_name}" recent news challenges{domain_hint}',
        f'"{company_name}" hiring team culture product launch',
    ]

    all_results = []
    for q in queries:
        results = await search(q, max_results=3)
        all_results.extend(results)

    # Deduplicate by URL
    seen_urls = set()
    unique = []
    for r in all_results:
        if r["url"] not in seen_urls:
            seen_urls.add(r["url"])
            unique.append(r)

    return {
        "company": company_name,
        "results": unique[:6],
        "summary_snippets": [r["content"][:300] for r in unique[:4]],
    }
