"""
Stage 3: Write personalised cold emails using Groq LLaMA 3.

Every email MUST contain at least one research-based personalisation.
The writer retries up to 2 times if the first attempt lacks personalisation.
"""
from __future__ import annotations

import json
from backend.services import groq_client


HUNTER_SYSTEM = """You write cold outreach emails for a business reaching out to potential clients.

Rules:
1. The email MUST contain at least one sentence that references a SPECIFIC, CONCRETE fact about the recipient's company from the research notes. Not a generic compliment — a real fact (recent news, product launch, hiring trend, specific challenge).
2. Keep the email under 150 words.
3. No salesy or pushy language. Write like a thoughtful peer, not a marketer.
4. Subject line: under 60 characters, specific to the recipient — never generic.
5. End with a clear, low-commitment call to action (e.g., "Would a 15-minute call next week work?").
6. Use the sender's name in sign-off, not "Best regards" or "Kind regards" — just the first name.

Output format (exactly this, no markdown):
SUBJECT: <subject line>
BODY: <email body as plain text>
PERSONALISATION_POINTS: <JSON array of the specific research facts you referenced>"""


SEEKER_SYSTEM = """You write cold outreach emails for a job seeker contacting companies they want to work at.

Rules:
1. The email MUST connect at least one SPECIFIC achievement or skill from the candidate's CV to something SPECIFIC happening at the company right now (from the research notes). Both sides must be concrete.
2. Keep the email under 150 words.
3. Sound genuine and confident, not desperate. You're offering value, not begging.
4. Subject line: under 60 characters, mentions the role and something specific about the company.
5. End with a low-pressure ask — an informational chat, not "please hire me".
6. Sign off with just the candidate's first name.

Output format (exactly this, no markdown):
SUBJECT: <subject line>
BODY: <email body as plain text>
PERSONALISATION_POINTS: <JSON array of [CV fact, company fact] pairs you connected>"""


FOLLOWUP_SYSTEM = """You write follow-up emails. The original email got no reply.

Rules:
1. Keep it under 80 words.
2. Reference ONE specific thing from the original email — don't repeat the whole pitch.
3. Be warm and brief, not pushy. "Just floating this back up" energy.
4. Offer to help or suggest a different angle, don't just say "checking in".
5. If this is follow-up #2 (final), acknowledge it's the last note and leave the door open.

Output format (exactly this, no markdown):
SUBJECT: Re: <original subject>
BODY: <follow-up body as plain text>
PERSONALISATION_POINTS: <JSON array with the one point you referenced>"""


def _parse_email_output(text: str) -> dict | None:
    """Parse SUBJECT/BODY/PERSONALISATION_POINTS from LLM output."""
    lines = text.strip().split("\n")
    subject = ""
    body_lines = []
    pp_raw = ""
    section = None

    for line in lines:
        if line.startswith("SUBJECT:"):
            subject = line[len("SUBJECT:"):].strip()
            section = "subject"
        elif line.startswith("BODY:"):
            body_lines.append(line[len("BODY:"):].strip())
            section = "body"
        elif line.startswith("PERSONALISATION_POINTS:"):
            pp_raw = line[len("PERSONALISATION_POINTS:"):].strip()
            section = "pp"
        elif section == "body":
            body_lines.append(line)
        elif section == "pp":
            pp_raw += line

    if not subject or not body_lines:
        return None

    body_text = "\n".join(body_lines).strip()

    # Parse personalisation points
    try:
        pp = json.loads(pp_raw) if pp_raw else []
    except json.JSONDecodeError:
        pp = []

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
        cv_excerpt = (campaign.get("cv_text") or "")[:2000]
        user_prompt = f"""Candidate CV highlights:
{cv_excerpt}

Desired role: {campaign.get('desired_role', 'not specified')}

Target company: {prospect['company_name']}
Contact: {prospect.get('contact_name', 'Hiring Manager')} — {prospect.get('contact_role', '')}

Research on {prospect['company_name']}:
Summary: {research_notes.get('summary', '')}
Recent news: {json.dumps(research_notes.get('news', []))}
Opportunities: {json.dumps(research_notes.get('opportunities', []))}

Write the cold email. Remember: connect a SPECIFIC CV achievement to something SPECIFIC at this company."""
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
            last_error = f"{type(exc).__name__}: {str(exc)[:200]}"
            continue

        result = _parse_email_output(response)
        if result and result["personalisation_points"]:
            return result

    # All retries exhausted — return the last successfully-parsed attempt if we have one
    if result:
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
