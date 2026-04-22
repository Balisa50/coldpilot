"use client";

import { useEffect, useState, useCallback } from "react";
import { api } from "../lib/api";
import type { Email, Campaign, Prospect } from "../lib/types";

type Tab = "pending" | "approved" | "sent" | "all";

const TAB_LIST: { key: Tab; label: string }[] = [
  { key: "pending",  label: "Needs Review" },
  { key: "approved", label: "Approved" },
  { key: "sent",     label: "Sent" },
  { key: "all",      label: "All" },
];

const STATUS_BADGE: Record<string, string> = {
  pending_approval: "bg-amber/15 text-amber",
  draft:            "bg-text-muted/15 text-text-muted",
  approved:         "bg-accent/15 text-accent",
  sent:             "bg-green/15 text-green",
  bounced:          "bg-red/15 text-red",
  failed:           "bg-red/15 text-red",
};

const DISMISSED_KEY = "coldpilot:inbox:dismissed";

function loadDismissed(): Set<string> {
  try {
    const raw = localStorage.getItem(DISMISSED_KEY);
    return new Set(raw ? JSON.parse(raw) : []);
  } catch { return new Set(); }
}

function saveDismissed(ids: Set<string>) {
  try {
    // Cap at 500 to avoid bloating localStorage
    const arr = [...ids].slice(-500);
    localStorage.setItem(DISMISSED_KEY, JSON.stringify(arr));
  } catch {}
}

export default function InboxPage() {
  const [campaigns, setCampaigns]   = useState<Campaign[]>([]);
  const [emails, setEmails]         = useState<Email[]>([]);
  const [prospects, setProspects]   = useState<Record<string, Prospect>>({});
  const [loading, setLoading]       = useState(true);
  const [error, setError]           = useState<string | null>(null);
  const [tab, setTab]               = useState<Tab>("pending");
  const [selected, setSelected]     = useState<Email | null>(null);
  const [acting, setActing]         = useState<string | null>(null);
  const [dismissed, setDismissed]   = useState<Set<string>>(new Set());

  // Load dismissed list from localStorage on mount
  useEffect(() => { setDismissed(loadDismissed()); }, []);

  const dismiss = useCallback((id: string) => {
    setDismissed((prev) => {
      const next = new Set(prev);
      next.add(id);
      saveDismissed(next);
      return next;
    });
    setSelected((s) => (s?.id === id ? null : s));
  }, []);

  const clearTab = useCallback((visibleIds: string[]) => {
    setDismissed((prev) => {
      const next = new Set(prev);
      visibleIds.forEach((id) => next.add(id));
      saveDismissed(next);
      return next;
    });
    setSelected(null);
  }, []);

  const load = useCallback(async () => {
    try {
      setError(null);
      const camps = await api.listCampaigns();
      setCampaigns(camps);

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
            cProspects.forEach((p) => { prospectMap[p.id] = p; });
          } catch {}
        })
      );

      allEmails.sort(
        (a, b) => new Date(b.created_at).getTime() - new Date(a.created_at).getTime()
      );

      setEmails(allEmails);
      setProspects(prospectMap);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load inbox");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { load(); }, [load]);

  // Pending emails are never dismissable — they need a decision (Approve/Reject)
  const canDismiss = (e: Email) => e.status !== "pending_approval";

  const filtered = emails.filter((e) => {
    if (dismissed.has(e.id) && canDismiss(e)) return false;
    if (tab === "pending")  return e.status === "pending_approval";
    if (tab === "approved") return e.status === "approved";
    if (tab === "sent")     return e.status === "sent";
    return true;
  });

  // IDs that can be cleared in the current tab view
  const clearableIds = filtered.filter(canDismiss).map((e) => e.id);

  const handleApprove = async (id: string) => {
    setActing(id);
    try {
      await api.approveEmail(id);
      setEmails((prev) => prev.map((e) => (e.id === id ? { ...e, status: "approved" } : e)));
      if (selected?.id === id) setSelected((s) => (s ? { ...s, status: "approved" } : null));
    } catch {} finally { setActing(null); }
  };

  const handleReject = async (id: string) => {
    setActing(id);
    try {
      await api.rejectEmail(id);
      setEmails((prev) => prev.filter((e) => e.id !== id));
      if (selected?.id === id) setSelected(null);
    } catch {} finally { setActing(null); }
  };

  const handleRewrite = async (id: string) => {
    setActing(id);
    try {
      const updated = await api.rewriteEmail(id);
      setEmails((prev) => prev.map((e) => (e.id === id ? updated : e)));
      if (selected?.id === id) setSelected(updated);
    } catch {} finally { setActing(null); }
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
        <button onClick={() => { setLoading(true); load(); }}
          className="text-sm text-accent hover:text-accent-hover transition-colors">
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

      {/* Tabs + Clear all */}
      <div className="flex items-end justify-between border-b border-border">
        <div className="flex gap-1">
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

        {/* Clear all — only shown when there are dismissable items in this tab */}
        {clearableIds.length > 0 && (
          <button
            onClick={() => clearTab(clearableIds)}
            className="text-xs text-text-muted hover:text-red transition-colors pb-2.5 pr-1"
          >
            Clear all
          </button>
        )}
      </div>

      {filtered.length === 0 ? (
        <div className="text-center py-16 text-text-muted text-sm">
          {tab === "pending"
            ? "No emails pending review"
            : tab === "approved"
            ? "No approved emails"
            : tab === "sent"
            ? "No sent emails"
            : "No emails yet — start a campaign first"}
        </div>
      ) : (
        <div className="space-y-3">
          {filtered.map((email) => {
            const prospect = getProspect(email);
            const isOpen   = selected?.id === email.id;
            const busy     = acting === email.id;

            return (
              <div
                key={email.id}
                className="bg-surface border border-border rounded-xl overflow-hidden"
              >
                {/* Row summary */}
                <div className="flex items-center gap-2 pr-3">
                  <button
                    onClick={() => setSelected(isOpen ? null : email)}
                    className="flex-1 text-left px-5 py-4 flex items-center gap-4 hover:bg-surface-elevated/50 transition-colors min-w-0"
                  >
                    {/* Status badge */}
                    <span className={`shrink-0 text-xs px-2 py-0.5 rounded-full font-medium ${
                      STATUS_BADGE[email.status] || "bg-border text-text-muted"
                    }`}>
                      {email.status === "pending_approval" ? "Review" : email.status}
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

                    {/* Campaign name */}
                    <div className="shrink-0 text-right hidden sm:block">
                      <p className="text-xs text-text-muted">{getCampaignName(email.campaign_id)}</p>
                      <p className="text-xs text-text-muted mt-0.5">
                        {email.email_type.replace(/_/g, " ")}
                      </p>
                    </div>

                    <span className="text-text-muted text-xs shrink-0">{isOpen ? "▲" : "▼"}</span>
                  </button>

                  {/* Dismiss X — shown on non-pending emails */}
                  {canDismiss(email) && (
                    <button
                      onClick={() => dismiss(email.id)}
                      className="shrink-0 text-text-muted hover:text-red transition-colors p-1.5 rounded"
                      title="Remove from inbox"
                    >
                      <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                        <path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" />
                      </svg>
                    </button>
                  )}
                </div>

                {/* Expanded detail */}
                {isOpen && (
                  <div className="border-t border-border px-5 py-4 space-y-4">
                    <div>
                      <p className="text-xs text-text-muted mb-1">Subject</p>
                      <p className="text-sm text-text-primary">{email.subject}</p>
                    </div>

                    <div>
                      <p className="text-xs text-text-muted mb-1">Body</p>
                      <div
                        className="text-sm text-text-secondary bg-background rounded-lg p-4 max-h-64 overflow-y-auto leading-relaxed"
                        dangerouslySetInnerHTML={{
                          __html: email.body_html || email.body_text.replace(/\n/g, "<br/>"),
                        }}
                      />
                    </div>

                    {email.personalisation_points && (
                      <div>
                        <p className="text-xs text-text-muted mb-1">Personalisation</p>
                        <p className="text-xs text-text-secondary">{email.personalisation_points}</p>
                      </div>
                    )}

                    {/* Actions — pending only */}
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
