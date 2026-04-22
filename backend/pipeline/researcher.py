"""
Stage 2: Research each target company using Tavily web search.

Produces structured research notes that the email writer uses to
personalise every outreach email.

Research quality tiers:
  "rich"  — found specific dated events (launches, funding, hires, etc.)
  "thin"  — found company description but no specific recent events
  "none"  — found nothing useful

The quality tier is written into the notes dict so the email writer
knows exactly what it has to work with — and can refuse to hallucinate
when the tier is "none".
"""
from __future__ import annotations

import json
from backend.services import tavily, groq_client


SUMMARISE_SYSTEM = """You are a research assistant preparing notes for a cold email writer.

Given raw web search results about a company, extract ONLY what is explicitly stated in the results. Never infer, assume, or invent facts.

Extract:

1. COMPANY SUMMARY (2-3 sentences)
   What the company does, what they sell or offer, what industry, approximate size/stage IF stated.
   Use their own language where possible. If you only have their website, summarise that honestly.

2. RECENT SPECIFIC EVENTS (last 12 months only)
   Product launches, funding rounds, new hires, partnerships, expansions, awards.
   Include approximate dates where stated: "launched X in March 2025", "raised $Y in late 2024".
   STRICT RULE: If you cannot find a specific event with a clear action (launched, raised, hired, partnered, expanded), leave news as an empty array [].
   Do NOT write vague items like "the company is growing" or "they are expanding their services" — those are not events.

3. PAIN POINTS (1-2 items, only if explicitly visible from the results)
4. OPPORTUNITIES (1-2 items, only if reasonably inferable from what is stated)

CRITICAL RULES:
- Empty arrays are correct and honest. Invented facts are a serious failure.
- Do NOT make up funding amounts, headcounts, product names, or dates.
- If results only contain generic company description (their about/home page), that is fine — write a good summary and leave news as [].
- Do NOT include a news item just because the search results mention the company in passing.

Output ONLY valid JSON with no extra text:
{
  "summary": "...",
  "news": [],
  "pain_points": [],
  "opportunities": []
}"""


# Specific date/event keywords that indicate a real, specific news item
_DATE_KEYWORDS = [
    "2024", "2025", "january", "february", "march", "april", "may", "june",
    "july", "august", "september", "october", "november", "december",
    "q1 ", "q2 ", "q3 ", "q4 ",
]
_EVENT_KEYWORDS = [
    "launched", "raised", "announced", "hired", "expanded", "acquired",
    "partnered", "awarded", "closed", "secured", "opened", "released",
    "series a", "series b", "seed round", "pre-seed", "ipo",
]


def _score_research_quality(notes: dict) -> str:
    """
    Score the quality of research notes.

    "rich"  — news array contains at least one item with a specific date or
              event keyword (e.g. "launched X in March 2025")
    "thin"  — has a meaningful company summary but no specific dated events
    "none"  — nothing useful: no news, summary is empty or is the fallback text
    """
    news = notes.get("news", [])
    summary = notes.get("summary", "").strip()

    # Check for specific, dateable news items
    specific_news = [
        item for item in news
        if (
            isinstance(item, str)
            and len(item) > 30
            and (
                any(kw in item.lower() for kw in _DATE_KEYWORDS)
                or any(kw in item.lower() for kw in _EVENT_KEYWORDS)
            )
        )
    ]
    if specific_news:
        return "rich"

    # No specific news — check whether we at least have a useful summary
    # (i.e. not the fallback "no recent public information found" text)
    _fallback_phrases = [
        "no recent public information found",
        "no information found",
        "could not find",
        "no public information",
    ]
    summary_useful = (
        len(summary) > 60
        and not any(phrase in summary.lower() for phrase in _fallback_phrases)
    )
    # news might have items even if none are specifically dated (e.g. "they
    # offer mobile payments and are present in 3 countries") — still "thin"
    if summary_useful or news:
        return "thin"

    return "none"


async def research(
    company_name: str,
    company_domain: str | None = None,
    context: str = "",
) -> dict:
    """
    Research a company via web search and LLM summarisation.

    Returns structured notes:
      {summary, news[], pain_points[], opportunities[],
       research_quality, raw_results[]}

    research_quality is "rich", "thin", or "none" — the email writer uses
    this to decide how to structure the email (or whether to abort).
    """
    # Step 1: Tavily search (3 concurrent queries)
    raw = await tavily.research_company(company_name, company_domain, context)
    snippets = raw.get("summary_snippets", [])
    website_snippets = raw.get("website_snippets", [])

    if not snippets and not website_snippets:
        # Zero search results — nothing to work with
        return {
            "summary": f"{company_name} — no public information found online.",
            "news": [],
            "pain_points": [],
            "opportunities": [],
            "research_quality": "none",
            "raw_results": [],
        }

    # Step 2: Build LLM prompt
    # Separate "press/news results" from "company's own website content"
    # so the LLM understands the provenance of what it's reading.
    sections: list[str] = []
    if snippets:
        sections.append(
            "=== PRESS AND WEB RESULTS ===\n"
            + "\n".join(f"- {s}" for s in snippets)
        )
    if website_snippets:
        sections.append(
            "=== COMPANY'S OWN WEBSITE CONTENT ===\n"
            "(Use this for the company summary. Only treat it as 'news' if "
            "it contains a specific dated announcement.)\n"
            + "\n".join(f"- {s}" for s in website_snippets)
        )

    user_prompt = (
        f"Company: {company_name}\n"
        f"Domain: {company_domain or 'unknown'}\n"
        f"Additional context: {context or 'none'}\n\n"
        + "\n\n".join(sections)
        + "\n\nExtract structured research notes as JSON."
    )

    notes: dict = {}
    try:
        response = await groq_client.chat(
            system=SUMMARISE_SYSTEM,
            user=user_prompt,
            temperature=0.2,     # Low temp = less creative = less hallucination
            max_tokens=600,
        )

        # Strip markdown fences if LLM wrapped in ```json
        text = response.strip()
        if text.startswith("```"):
            text = text.split("\n", 1)[1]
            text = text.rsplit("```", 1)[0]

        notes = json.loads(text)

        # Ensure all expected keys exist
        notes.setdefault("summary", "")
        notes.setdefault("news", [])
        notes.setdefault("pain_points", [])
        notes.setdefault("opportunities", [])

    except Exception:
        # LLM failed or returned malformed JSON — fall back to raw content
        # Use website snippets as summary if available (more reliable than press snippets)
        first_snippet = (website_snippets or snippets or [""])[0]
        notes = {
            "summary": first_snippet[:400] if first_snippet else f"Research on {company_name}",
            "news": [],
            "pain_points": [],
            "opportunities": [],
        }

    # Step 3: Score quality and attach metadata
    notes["research_quality"] = _score_research_quality(notes)
    notes["raw_results"] = [
        {"title": r.get("title", ""), "url": r.get("url", "")}
        for r in raw.get("results", [])[:5]
    ]

    return notes
