"""Action log + stats endpoints."""
from __future__ import annotations

from fastapi import APIRouter

from backend import db

router = APIRouter(tags=["activity"])


@router.get("/api/activity")
async def global_activity(limit: int = 100, offset: int = 0):
    return await db.list_actions(limit=limit, offset=offset)


@router.get("/api/campaigns/{campaign_id}/activity")
async def campaign_activity(campaign_id: str, limit: int = 100, offset: int = 0):
    return await db.list_actions(campaign_id=campaign_id, limit=limit, offset=offset)


@router.get("/api/stats")
async def stats():
    return await db.get_stats()
