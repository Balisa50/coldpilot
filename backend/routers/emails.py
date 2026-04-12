"""Email viewing, approval, rejection, and rewriting."""
from __future__ import annotations

from fastapi import APIRouter, HTTPException

from backend import db
from backend.models import EmailAction

router = APIRouter(prefix="/api/emails", tags=["emails"])


@router.get("/campaign/{campaign_id}")
async def list_campaign_emails(campaign_id: str):
    return await db.list_emails(campaign_id)


@router.get("/pending")
async def list_pending():
    """Get all emails waiting for approval (Copilot mode)."""
    return await db.list_emails_by_status("pending_approval")


@router.get("/{email_id}")
async def get_email(email_id: str):
    email = await db.get_email(email_id)
    if not email:
        raise HTTPException(404, "Email not found")

    # Attach prospect info
    prospect = await db.get_prospect(email["prospect_id"])
    return {**email, "prospect": prospect}


@router.post("/{email_id}/approve")
async def approve_email(email_id: str):
    email = await db.get_email(email_id)
    if not email:
        raise HTTPException(404, "Email not found")
    if email["status"] != "pending_approval":
        raise HTTPException(400, f"Email is {email['status']}, not pending_approval")

    await db.update_email(email_id, {"status": "approved"})
    await db.update_prospect(email["prospect_id"], {"status": "email_approved"})
    await db.log_action("email_approved", email["campaign_id"],
                        email["prospect_id"], email_id)
    return {"approved": True}


@router.post("/{email_id}/reject")
async def reject_email(email_id: str, body: EmailAction | None = None):
    email = await db.get_email(email_id)
    if not email:
        raise HTTPException(404, "Email not found")

    feedback = body.feedback if body else None
    await db.update_email(email_id, {"status": "draft"})
    await db.log_action("email_rejected", email["campaign_id"],
                        email["prospect_id"], email_id,
                        detail={"feedback": feedback})
    return {"rejected": True, "feedback": feedback}


@router.post("/{email_id}/rewrite")
async def rewrite_email(email_id: str, body: EmailAction | None = None):
    """Regenerate the email, optionally with feedback guidance."""
    import json
    from backend.pipeline import email_writer, researcher

    email = await db.get_email(email_id)
    if not email:
        raise HTTPException(404, "Email not found")

    prospect = await db.get_prospect(email["prospect_id"])
    campaign = await db.get_campaign(email["campaign_id"])
    if not prospect or not campaign:
        raise HTTPException(404, "Related data not found")

    # Get research notes
    notes = {}
    if prospect.get("research_notes"):
        notes = json.loads(prospect["research_notes"]) if isinstance(
            prospect["research_notes"], str) else prospect["research_notes"]

    new_email = await email_writer.write_initial_email(campaign, prospect, notes)
    if not new_email:
        raise HTTPException(500, "Failed to generate email")

    await db.update_email(email_id, {
        "subject": new_email["subject"],
        "body_html": new_email["body_html"],
        "body_text": new_email["body_text"],
        "personalisation_points": new_email["personalisation_points"],
        "status": "pending_approval",
    })

    return await db.get_email(email_id)
