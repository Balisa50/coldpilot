"""
Stage 6: Schedule and execute follow-ups.

Follow-up 1 is scheduled 3 days after the initial email.
Follow-up 2 is scheduled 3 days after follow-up 1.
Maximum 2 follow-ups per contact. Never follow up if they replied, bounced, or opted out.
"""
from __future__ import annotations

from datetime import datetime, timedelta

from backend import db


async def schedule_followup(
    email_id: str,
    prospect_id: str,
    campaign_id: str,
    followup_number: int = 1,
    days_delay: int = 3,
) -> dict:
    """Schedule a follow-up N days from now."""
    scheduled_for = (datetime.utcnow() + timedelta(days=days_delay)).strftime(
        "%Y-%m-%d %H:%M:%S"
    )

    result = await db.create_followup({
        "email_id": email_id,
        "prospect_id": prospect_id,
        "campaign_id": campaign_id,
        "scheduled_for": scheduled_for,
        "followup_number": followup_number,
    })

    await db.log_action(
        "followup_scheduled",
        campaign_id=campaign_id,
        prospect_id=prospect_id,
        email_id=email_id,
        detail={
            "followup_number": followup_number,
            "scheduled_for": scheduled_for,
        },
    )

    return result


def should_followup(prospect: dict) -> bool:
    """Check if a prospect should receive a follow-up."""
    skip_statuses = {"replied", "bounced", "opted_out", "failed"}
    return prospect.get("status") not in skip_statuses
