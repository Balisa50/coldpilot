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

Your job is to write something a real person would genuinely send — not a template, not a pitch deck, not a press release. A real human wrote this, thought about this specific company, and decided it was worth reaching out.

What makes a great cold email:
- It opens with something SPECIFIC to them — a recent move they made, something they're building, a problem their industry is facing right now. Not "I came across your company." Not "Congratulations on your growth." Something real.
- It gets to the point fast. The recipient is busy. Two or three sentences in, they should know exactly what you're offering and why it matters to them specifically.
- It doesn't oversell. No "industry-leading", no "cutting-edge", no "I'd love to connect and explore synergies." Just direct, confident, human language.
- The ask is small. Not "let's schedule a demo." Something like "worth a quick call?" or "open to a short chat this week?"
- The length fits the message. If the value is obvious in 4 sentences, write 4 sentences. If there's a story worth telling or context worth giving, write more. Never pad, never cut substance just to hit a word count.

What to absolutely avoid:
- "I hope this email finds you well" — never
- "I wanted to reach out" — never
- "As a leader in [industry]" — never
- Any phrase that sounds like it came from a sales training manual
- Vague claims without specifics ("help you grow", "drive results", "improve efficiency")
- Sounding like ChatGPT wrote it

Subject line: make it feel like it came from a real person who did their homework. Specific, not clickbait, not generic. Under 60 characters.

Sign off: just the sender's first name. No titles, no "Best regards."

Output format (exactly this, no markdown):
SUBJECT: <subject line>
BODY: <email body>
PERSONALISATION_POINTS: <JSON array of the specific research facts you used>"""


SEEKER_SYSTEM = """You write cold outreach emails from a job seeker to someone at a company they want to work at.

CRITICAL DIRECTION: The job seeker is WRITING this email. A person at the company is RECEIVING it.
The seeker is introducing themselves and expressing genuine interest. They are NOT being recruited.

Your job is to write something that would actually make a busy hiring manager or founder stop and reply — not delete it immediately.

What separates a cold email that gets a reply from one that gets deleted:
- It doesn't open with "I am writing to express my interest in opportunities at your company." That goes straight to trash.
- It opens with something that shows the sender actually knows the company. A specific product decision, a recent hire, a launch, something from the news. One sentence that proves this isn't a mass email.
- It then connects that to something concrete the sender has actually built or achieved. Not skills listed on a CV — something they DID. A number, a project, a result.
- It's honest about why this company specifically. Not "I'm passionate about innovation." What specifically about this company made them reach out today?
- The ask is low pressure. "Would you be open to a 20-minute call?" Not "I'd love to join your team and contribute to your mission."
- The length fits the story. If it's a straightforward pitch, keep it tight. If there's context worth giving, give it. Never pad.

What to absolutely avoid:
- "I hope this finds you well"
- "I am passionate about [vague thing]"
- "I believe I would be a great fit"
- "I would love the opportunity to"
- Any phrase a cover letter template would use
- Sounding like a robot summarising a CV

The sign-off is just the sender's first name — pull it from their CV.

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
        recipient_name = prospect.get('contact_name') or 'Hiring Manager'
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

Write the cold outreach email. Reference at least one SPECIFIC research fact."""

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
            return result
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
