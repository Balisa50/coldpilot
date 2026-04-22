"""Campaign CRUD + pipeline control + SSE stream."""
from __future__ import annotations

import asyncio
import io
import json

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, UploadFile, File
from backend.auth import get_current_user
from fastapi.responses import StreamingResponse

from backend import db, event_bus
from backend.models import CampaignCreate, CampaignUpdate
from backend.pipeline.orchestrator import run_campaign

router = APIRouter(prefix="/api/campaigns", tags=["campaigns"])


@router.post("/parse-cv")
async def parse_cv(file: UploadFile = File(...)):
    """Extract plain text from an uploaded CV PDF.

    The dashboard uploads the raw PDF here so we never store binary bytes
    in the database as 'cv_text' (which breaks the LLM prompt).
    """
    raw = await file.read()
    if not raw:
        raise HTTPException(400, "Empty file")

    # Try pypdf first
    text = ""
    try:
        from pypdf import PdfReader
        reader = PdfReader(io.BytesIO(raw))
        pages = []
        for page in reader.pages:
            try:
                t = page.extract_text() or ""
            except Exception:
                t = ""
            if t:
                pages.append(t)
        text = "\n\n".join(pages).strip()
    except Exception as exc:
        raise HTTPException(
            400,
            f"Could not read PDF ({type(exc).__name__}). Is the file a valid PDF?",
        )

    if not text:
        raise HTTPException(
            400,
            "No text found in PDF. It may be image-based (scanned). "
            "Please paste your CV text manually.",
        )

    # Cap at something sane for LLM prompts — 8k chars is plenty of context
    text = text[:8000]

    return {
        "text": text,
        "char_count": len(text),
        "filename": file.filename or "cv.pdf",
    }


def _sanitize_cv_text(raw: str | None) -> str | None:
    """Reject/clean cv_text that is clearly raw binary (PDF bytes, etc.).

    The dashboard is supposed to POST PDFs to /parse-cv and only store
    extracted text in this field. This is a defense-in-depth check in case
    an old client or a different caller sends binary.
    """
    if not raw:
        return raw
    # Obvious binary header
    if raw.startswith("%PDF-") or raw.startswith("\x89PNG") or raw.startswith("PK\x03\x04"):
        raise HTTPException(
            400,
            "cv_text looks like raw binary (PDF/image/zip header). "
            "Upload the PDF via /api/campaigns/parse-cv first and pass the "
            "extracted text instead.",
        )
    # High ratio of control/replacement chars → binary garbage
    bad = sum(1 for c in raw if c == "\ufffd" or (ord(c) < 32 and c not in "\n\r\t"))
    if len(raw) > 50 and bad > len(raw) * 0.05:
        raise HTTPException(
            400,
            f"cv_text contains too many non-printable bytes "
            f"({bad}/{len(raw)}). Use /api/campaigns/parse-cv to extract "
            f"clean text from the PDF first.",
        )
    return raw


@router.post("")
async def create_campaign(body: CampaignCreate, background: BackgroundTasks, user_id: str = Depends(get_current_user)):
    data = body.model_dump()
    data["user_id"] = user_id

    # Defensive: reject obvious PDF/binary garbage in cv_text (legacy clients)
    data["cv_text"] = _sanitize_cv_text(data.get("cv_text"))

    # For seeker mode: create prospect rows from target_companies
    target_companies = data.pop("target_companies", None) or []

    campaign = await db.create_campaign(data)

    # Auto-create prospects from target_companies for BOTH modes.
    # Hunter mode: contact_finder will look up emails if not provided.
    # Seeker mode: user typically provides contacts; if not, contact_finder runs too.
    if target_companies:
        for tc in target_companies:
            prospect_data: dict = {
                "campaign_id": campaign["id"],
                "company_name": tc["company_name"],
                "company_domain": tc.get("company_domain"),
            }
            # If user already has contact info, include it and skip contact-finding
            if tc.get("contact_email"):
                prospect_data["contact_name"] = tc.get("contact_name")
                prospect_data["contact_email"] = tc["contact_email"]
                prospect_data["contact_role"] = tc.get("contact_role")
                prospect_data["email_source"] = "manual"
                prospect_data["status"] = "contact_found"  # skip contact-finding
            elif tc.get("contact_name") or tc.get("contact_role"):
                # Partial contact info — keep what's given, still find email
                prospect_data["contact_name"] = tc.get("contact_name")
                prospect_data["contact_role"] = tc.get("contact_role")
            await db.create_prospect(prospect_data)

    return campaign


@router.get("")
async def list_campaigns(user_id: str = Depends(get_current_user)):
    campaigns = await db.list_campaigns(user_id=user_id)
    # Attach counts
    for c in campaigns:
        prospects = await db.list_prospects(c["id"])
        c["prospect_count"] = len(prospects)
        c["sent_count"] = sum(1 for p in prospects if p["status"] == "email_sent")
        c["replied_count"] = sum(1 for p in prospects if p["status"] == "replied")
        c["bounce_count"] = sum(1 for p in prospects if p["status"] == "bounced")
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
async def start_campaign(campaign_id: str, background: BackgroundTasks, user_id: str = Depends(get_current_user)):
    campaign = await db.get_campaign(campaign_id)
    if not campaign:
        raise HTTPException(404, "Campaign not found")
    if campaign["status"] == "active":
        raise HTTPException(400, "Campaign already running")

    await db.update_campaign(campaign_id, {"status": "active"})
    background.add_task(run_campaign, campaign_id, user_id)
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
