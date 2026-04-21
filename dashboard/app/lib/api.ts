// In production browser, use proxy route to avoid DNS issues
// /api/health → /api/proxy/health (Vercel serverless → Render backend)
const IS_BROWSER = typeof window !== "undefined";
const USE_PROXY = IS_BROWSER && !process.env.NEXT_PUBLIC_API_URL;
const API_BASE = process.env.NEXT_PUBLIC_API_URL || "";

async function request<T>(path: string, options?: RequestInit, retries = 2): Promise<T> {
  const url = USE_PROXY ? path.replace(/^\/api\//, "/api/proxy/") : `${API_BASE}${path}`;

  for (let attempt = 0; attempt <= retries; attempt++) {
    try {
      const res = await fetch(url, {
        headers: { "Content-Type": "application/json", ...options?.headers },
        ...options,
      });
      if (!res.ok) {
        const body = await res.text().catch(() => "");
        throw new Error(`${res.status}: ${body}`);
      }
      return res.json();
    } catch (err) {
      if (attempt < retries) {
        await new Promise((r) => setTimeout(r, 3000));
        continue;
      }
      throw err;
    }
  }
  throw new Error("Server unreachable");
}

// ─── Campaigns ──────────────────────────────────────────

import type {
  Campaign,
  CampaignCreatePayload,
  Prospect,
  Email,
  ActionLog,
  Stats,
  Settings,
  DnsCheckResult,
} from "./types";

export const api = {
  // Campaigns
  listCampaigns: () => request<Campaign[]>("/api/campaigns"),
  getCampaign: (id: string) => request<Campaign>(`/api/campaigns/${id}`),
  createCampaign: (data: CampaignCreatePayload) =>
    request<Campaign>("/api/campaigns", {
      method: "POST",
      body: JSON.stringify(data),
    }),
  updateCampaign: (id: string, data: Partial<Campaign>) =>
    request<Campaign>(`/api/campaigns/${id}`, {
      method: "PATCH",
      body: JSON.stringify(data),
    }),
  deleteCampaign: (id: string) =>
    request<{ deleted: boolean }>(`/api/campaigns/${id}`, { method: "DELETE" }),
  startCampaign: (id: string) =>
    request<{ started: boolean }>(`/api/campaigns/${id}/start`, {
      method: "POST",
    }),
  pauseCampaign: (id: string) =>
    request<{ paused: boolean }>(`/api/campaigns/${id}/pause`, {
      method: "POST",
    }),

  // Prospects
  listProspects: (campaignId: string) =>
    request<Prospect[]>(`/api/campaigns/${campaignId}/prospects`),
  createProspect: (
    campaignId: string,
    data: {
      company_name: string;
      company_domain?: string;
      contact_name?: string;
      contact_email?: string;
      contact_role?: string;
    },
  ) =>
    request<Prospect>(`/api/campaigns/${campaignId}/prospects`, {
      method: "POST",
      body: JSON.stringify(data),
    }),

  // Emails
  listEmails: (campaignId: string) =>
    request<Email[]>(`/api/emails/campaign/${campaignId}`),
  listPendingEmails: () => request<Email[]>("/api/emails/pending"),
  getEmail: (id: string) => request<Email>(`/api/emails/${id}`),
  approveEmail: (id: string) =>
    request<{ approved: boolean }>(`/api/emails/${id}/approve`, {
      method: "POST",
    }),
  rejectEmail: (id: string, feedback?: string) =>
    request<{ rejected: boolean }>(`/api/emails/${id}/reject`, {
      method: "POST",
      body: JSON.stringify({ feedback }),
    }),
  rewriteEmail: (id: string) =>
    request<Email>(`/api/emails/${id}/rewrite`, { method: "POST" }),

  // Activity
  listActivity: (limit = 100) =>
    request<ActionLog[]>(`/api/activity?limit=${limit}`),
  listCampaignActivity: (campaignId: string, limit = 100) =>
    request<ActionLog[]>(`/api/campaigns/${campaignId}/activity?limit=${limit}`),

  // Stats & Settings
  getStats: () => request<Stats>("/api/stats"),
  getSettings: () => request<Settings>("/api/settings"),
  validateSmtp: () => request<{ ok: boolean; message: string }>("/api/settings/validate-smtp", { method: "POST" }),
  validateImap: () => request<{ ok: boolean; message: string }>("/api/settings/validate-imap", { method: "POST" }),
  validateKeys: () => request<Record<string, { ok: boolean }>>("/api/settings/validate-keys", { method: "POST" }),
  checkDns: () => request<DnsCheckResult>("/api/settings/check-dns", { method: "POST" }),
  updateSettings: (data: { smtp_user?: string; smtp_pass?: string; sender_name?: string; sender_email?: string }) =>
    request<{ ok: boolean }>("/api/settings", { method: "PATCH", body: JSON.stringify(data) }),

  // CV parsing (PDF upload → extracted text)
  parseCv: async (file: File): Promise<{ text: string; char_count: number; filename: string }> => {
    const form = new FormData();
    form.append("file", file);
    const url = USE_PROXY ? "/api/proxy/campaigns/parse-cv" : `${API_BASE}/api/campaigns/parse-cv`;
    const res = await fetch(url, { method: "POST", body: form });
    if (!res.ok) {
      const body = await res.text().catch(() => "");
      throw new Error(`${res.status}: ${body}`);
    }
    return res.json();
  },

  // Health
  health: () => request<{ status: string }>("/api/health"),

  // SSE stream URL (not a fetch — used with EventSource)
  streamUrl: (campaignId: string) =>
    USE_PROXY
      ? `/api/proxy/campaigns/${campaignId}/stream`
      : `${API_BASE}/api/campaigns/${campaignId}/stream`,
};
