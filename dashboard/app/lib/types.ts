// ─── Campaigns ──────────────────────────────────────────

export type CampaignMode = "hunter" | "seeker";
export type AutonomyLevel = "copilot" | "supervised" | "full_auto";
export type CampaignStatus = "draft" | "active" | "paused" | "completed";

export interface IdealCustomerProfile {
  industry: string;
  company_size: string;
  roles: string[];
  keywords: string[];
}

export interface Campaign {
  id: string;
  mode: CampaignMode;
  autonomy: AutonomyLevel;
  name: string;
  status: CampaignStatus;
  dry_run: boolean;
  company_name: string | null;
  company_url: string | null;
  company_description: string | null;
  ideal_customer_profile: string | null;
  cv_text: string | null;
  desired_role: string | null;
  created_at: string;
  updated_at: string;
  // Attached by list endpoint
  prospect_count?: number;
  sent_count?: number;
  replied_count?: number;
  bounce_count?: number;
}

export interface TargetCompany {
  company_name: string;
  company_domain?: string;
  contact_name?: string;
  contact_email?: string;
  contact_role?: string;
}

export interface CampaignCreatePayload {
  mode: CampaignMode;
  name: string;
  autonomy: AutonomyLevel;
  dry_run: boolean;
  // Hunter
  company_name?: string;
  company_url?: string;
  company_description?: string;
  ideal_customer_profile?: IdealCustomerProfile;
  // Seeker
  cv_text?: string;
  desired_role?: string;
  target_companies?: TargetCompany[];
}

// ─── Prospects ──────────────────────────────────────────

export type ProspectStatus =
  | "pending"
  | "researching"
  | "contact_found"
  | "email_drafted"
  | "email_approved"
  | "email_sent"
  | "replied"
  | "bounced"
  | "opted_out"
  | "failed";

export interface Prospect {
  id: string;
  campaign_id: string;
  company_name: string;
  company_domain: string | null;
  contact_name: string | null;
  contact_email: string | null;
  contact_role: string | null;
  email_source: string | null;
  email_verified: boolean;
  research_notes: string | null;
  status: ProspectStatus;
  created_at: string;
  updated_at: string;
}

// ─── Emails ──────────────────────────────────────────

export type EmailStatus =
  | "draft"
  | "pending_approval"
  | "approved"
  | "sent"
  | "bounced"
  | "failed";

export interface Email {
  id: string;
  prospect_id: string;
  campaign_id: string;
  email_type: "initial" | "followup_1" | "followup_2";
  subject: string;
  body_html: string;
  body_text: string;
  personalisation_points: string | null;
  status: EmailStatus;
  dismissed: number;  // 0 = visible, 1 = dismissed
  message_id: string | null;
  sent_at: string | null;
  replied_at: string | null;
  bounce_reason: string | null;
  created_at: string;
  prospect?: Prospect;
}

// ─── Activity ──────────────────────────────────────────

export interface ActionLog {
  id: string;
  campaign_id: string | null;
  prospect_id: string | null;
  email_id: string | null;
  action: string;
  detail: string | null;
  created_at: string;
}

// ─── Stats ──────────────────────────────────────────

export interface Stats {
  sent_today: number;
  limit_today: number;
  total_sent: number;
  total_replied: number;
  total_bounced: number;
  reply_rate: number;
  bounce_rate: number;
  pending_approval: number;
  active_campaigns: number;
}

export interface DnsCheckResult {
  ok: boolean;
  domain: string;
  spf: { ok: boolean; record: string; warning?: string };
  dmarc: { ok: boolean; record: string; warning?: string };
  warnings: string[];
  advice: string;
  error?: string;
}

// ─── Settings ──────────────────────────────────────────

export interface Settings {
  smtp_configured: boolean;
  imap_configured: boolean;
  smtp_user: string;
  sender_name?: string;
  hunter_configured: boolean;
  tavily_configured: boolean;
  groq_configured: boolean;
}

// ─── SSE Events ──────────────────────────────────────────

export interface PipelineEvent {
  event: string;
  prospect_id?: string;
  email_id?: string;
  campaign_id?: string;
  [key: string]: unknown;
}
