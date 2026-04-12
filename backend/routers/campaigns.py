"""Campaign CRUD + pipeline control + SSE stream."""
from __future__ import annotations

import asyncio
import json

from fastapi import APIRouter, BackgroundTasks, HTTPException
from fastapi.responses import StreamingResponse

from backend import db, event_bus
from backend.models import CampaignCreate, CampaignUpdate
from backend.pipeline.orchestrator import run_campaign

router = APIRouter(prefix="/api/campaigns", tags=["campaigns"])


@router.post("")
async def create_campaign(body: CampaignCreate, background: BackgroundTasks):
    data = body.model_dump()

    # For seeker mode: create prospect rows from target_companies
    target_companies = data.pop("target_companies", None) or []

    campaign = await db.create_campaign(data)

    # Auto-create prospects for seeker mode
    if body.mode == "seeker" and target_companies:
        for tc in target_companies:
            await db.create_prospect({
                "campaign_id": campaign["id"],
                "company_name": tc["company_name"],
                "company_domain": tc.get("company_domain"),
            })

    return campaign


@router.get("")
async def list_campaigns():
    campaigns = await db.list_campaigns()
    # Attach counts
    for c in campaigns:
        prospects = await db.list_prospects(c["id"])
        c["prospect_count"] = len(prospects)
        c["sent_count"] = sum(1 for p in prospects if p["status"] == "email_sent")
        c["replied_count"] = sum(1 for p in prospects if p["status"] == "replied")
    return campaigns


@router.get("/{campaign_id}")
async def get_campaign(campaign_id: str):
    campaign = await db.get_campaign(campaign_id)
    if not campaign:
        raise HTTPException(404, "Campaign not found")
    return campaign


@router.patch("/{campaign_id}")
async def update_campaign(campaign_id: str, body: CampaignUpdate):
    updates = body.model_dump(exclude_none=True)
    campaign = await db.update_campaign(campaign_id, updates)
    if not campaign:
        raise HTTPException(404, "Campaign not found")
    return campaign


@router.delete("/{campaign_id}")
async def delete_campaign(campaign_id: str):
    deleted = await db.delete_campaign(campaign_id)
    if not deleted:
        raise HTTPException(404, "Campaign not found")
    return {"deleted": True}


@router.post("/{campaign_id}/start")
async def start_campaign(campaign_id: str, background: BackgroundTasks):
    campaign = await db.get_campaign(campaign_id)
    if not campaign:
        raise HTTPException(404, "Campaign not found")
    if campaign["status"] == "active":
        raise HTTPException(400, "Campaign already running")

    await db.update_campaign(campaign_id, {"status": "active"})
    background.add_task(run_campaign, campaign_id)
    return {"started": True, "campaign_id": campaign_id}


@router.post("/{campaign_id}/pause")
async def pause_campaign(campaign_id: str):
    campaign = await db.get_campaign(campaign_id)
    if not campaign:
        raise HTTPException(404, "Campaign not found")
    await db.update_campaign(campaign_id, {"status": "paused"})
    return {"paused": True}


@router.get("/{campaign_id}/stream")
async def campaign_stream(campaign_id: str):
    """SSE endpoint for real-time pipeline progress."""
    async def event_generator():
        queue = event_bus.subscribe(campaign_id)
        try:
            while True:
                try:
                    event = await asyncio.wait_for(queue.get(), timeout=30)
                    yield f"data: {json.dumps(event)}\n\n"
                except asyncio.TimeoutError:
                    yield f": keepalive\n\n"
        except asyncio.CancelledError:
            pass
        finally:
            event_bus.unsubscribe(campaign_id, queue)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
        },
    )
