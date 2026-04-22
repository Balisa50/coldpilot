"""
Stage 3: Write personalised cold emails using Groq LLaMA 3.

Every email MUST contain at least one research-based personalisation.
The writer retries up to 2 times if the first attempt lacks personalisation.
"""
from __future__ import annotations

import json
from backend.services import groq_client


def _strip_binary(text: str, max_len: int = 8000) -> str:
    """Remove control/replacement chars and cap length before prompting Groq.

    Prevents binary garbage (e.g. unparsed PDF bytes in cv_text) from
    poisoning the LLM prompt and causing it to echo PDF stream markers
    as output.
    """
    if not text:
        return ""
    # Drop every char that's a control byte (except \n, \r, \t) or U+FFFD.
    cleaned = "".join(
        c for c in text
        if c != "\ufffd" and (ord(c) >= 32 or c in "\n\r\t")
    )
    return cleaned[:max_len]


HUNTER_SYSTEM = """You write cold outreach emails from one business to a potential client or partner.

Structure of a great one:
1. Open with ONE specific recent event at the recipient's company — something that happened in the last year. Name it precisely: "I saw you launched X last month", "noticed you raised a round in [month]", "saw the news about your expansion into Y". Not "I noticed your company is growing" — that's vague and worthless. The reader should think "this person actually reads the news about us."
2. Get to the point immediately. What does the sender do, and why does it matter to THIS company right now given what you just mentioned? Connect their recent event to the sender's specific capability. One or two sentences.
3. The ask is one sentence. Small and easy to say yes to. "Worth a quick call?" "Open to 15 minutes this week?"

Length: 4-6 sentences total. Long enough to be specific, short enough to read in 20 seconds. Never pad with filler sentences.

CRITICAL — facts and hallucination:
- ONLY use facts that appear in the research notes provided. Do NOT invent dollar amounts, revenue figures, headcounts, funding rounds, product names, or news items.
- If a specific fact isn't in the research, do NOT include it. Use what's there.
- Never write things like "Google recently invested $30M" or any figure you haven't been given. If you weren't told it, it did not happen.

Banned phrases — any email containing these fails:
"I hope this email finds you well"
"I wanted to reach out"
"I came across your company"
"As a leader in [industry]"
"industry-leading" / "cutting-edge" / "best-in-class"
"I'd love to connect and explore synergies"
"help you grow" / "drive results" / "improve efficiency" (without specifics)
"Best regards" / "Kind regards"
Anything that could be sent to 1,000 companies unchanged

Subject line: something a real person would write. Specific to them. Under 60 characters.
Sign off: just the sender's first name.

Output format (exactly this, no markdown):
SUBJECT: <subject line>
BODY: <email body>
PERSONALISATION_POINTS: <JSON array of the specific research facts you used>"""


SEEKER_SYSTEM = """You write cold outreach emails from a job seeker (or internship seeker) to someone at a company they want to work at.

CRITICAL: The job seeker WRITES this. A company contact RECEIVES it. The seeker is reaching out — not being recruited.

First, check whether the desired role contains "intern", "internship", or "placement". If yes, write in INTERNSHIP VOICE:
- The sender is a student or recent graduate, eager to learn
- Lead with a specific thing the company built or is working on that genuinely interests them — and say WHY it interests them specifically
- Highlight ONE relevant project, course, or skill from their CV — something concrete, not just "I am passionate about"
- Ask if there is an internship or placement opportunity, or whether they would be open to a conversation
- Keep the tone professional but enthusiastic — not desperate

If NOT an internship, write in PROFESSIONAL SEEKER VOICE:
1. Open with one sentence about the company proving you looked — a recent product, decision, or news item. Not "I came across your company."
2. Introduce the sender in one line: first name, what they do. Give ONE concrete thing they built or achieved — a number, a project, a measurable result.
3. Connect that to the company's specific work. One sentence.
4. Ask for a call. One sentence.

Length: 4-6 sentences. Specific enough to be credible, short enough to read fast. Never pad.

CRITICAL — facts and hallucination:
- Company facts must come ONLY from the research notes provided. Do not invent any company activity, product, news, or milestone.
- CV facts must come ONLY from the CV text provided. Do not invent degrees, companies, projects, or metrics.
- If the CV says the seeker's name is "Abdoulie", sign off as "Abdoulie" — never invent a different name.
- Never mention any figure, statistic, or event you weren't explicitly given.

Banned phrases — any email containing these fails:
"I came across your company and was impressed"
"I'd love to explore how my skills can contribute"
"I'm excited about the potential"
"I'm confident that my experience"
"I'd appreciate the opportunity"
"I believe I would be a great fit"
"I am passionate about"
"I am writing to express my interest"
"Best regards" / "Kind regards"
Any sentence that could appear in any email to any company

The sign-off is the sender's first name only — pull it from their CV.

Output format (exactly this, no markdown):
SUBJECT: <subject line under 60 chars>
BODY: <email body>
PERSONALISATION_POINTS: <JSON array of [specific CV achievement, specific company fact] pairs>"""


FOLLOWUP_SYSTEM = """You write follow-up emails. The first email got no reply.

The goal is to get a response — not to resend the pitch. Most follow-ups fail because they're just "checking in" or repeating what was already said. A good follow-up does something different:
- It's short. Very short. 2-4 sentences max.
- It adds something — a new angle, a question, a relevant piece of news, a different framing of the value. Not just "I wanted to follow up on my previous email."
- It gives the recipient an easy out. Make it easy to say yes OR to say "not interested." Either response is fine.
- For a final follow-up (#2): acknowledge it's the last note. Leave the door open without being dramatic about it.

Never say: "I just wanted to follow up", "checking in", "circling back", "touching base."

Output format (exactly this, no markdown):
SUBJECT: Re: <original subject>
BODY: <follow-up body>
PERSONALISATION_POINTS: <JSON array with what you added or referenced>"""


def _parse_email_output(text: str) -> dict | None:
    """Parse SUBJECT/BODY/PERSONALISATION_POINTS from LLM output.
    Lenient: accepts lowercase keys, 'Subject Line:', markdown bold, etc."""
    if not text or not text.strip():
        return None

    import re as _re

    # Strip markdown bold, code fences, leading/trailing whitespace
    clean = text.strip()
    clean = _re.sub(r"\*\*", "", clean)
    clean = _re.sub(r"^```[a-z]*\n?", "", clean)
    clean = _re.sub(r"\n?```$", "", clean)

    # Case-insensitive field extraction
    subj_match = _re.search(r"(?:^|\n)\s*(?:subject|subject\s*line)\s*:\s*(.+)",
                            clean, _re.IGNORECASE)
    body_match = _re.search(r"(?:^|\n)\s*body\s*:\s*(.*?)(?=\n\s*personalisation|\n\s*personalization|$)",
                            clean, _re.IGNORECASE | _re.DOTALL)
    pp_match = _re.search(r"(?:^|\n)\s*personalisation[_\s]*points?\s*:\s*(.+)",
                          clean, _re.IGNORECASE | _re.DOTALL)
    if not pp_match:
        pp_match = _re.search(r"(?:^|\n)\s*personalization[_\s]*points?\s*:\s*(.+)",
                              clean, _re.IGNORECASE | _re.DOTALL)

    subject = subj_match.group(1).strip() if subj_match else ""
    body_text = body_match.group(1).strip() if body_match else ""
    pp_raw = pp_match.group(1).strip() if pp_match else ""

    # Fallback: no SUBJECT/BODY markers but response has content — treat
    # first line as subject, rest as body
    if not subject and not body_text:
        parts = clean.split("\n", 1)
        if len(parts) == 2 and len(parts[0]) < 120:
            subject = parts[0].strip(" :-*#")
            body_text = parts[1].strip()

    if not subject or not body_text:
        return None

    # Parse personalisation points (accept JSON array or comma list)
    pp: list = []
    if pp_raw:
        try:
            pp = json.loads(pp_raw)
            if not isinstance(pp, list):
                pp = [str(pp)]
        except json.JSONDecodeError:
            # Try extracting JSON array from within text
            m = _re.search(r"\[.*\]", pp_raw, _re.DOTALL)
            if m:
                try:
                    pp = json.loads(m.group(0))
                except json.JSONDecodeError:
                    pp = [pp_raw[:200]]
            else:
                pp = [s.strip() for s in pp_raw.split(",") if s.strip()][:5]

    # Convert plain text to simple HTML
    body_html = body_text.replace("\n\n", "</p><p>").replace("\n", "<br>")
    body_html = f"<p>{body_html}</p>"

    return {
        "subject": subject,
        "body_text": body_text,
        "body_html": body_html,
        "personalisation_points": pp,
    }


async def write_initial_email(
    campaign: dict,
    prospect: dict,
    research_notes: dict,
    max_retries: int = 2,
) -> dict | None:
    """
    Write the initial outreach email. Retries if personalisation is missing.
    Returns {subject, body_text, body_html, personalisation_points} or None.
    """
    is_seeker = campaign["mode"] == "seeker"
    system = SEEKER_SYSTEM if is_seeker else HUNTER_SYSTEM

    # Build the user prompt with all context
    if is_seeker:
        # Strip any binary garbage that slipped through (e.g. unparsed PDF)
        cv_excerpt = _strip_binary(campaign.get("cv_text") or "", max_len=2000)
        if not cv_excerpt.strip():
            return {
                "__error__": "CV text is empty or contained only binary data. "
                             "Please re-upload your CV as a PDF so it can be parsed correctly."
            }
        # Use first name only for the greeting — avoids "Hi AbdouAbdou Ceesay,"
        _full_name = (prospect.get('contact_name') or '').strip()
        recipient_name = _full_name.split()[0] if _full_name else 'Hiring Manager'
        recipient_role = prospect.get('contact_role') or ''
        user_prompt = f"""=== JOB SEEKER (the person WRITING this email) ===
CV:
{cv_excerpt}

Desired role: {campaign.get('desired_role', 'not specified')}

=== RECIPIENT (the person RECEIVING this email) ===
Name: {recipient_name}
Role: {recipient_role}
Company: {prospect['company_name']}

=== RESEARCH ON {prospect['company_name'].upper()} ===
Summary: {research_notes.get('summary', '')}
Recent news: {json.dumps(research_notes.get('news', []))}
Opportunities: {json.dumps(research_notes.get('opportunities', []))}

Write the email FROM the job seeker TO {recipient_name} at {prospect['company_name']}.
The job seeker introduces themselves, shows they know the company, and pitches why they are a fit."""
    else:
        user_prompt = f"""Sender's company: {campaign.get('company_name', '')}
What they do: {campaign.get('company_description', '')}

Target prospect: {prospect.get('contact_name', 'there')} at {prospect['company_name']}
Their role: {prospect.get('contact_role', '')}

Research on {prospect['company_name']}:
Summary: {research_notes.get('summary', '')}
Recent news: {json.dumps(research_notes.get('news', []))}
Pain points: {json.dumps(research_notes.get('pain_points', []))}
Opportunities: {json.dumps(research_notes.get('opportunities', []))}

Write the cold outreach email. Reference at least one SPECIFIC research fact.

STRICT RULE: Only describe what the sender's company actually does (as stated above). Do NOT invent services, case studies, past clients, or capabilities that are not mentioned in the company description. If the description says they build AI tools, say that — do not claim they do recruiting, consulting, or anything else."""

    last_response: str = ""
    result: dict | None = None
    last_error: str = ""

    for attempt in range(max_retries + 1):
        try:
            response = await groq_client.chat(
                system=system,
                user=user_prompt if attempt == 0 else user_prompt + "\n\nPREVIOUS ATTEMPT LACKED PERSONALISATION. You MUST include a specific, concrete research-based fact. Try again.",
                temperature=0.7 + (attempt * 0.1),  # Slightly more creative on retry
            )
            last_response = response
        except Exception as exc:
            # Groq client already tried all fallback models — no point
            # retrying at this level. Surface the error and stop.
            last_error = f"{type(exc).__name__}: {str(exc)[:300]}"
            break

        result = _parse_email_output(response)
        if result and result.get("personalisation_points"):
            # Sanity: reject if body contains suspicious invented stats
            # (dollar/million/billion figures not present in research notes)
            body = result.get("body_text", "")
            research_str = json.dumps(research_notes)
            import re as _re2
            invented = False
            for m in _re2.findall(r"\$[\d,]+[MBK]?|\d+[\s]?(?:million|billion|M|B)\s*(?:dollar|USD|\$)?", body, _re2.IGNORECASE):
                # If the figure doesn't appear in the research text, flag it
                stripped = _re2.sub(r"[\s,]", "", m).lower()
                if stripped not in research_str.lower():
                    invented = True
                    break
            if not invented:
                return result
            # Retry with a stronger hallucination warning
            user_prompt = user_prompt + "\n\nCRITICAL: Your previous draft contained statistics or dollar figures not found in the research. Use ONLY facts explicitly listed in the research notes. No invented numbers."
            continue
        # Parse succeeded but missing personalisation — retry with nudge.
        # If parse failed entirely, also retry in case it was a one-off
        # format glitch.

    # All retries exhausted — return the last parsed attempt even without
    # personalisation_points (better than a total failure)
    if result and result.get("subject") and result.get("body_text"):
        return result

    # Nothing parsed — return a dict with error detail so orchestrator can log it
    preview = last_response[:300] if last_response else "(no response)"
    err_detail = last_error or f"LLM did not produce SUBJECT:/BODY: format. Got: {preview}"
    return {"__error__": err_detail}


async def write_followup_email(
    original_email: dict,
    prospect: dict,
    followup_number: int,
) -> dict | None:
    """
    Write a follow-up email referencing the original.
    """
    user_prompt = f"""Original email to {prospect.get('contact_name', 'them')} at {prospect['company_name']}:
Subject: {original_email['subject']}
Body: {original_email['body_text']}

This is follow-up #{followup_number} of maximum 2.
{'This is the FINAL follow-up. Acknowledge it gracefully.' if followup_number == 2 else ''}

Write a brief, warm follow-up."""

    response = await groq_client.chat(
        system=FOLLOWUP_SYSTEM,
        user=user_prompt,
        temperature=0.6,
        max_tokens=512,
    )

    return _parse_email_output(response)
