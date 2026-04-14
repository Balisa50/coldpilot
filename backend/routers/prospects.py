"""Prospect CRUD within a campaign."""
from __future__ import annotations

from fastapi import APIRouter, HTTPException

from backend import db
from backend.models import ProspectCreate

router = APIRouter(prefix="/api/campaigns/{campaign_id}/prospects", tags=["prospects"])


@router.get("")
async def list_prospects(campaign_id: str):
    return await db.list_prospects(campaign_id)


@router.get("/{prospect_id}")
async def get_prospect(campaign_id: str, prospect_id: str):
    prospect = await db.get_prospect(prospect_id)
    if not prospect or prospect["campaign_id"] != campaign_id:
        raise HTTPException(404, "Prospect not found")
    return prospect


@router.post("")
async def create_prospect(campaign_id: str, body: ProspectCreate):
    data = body.model_dump()
    data["campaign_id"] = campaign_id
    # If user provided contact email, mark as manually sourced and skip contact-finding
    if data.get("contact_email"):
        data["email_source"] = "manual"
        data["status"] = "contact_found"
    return await db.create_prospect(data)


@router.patch("/{prospect_id}")
async def update_prospect(campaign_id: str, prospect_id: str, updates: dict):
    prospect = await db.get_prospect(prospect_id)
    if not prospect or prospect["campaign_id"] != campaign_id:
        raise HTTPException(404, "Prospect not found")
    allowed = {"contact_name", "contact_email", "contact_role", "status"}
    filtered = {k: v for k, v in updates.items() if k in allowed}
    return await db.update_prospect(prospect_id, filtered)
