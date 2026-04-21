"use client";

import { useEffect, useState, useCallback } from "react";
import { api } from "../lib/api";
import type { Email, Campaign, Prospect } from "../lib/types";

type Tab = "pending" | "approved" | "sent" | "all";

const TAB_LIST: { key: Tab; label: string }[] = [
  { key: "pending", label: "Needs Review" },
  { key: "approved", label: "Approved" },
  { key: "sent", label: "Sent" },
  { key: "all", label: "All" },
];

const STATUS_BADGE: Record<string, string> = {
  pending_approval: "bg-amber/15 text-amber",
  draft: "bg-text-muted/15 text-text-muted",
  approved: "bg-accent/15 text-accent",
  sent: "bg-green/15 text-green",
  bounced: "bg-red/15 text-red",
  failed: "bg-red/15 text-red",
};

export default function InboxPage() {
  const [campaigns, setCampaigns] = useState<Campaign[]>([]);
  const [emails, setEmails] = useState<Email[]>([]);
  const [prospects, setProspects] = useState<Record<string, Prospect>>({});
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [tab, setTab] = useState<Tab>("pending");
  const [selected, setSelected] = useState<Email | null>(null);
  const [acting, setActing] = useState<string | null>(null);

  const load = useCallback(async () => {
    try {
      setError(null);
      const camps = await api.listCampaigns();
      setCampaigns(camps);

      // Fetch all emails and prospects per campaign
      const allEmails: Email[] = [];
      const prospectMap: Record<string, Prospect> = {};

      await Promise.all(
        camps.map(async (c) => {
          try {
            const [cEmails, cProspects] = await Promise.all([
              api.listEmails(c.id),
              api.listProspects(c.id),
            ]);
            allEmails.push(...cEmails);
            cProspects.forEach((p) => {
              prospectMap[p.id] = p;
            });
          } catch {}
        })
      );

      // Sort newest first
      allEmails.sort(
        (a, b) =>
          new Date(b.created_at).getTime() - new Date(a.created_at).getTime()
      );

      setEmails(allEmails);
      setProspects(prospectMap);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load inbox");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  const filtered = emails.filter((e) => {
    if (tab === "pending") return e.status === "pending_approval";
    if (tab === "approved") return e.status === "approved";
    if (tab === "sent") return e.status === "sent";
    return true;
  });

  const handleApprove = async (id: string) => {
    setActing(id);
    try {
      await api.approveEmail(id);
      setEmails((prev) =>
        prev.map((e) => (e.id === id ? { ...e, status: "approved" } : e))
      );
      if (selected?.id === id) setSelected((s) => (s ? { ...s, status: "approved" } : null));
    } catch {
      // Non-fatal — user can retry
    } finally {
      setActing(null);
    }
  };

  const handleReject = async (id: string) => {
    setActing(id);
    try {
      await api.rejectEmail(id);
      setEmails((prev) => prev.filter((e) => e.id !== id));
      if (selected?.id === id) setSelected(null);
    } catch {
      // Non-fatal
    } finally {
      setActing(null);
    }
  };

  const handleRewrite = async (id: string) => {
    setActing(id);
    try {
      const updated = await api.rewriteEmail(id);
      setEmails((prev) => prev.map((e) => (e.id === id ? updated : e)));
      if (selected?.id === id) setSelected(updated);
    } catch {
      // Non-fatal
    } finally {
      setActing(null);
    }
  };

  const getCampaignName = (cid: string) =>
    campaigns.find((c) => c.id === cid)?.name || "Unknown";

  const getProspect = (e: Email) => prospects[e.prospect_id];

  const pendingCount = emails.filter((e) => e.status === "pending_approval").length;

  if (loading) {
    return (
      <div className="flex items-center justify-center min-h-[50vh]">
        <div className="w-8 h-8 border-2 border-border border-t-accent rounded-full animate-spin" />
      </div>
    );
  }

  if (error) {
    return (
      <div className="flex flex-col items-center justify-center min-h-[50vh] gap-4">
        <p className="text-red text-sm">{error}</p>
        <button
          onClick={() => { setLoading(true); load(); }}
          className="text-sm text-accent hover:text-accent-hover transition-colors"
        >
          Retry
        </button>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-bold text-text-primary">Inbox</h1>
          <p className="text-sm text-text-muted mt-1">
            {pendingCount > 0
              ? `${pendingCount} email${pendingCount !== 1 ? "s" : ""} waiting for review`
              : "All caught up"}
          </p>
        </div>
        <button
          onClick={() => { setLoading(true); load(); }}
          className="text-xs text-text-secondary hover:text-accent transition-colors"
        >
          Refresh
        </button>
      </div>

      {/* Tabs */}
      <div className="flex gap-1 border-b border-border">
        {TAB_LIST.map((t) => (
          <button
            key={t.key}
            onClick={() => setTab(t.key)}
            className={`px-4 py-2.5 text-sm transition-colors border-b-2 -mb-px ${
              tab === t.key
                ? "border-accent text-accent font-medium"
                : "border-transparent text-text-secondary hover:text-text-primary"
            }`}
          >
            {t.label}
            {t.key === "pending" && pendingCount > 0 && (
              <span className="ml-2 bg-amber/20 text-amber text-xs px-1.5 py-0.5 rounded-full">
                {pendingCount}
              </span>
            )}
          </button>
        ))}
      </div>

      {filtered.length === 0 ? (
        <div className="text-center py-16 text-text-muted text-sm">
          {tab === "pending"
            ? "No emails pending review"
            : tab === "approved"
            ? "No approved emails yet"
            : tab === "sent"
            ? "No sent emails yet"
            : "No emails yet — start a campaign first"}
        </div>
      ) : (
        <div className="space-y-3">
          {filtered.map((email) => {
            const prospect = getProspect(email);
            const isOpen = selected?.id === email.id;
            const busy = acting === email.id;

            return (
              <div
                key={email.id}
                className="bg-surface border border-border rounded-xl overflow-hidden"
              >
                {/* Row summary */}
                <button
                  onClick={() => setSelected(isOpen ? null : email)}
                  className="w-full text-left px-5 py-4 flex items-center gap-4 hover:bg-surface-elevated/50 transition-colors"
                >
                  {/* Status dot */}
                  <span
                    className={`shrink-0 text-xs px-2 py-0.5 rounded-full font-medium ${
                      STATUS_BADGE[email.status] || "bg-border text-text-muted"
                    }`}
                  >
                    {email.status.replace(/_/g, " ")}
                  </span>

                  {/* Prospect info */}
                  <div className="flex-1 min-w-0">
                    <p className="text-sm font-medium text-text-primary truncate">
                      {prospect?.contact_name || prospect?.company_name || "Unknown"}{" "}
                      <span className="text-text-muted font-normal">
                        — {prospect?.contact_email || "no email"}
                      </span>
                    </p>
                    <p className="text-xs text-text-secondary truncate mt-0.5">
                      {email.subject}
                    </p>
                  </div>

                  {/* Meta */}
                  <div className="shrink-0 text-right hidden sm:block">
                    <p className="text-xs text-text-muted">
                      {getCampaignName(email.campaign_id)}
                    </p>
                    <p className="text-xs text-text-muted mt-0.5">
                      {email.email_type.replace(/_/g, " ")}
                    </p>
                  </div>

                  {/* Chevron */}
                  <span className="text-text-muted text-xs shrink-0">
                    {isOpen ? "▲" : "▼"}
                  </span>
                </button>

                {/* Expanded detail */}
                {isOpen && (
                  <div className="border-t border-border px-5 py-4 space-y-4">
                    {/* Subject */}
                    <div>
                      <p className="text-xs text-text-muted mb-1">Subject</p>
                      <p className="text-sm text-text-primary">{email.subject}</p>
                    </div>

                    {/* Body */}
                    <div>
                      <p className="text-xs text-text-muted mb-1">Body</p>
                      <div
                        className="text-sm text-text-secondary bg-background rounded-lg p-4 max-h-64 overflow-y-auto leading-relaxed"
                        dangerouslySetInnerHTML={{
                          __html: email.body_html || email.body_text.replace(/\n/g, "<br/>"),
                        }}
                      />
                    </div>

                    {/* Personalisation */}
                    {email.personalisation_points && (
                      <div>
                        <p className="text-xs text-text-muted mb-1">
                          Personalisation
                        </p>
                        <p className="text-xs text-text-secondary">
                          {email.personalisation_points}
                        </p>
                      </div>
                    )}

                    {/* Actions */}
                    {email.status === "pending_approval" && (
                      <div className="flex gap-2 pt-2">
                        <button
                          disabled={busy}
                          onClick={() => handleApprove(email.id)}
                          className="bg-green hover:bg-green/80 text-white text-sm px-4 py-2 rounded-lg transition-colors disabled:opacity-50"
                        >
                          {busy ? "..." : "Approve"}
                        </button>
                        <button
                          disabled={busy}
                          onClick={() => handleRewrite(email.id)}
                          className="bg-accent hover:bg-accent-hover text-white text-sm px-4 py-2 rounded-lg transition-colors disabled:opacity-50"
                        >
                          {busy ? "..." : "Rewrite"}
                        </button>
                        <button
                          disabled={busy}
                          onClick={() => handleReject(email.id)}
                          className="bg-red/10 hover:bg-red/20 text-red text-sm px-4 py-2 rounded-lg transition-colors disabled:opacity-50"
                        >
                          {busy ? "..." : "Reject"}
                        </button>
                      </div>
                    )}

                    {email.sent_at && (
                      <p className="text-xs text-text-muted">
                        Sent {new Date(email.sent_at).toLocaleString()}
                      </p>
                    )}
                  </div>
                )}
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
