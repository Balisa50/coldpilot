"""
Stage 3: Write personalised cold emails using Groq LLaMA 3.

Two research quality tiers change how the email is structured:

  "rich"  — specific recent events found → event-led opening
  "thin"  — company description found, no specific news → value-prop opening
  "none"  — nothing found → abort Hunter, warn-but-proceed Seeker

The email writer retries up to 2 times if the first attempt lacks
personalisation or contains invented statistics.
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
    cleaned = "".join(
        c for c in text
        if c != "\ufffd" and (ord(c) >= 32 or c in "\n\r\t")
    )
    return cleaned[:max_len]


# ─────────────────────────────────────────────────────────────────────────────
# SYSTEM PROMPTS
# ─────────────────────────────────────────────────────────────────────────────

HUNTER_SYSTEM = """You write cold outreach emails from one business to a potential client or partner.

You will be told the RESEARCH QUALITY for this company: "rich" or "thin".

=== IF RESEARCH QUALITY IS "rich" (specific recent events available) ===
Structure:
1. Open with ONE specific recent event at the recipient's company. Name it precisely:
   "Saw you launched X last month", "noticed your expansion into Y in March", "saw the news about your Series A in late 2024".
   The reader should think "this person actually follows our news." Not vague — exact event.
2. Connect that event directly to what the sender does and why it matters NOW given that event. One or two sentences.
3. One-sentence ask. Small and easy: "Worth a quick call?" / "Open to 15 minutes?"

=== IF RESEARCH QUALITY IS "thin" (company description only, no specific events) ===
Structure:
1. Open with one sentence showing you understand what the company specifically does — not generic flattery.
   Example: "You run mobile money infrastructure for unbanked users in West Africa — that puts you squarely in the fraud detection problem we help fintechs solve."
   Example: "Building logistics software for SMEs means you're dealing with last-mile delivery complexity we specialise in."
   Make it specific to THEIR business, not a generic compliment.
2. One or two sentences on what the sender does and why it's directly relevant.
3. One-sentence ask.

=== RULES FOR BOTH MODES ===
Length: 4-6 sentences total. Long enough to be specific, short enough to read in 20 seconds. Never pad.

CRITICAL — facts and hallucination:
- ONLY use facts that appear in the research notes provided. Do NOT invent dollar amounts, revenue figures, headcounts, funding rounds, product names, or news items.
- If a specific fact is not in the research, do NOT include it. Use what is there.
- The sender's company description is the ONLY source for what the sender does. Do not invent services, case studies, clients, or capabilities not mentioned in that description.

Banned phrases — any email containing these fails immediately:
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

You will be told the RESEARCH QUALITY for this company: "rich" or "thin".

=== INTERNSHIP VOICE (if desired role contains "intern", "internship", or "placement") ===
Write as a student or recent graduate, eager to learn.
- Lead with a specific thing the company built or is working on that genuinely interests them — say WHY it interests them specifically. Use the research notes for this.
- If research is "thin" (no specific news), lead with what the company does and why that specific area of work matters to the seeker given their background.
- Highlight ONE relevant project, course, or skill from their CV — concrete, not "I am passionate about".
- Ask whether there is an internship or placement opportunity, or whether they would be open to a conversation.
- Professional but enthusiastic — not desperate.

=== PROFESSIONAL SEEKER VOICE (if NOT an internship role) ===
IF RESEARCH QUALITY IS "rich":
1. Open with one sentence about the company proving you looked — a recent product, decision, or news item.
2. Introduce the sender: first name, what they do. ONE concrete thing they built or achieved — a number, a project, a measurable result.
3. Connect that to the company's specific work.
4. Ask for a call.

IF RESEARCH QUALITY IS "thin":
1. Open with one sentence showing you understand what the company specifically does.
   Example: "You're building digital banking infrastructure for SMEs in The Gambia — that's exactly the kind of product engineering work I want to be doing."
2. Introduce yourself in one line. ONE concrete achievement from your CV.
3. Connect it to their work.
4. Ask for a call.

=== RULES FOR ALL MODES ===
Length: 4-6 sentences. Specific enough to be credible, short enough to read fast. Never pad.

CRITICAL — facts and hallucination:
- Company facts must come ONLY from the research notes. Do not invent any company activity, product, news, or milestone.
- CV facts must come ONLY from the CV text. Do not invent degrees, companies, projects, or metrics.
- If the CV says the seeker's name is "Abdoulie", sign off as "Abdoulie" — never invent a different name.
- Never mention any figure, statistic, or event not explicitly given to you.

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

Sign-off is the sender's first name only — pull it from their CV.

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


# ─────────────────────────────────────────────────────────────────────────────
# PARSER
# ─────────────────────────────────────────────────────────────────────────────

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

    # Fallback: no SUBJECT/BODY markers but response has content
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


# ─────────────────────────────────────────────────────────────────────────────
# HALLUCINATION GUARD
# ─────────────────────────────────────────────────────────────────────────────

def _contains_invented_stats(body: str, research_str: str) -> bool:
    """
    Return True if the email body contains dollar/million/billion figures
    that are NOT present in the research notes.
    This catches the most common class of hallucination: invented funding rounds.
    """
    import re as _re
    for m in _re.findall(
        r"\$[\d,]+[MBK]?|\d+[\s]?(?:million|billion|M|B)\s*(?:dollar|USD|\$)?",
        body, _re.IGNORECASE
    ):
        stripped = _re.sub(r"[\s,]", "", m).lower()
        if stripped not in research_str.lower():
            return True
    return False


# ─────────────────────────────────────────────────────────────────────────────
# MAIN EMAIL WRITER
# ─────────────────────────────────────────────────────────────────────────────

async def write_initial_email(
    campaign: dict,
    prospect: dict,
    research_notes: dict,
    max_retries: int = 2,
) -> dict | None:
    """
    Write the initial outreach email.
    Retries if personalisation is missing or invented stats are detected.
    Returns {subject, body_text, body_html, personalisation_points} or
    {"__error__": "..."} on unrecoverable failure.
    """
    is_seeker = campaign["mode"] == "seeker"
    system = SEEKER_SYSTEM if is_seeker else HUNTER_SYSTEM
    research_quality = research_notes.get("research_quality", "thin")

    # ── Hard abort for Hunter + zero research ──────────────────────────────
    # If we have literally nothing on this company, writing an email would
    # require the LLM to invent facts. Don't do it.
    if not is_seeker and research_quality == "none":
        return {
            "__error__": (
                f"No public information found for {prospect['company_name']}. "
                "ColdPilot cannot write a genuine personalised email without any research. "
                "Options: (1) check the company name is correct, (2) add their website domain, "
                "(3) add the contact details manually along with notes in your company description."
            )
        }

    # ── Build user prompt ──────────────────────────────────────────────────
    if is_seeker:
        cv_excerpt = _strip_binary(campaign.get("cv_text") or "", max_len=2000)
        if not cv_excerpt.strip():
            return {
                "__error__": (
                    "CV text is empty or contained only binary data. "
                    "Please re-upload your CV as a PDF so it can be parsed correctly."
                )
            }
        _full_name = (prospect.get("contact_name") or "").strip()
        recipient_name = _full_name.split()[0] if _full_name else "Hiring Manager"
        recipient_role = prospect.get("contact_role") or ""

        user_prompt = f"""RESEARCH QUALITY: {research_quality}
(rich = specific recent events available; thin = company description only, no specific events)

=== JOB SEEKER (the person WRITING this email) ===
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
Match the opening style to the RESEARCH QUALITY stated above.
Use ONLY facts present in the research notes and CV above."""

    else:
        user_prompt = f"""RESEARCH QUALITY: {research_quality}
(rich = specific recent events available; thin = company description only, no specific events)

=== SENDER ===
Company: {campaign.get('company_name', '')}
What they do: {campaign.get('company_description', '')}

=== RECIPIENT ===
{prospect.get('contact_name', 'Decision maker')} at {prospect['company_name']}
Role: {prospect.get('contact_role', '')}

=== RESEARCH ON {prospect['company_name'].upper()} ===
Summary: {research_notes.get('summary', '')}
Recent news: {json.dumps(research_notes.get('news', []))}
Pain points: {json.dumps(research_notes.get('pain_points', []))}
Opportunities: {json.dumps(research_notes.get('opportunities', []))}

Match the opening style to the RESEARCH QUALITY stated above.
Use ONLY facts present in the research notes above.
Only describe what the sender's company actually does (as stated above) — do NOT invent services, clients, case studies, or capabilities not mentioned."""

    # ── Retry loop ─────────────────────────────────────────────────────────
    last_response: str = ""
    result: dict | None = None
    last_error: str = ""
    research_str = json.dumps(research_notes)
    active_prompt = user_prompt

    for attempt in range(max_retries + 1):
        try:
            response = await groq_client.chat(
                system=system,
                user=active_prompt,
                temperature=0.7 + (attempt * 0.1),
            )
            last_response = response
        except Exception as exc:
            last_error = f"{type(exc).__name__}: {str(exc)[:300]}"
            break

        result = _parse_email_output(response)
        if not result:
            # Format glitch — retry
            continue

        # ── Hallucination guard: invented stats ──
        if _contains_invented_stats(result.get("body_text", ""), research_str):
            active_prompt = (
                user_prompt
                + "\n\nCRITICAL FAILURE: Your previous draft contained dollar figures or "
                "statistics not found in the research notes. This is hallucination and is "
                "unacceptable. Use ONLY facts explicitly listed above. No invented numbers, "
                "no revenue figures, no funding amounts unless they appear verbatim in the research."
            )
            result = None
            continue

        # ── Require some form of personalisation ──
        if not result.get("personalisation_points"):
            active_prompt = (
                user_prompt
                + "\n\nPREVIOUS ATTEMPT LACKED PERSONALISATION. Every email must reference "
                "at least one specific fact from the research or CV. Use the RESEARCH QUALITY "
                "mode described above to decide how to open. Try again."
            )
            continue

        # Passed all checks
        return result

    # ── All retries exhausted ──────────────────────────────────────────────
    # Return best parsed result even without personalisation_points —
    # better than a total failure (copilot users can still review it)
    if result and result.get("subject") and result.get("body_text"):
        return result

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
