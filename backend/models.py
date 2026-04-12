"""Pydantic models for API request/response validation."""
from __future__ import annotations

from pydantic import BaseModel, Field


# ─── Campaigns ───────────────────────────────────────────────

class IdealCustomerProfile(BaseModel):
    industry: str = ""
    company_size: str = ""
    roles: list[str] = []
    keywords: list[str] = []


class CampaignCreate(BaseModel):
    mode: str = Field(pattern="^(hunter|seeker)$")
    name: str
    autonomy: str = Field(default="copilot", pattern="^(copilot|supervised|full_auto)$")
    dry_run: bool = False

    # Hunter mode
    company_name: str | None = None
    company_url: str | None = None
    company_description: str | None = None
    ideal_customer_profile: IdealCustomerProfile | None = None

    # Seeker mode
    cv_text: str | None = None
    desired_role: str | None = None
    target_companies: list[TargetCompany] | None = None


class TargetCompany(BaseModel):
    company_name: str
    company_domain: str | None = None


# Fix forward reference
CampaignCreate.model_rebuild()


class CampaignUpdate(BaseModel):
    name: str | None = None
    autonomy: str | None = Field(default=None, pattern="^(copilot|supervised|full_auto)$")
    status: str | None = Field(default=None, pattern="^(draft|active|paused|completed)$")
    dry_run: bool | None = None


class CampaignResponse(BaseModel):
    id: str
    mode: str
    autonomy: str
    name: str
    status: str
    dry_run: int
    company_name: str | None = None
    company_url: str | None = None
    company_description: str | None = None
    ideal_customer_profile: str | None = None
    cv_text: str | None = None
    desired_role: str | None = None
    created_at: str
    updated_at: str


# ─── Prospects ───────────────────────────────────────────────

class ProspectCreate(BaseModel):
    company_name: str
    company_domain: str | None = None
    contact_name: str | None = None
    contact_email: str | None = None
    contact_role: str | None = None


class ProspectResponse(BaseModel):
    id: str
    campaign_id: str
    company_name: str
    company_domain: str | None = None
    contact_name: str | None = None
    contact_email: str | None = None
    contact_role: str | None = None
    email_source: str | None = None
    email_verified: int
    research_notes: str | None = None
    status: str
    created_at: str
    updated_at: str


# ─── Emails ──────────────────────────────────────────────────

class EmailResponse(BaseModel):
    id: str
    prospect_id: str
    campaign_id: str
    email_type: str
    subject: str
    body_html: str
    body_text: str
    personalisation_points: str | None = None
    status: str
    sent_at: str | None = None
    replied_at: str | None = None
    bounce_reason: str | None = None
    created_at: str


class EmailAction(BaseModel):
    feedback: str | None = None


# ─── Activity ────────────────────────────────────────────────

class ActionResponse(BaseModel):
    id: str
    campaign_id: str | None = None
    prospect_id: str | None = None
    email_id: str | None = None
    action: str
    detail: str | None = None
    created_at: str


# ─── Stats ───────────────────────────────────────────────────

class StatsResponse(BaseModel):
    sent_today: int
    limit_today: int
    total_sent: int
    total_replied: int
    total_bounced: int
    reply_rate: float
    bounce_rate: float
    pending_approval: int
    active_campaigns: int
