"""
Stage 2: Research each target company using Tavily web search.

Produces structured research notes that the email writer uses to
personalise every outreach email. No research = no personalisation = no send.
"""
from __future__ import annotations

import json
from backend.services import tavily, groq_client


SUMMARISE_SYSTEM = """You are a research assistant preparing notes for a cold email.
Given raw search results about a company, extract:
1. A 2-sentence company summary (what they do, how big)
2. 2-3 recent news items or developments (product launches, funding, hiring, partnerships)
3. 1-2 potential pain points or challenges they might face
4. 1-2 opportunities where the sender could help

Output ONLY valid JSON with this exact structure:
{
  "summary": "...",
  "news": ["...", "..."],
  "pain_points": ["...", "..."],
  "opportunities": ["...", "..."]
}"""


async def research(
    company_name: str,
    company_domain: str | None = None,
    context: str = "",
) -> dict:
    """
    Research a company via web search and LLM summarisation.
    Returns structured notes: {summary, news[], pain_points[], opportunities[]}.
    """
    # Step 1: Tavily search
    raw = await tavily.research_company(company_name, company_domain, context)
    snippets = raw.get("summary_snippets", [])

    if not snippets:
        # No search results — return minimal notes
        return {
            "summary": f"{company_name} — no recent public information found.",
            "news": [],
            "pain_points": [],
            "opportunities": [],
            "raw_results": [],
        }

    # Step 2: LLM summarisation
    user_prompt = f"""Company: {company_name}
Domain: {company_domain or 'unknown'}
Additional context: {context}

Raw search results:
{chr(10).join(f'- {s}' for s in snippets)}

Extract structured research notes as JSON."""

    try:
        response = await groq_client.chat(
            system=SUMMARISE_SYSTEM,
            user=user_prompt,
            temperature=0.3,
            max_tokens=512,
        )

        # Parse JSON from response
        # Handle case where LLM wraps in ```json ... ```
        text = response.strip()
        if text.startswith("```"):
            text = text.split("\n", 1)[1]
            text = text.rsplit("```", 1)[0]

        notes = json.loads(text)
    except Exception:
        # LLM failed or produced malformed JSON — fall back to raw snippets
        notes = {
            "summary": snippets[0][:300] if snippets else f"Research on {company_name}",
            "news": snippets[1:3] if len(snippets) > 1 else [],
            "pain_points": [],
            "opportunities": [],
        }

    notes["raw_results"] = [
        {"title": r.get("title", ""), "url": r.get("url", "")}
        for r in raw.get("results", [])[:4]
    ]

    return notes
