"use client";

import { useEffect, useState, useCallback } from "react";
import { useParams, useRouter } from "next/navigation";
import Link from "next/link";
import { api } from "../../lib/api";
import type { Campaign, Prospect, Email, ActionLog } from "../../lib/types";

type DetailTab = "prospects" | "emails" | "activity";

const PROSPECT_STATUS_BADGE: Record<string, string> = {
  pending:           "bg-text-muted/15 text-text-muted",
  researching:       "bg-accent/15 text-accent",
  contact_found:     "bg-amber/15 text-amber",
  email_drafted:     "bg-accent/15 text-accent",
  email_approved:    "bg-accent/15 text-accent",
  email_sent:        "bg-green/15 text-green",
  replied:           "bg-green/15 text-green",
  bounced:           "bg-red/15 text-red",
  opted_out:         "bg-red/15 text-red",
  failed:            "bg-red/15 text-red",
};

const EMAIL_STATUS_BADGE: Record<string, string> = {
  draft:            "bg-text-muted/15 text-text-muted",
  pending_approval: "bg-amber/15 text-amber",
  approved:         "bg-accent/15 text-accent",
  sent:             "bg-green/15 text-green",
  bounced:          "bg-red/15 text-red",
  failed:           "bg-red/15 text-red",
};

// Action log colours
const ACTION_STYLE: Record<string, { dot: string; text: string }> = {
  email_sent:              { dot: "bg-green",      text: "text-green" },
  email_approved:          { dot: "bg-green",      text: "text-green" },
  reply_detected:          { dot: "bg-green",      text: "text-green" },
  campaign_completed:      { dot: "bg-green",      text: "text-green" },
  contact_found:           { dot: "bg-accent",     text: "text-accent" },
  email_drafted:           { dot: "bg-accent",     text: "text-accent" },
  email_pending_approval:  { dot: "bg-accent",     text: "text-accent" },
  campaign_started:        { dot: "bg-accent",     text: "text-accent" },
  research_complete:       { dot: "bg-text-muted", text: "text-text-secondary" },
  contact_provided:        { dot: "bg-text-muted", text: "text-text-secondary" },
  contact_not_found:       { dot: "bg-amber",      text: "text-amber" },
  contact_skipped:         { dot: "bg-amber",      text: "text-amber" },
  daily_limit_reached:     { dot: "bg-amber",      text: "text-amber" },
  campaign_auto_paused:    { dot: "bg-amber",      text: "text-amber" },
  send_failed:             { dot: "bg-red",        text: "text-red" },
  bounce_detected:         { dot: "bg-red",        text: "text-red" },
  pipeline_error:          { dot: "bg-red",        text: "text-red" },
};

function getActionStyle(action: string) {
  return ACTION_STYLE[action] ?? { dot: "bg-text-muted", text: "text-text-secondary" };
}

/** Convert a JSON-encoded action log detail string to a readable one-liner. */
function formatDetail(raw: string | null): string {
  if (!raw) return "";
  try {
    const obj = JSON.parse(raw);
    if (typeof obj !== "object" || obj === null) return raw;
    return Object.entries(obj)
      .map(([k, v]) => `${k}: ${String(v).slice(0, 60)}`)
      .join("  ·  ");
  } catch {
    return raw;
  }
}

/** Safely extract a readable summary from research_notes (may be JSON string or plain text). */
function parseResearchSummary(raw: unknown): string {
  if (!raw) return "";
  if (typeof raw === "string") {
    try {
      const parsed = JSON.parse(raw);
      return parsed?.summary ?? raw;
    } catch {
      return raw;
    }
  }
  if (typeof raw === "object" && raw !== null) {
    return (raw as Record<string, string>).summary ?? JSON.stringify(raw);
  }
  return String(raw);
}

export default function CampaignDetailPage() {
  const { id } = useParams<{ id: string }>();
  const router = useRouter();

  const [campaign, setCampaign] = useState<Campaign | null>(null);
  const [prospects, setProspects] = useState<Prospect[]>([]);
  const [emails, setEmails] = useState<Email[]>([]);
  const [activity, setActivity] = useState<ActionLog[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [tab, setTab] = useState<DetailTab>("prospects");
  const [expandedEmail, setExpandedEmail] = useState<string | null>(null);
  const [acting, setActing] = useState<string | null>(null);

  const load = useCallback(async () => {
    if (!id) return;
    setError(null);
    try {
      const [c, p, e, a] = await Promise.all([
        api.getCampaign(id),
        api.listProspects(id),
        api.listEmails(id),
        api.listCampaignActivity(id, 200),
      ]);
      setCampaign(c);
      setProspects(p);
      setEmails(
        e.sort(
          (x, y) => new Date(y.created_at).getTime() - new Date(x.created_at).getTime(),
        ),
      );
      setActivity(a);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load campaign");
    } finally {
      setLoading(false);
    }
  }, [id]);

  useEffect(() => {
    load();
  }, [load]);

  const handleApprove = async (emailId: string) => {
    setActing(emailId);
    try {
      await api.approveEmail(emailId);
      setEmails((prev) =>
        prev.map((e) => (e.id === emailId ? { ...e, status: "approved" } : e)),
      );
    } catch {}
    setActing(null);
  };

  const handleReject = async (emailId: string) => {
    setActing(emailId);
    try {
      await api.rejectEmail(emailId);
      setEmails((prev) => prev.filter((e) => e.id !== emailId));
    } catch {}
    setActing(null);
  };

  const handleRewrite = async (emailId: string) => {
    setActing(emailId);
    try {
      const updated = await api.rewriteEmail(emailId);
      setEmails((prev) => prev.map((e) => (e.id === emailId ? updated : e)));
    } catch {}
    setActing(null);
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center min-h-[50vh]">
        <div className="w-8 h-8 border-2 border-border border-t-accent rounded-full animate-spin" />
      </div>
    );
  }

  if (error || !campaign) {
    return (
      <div className="flex flex-col items-center justify-center min-h-[50vh] gap-4">
        <p className="text-red text-sm">{error || "Campaign not found"}</p>
        <button
          onClick={() => router.push("/campaigns")}
          className="text-sm text-accent hover:text-accent-hover transition-colors"
        >
          Back to Campaigns
        </button>
      </div>
    );
  }

  const pendingCount = emails.filter((e) => e.status === "pending_approval").length;
  const sentCount = emails.filter((e) => e.status === "sent").length;
  const openedCount = emails.filter((e) => e.opened_at).length;
  const repliedCount = prospects.filter((p) => p.status === "replied").length;

  return (
    <div className="space-y-6">
      {/* Back + header */}
      <div className="flex items-start gap-4">
        <Link
          href="/campaigns"
          className="text-text-muted hover:text-text-primary text-sm transition-colors mt-1"
        >
          ← Campaigns
        </Link>
        <div className="flex-1">
          <div className="flex items-center gap-3 flex-wrap">
            <h1 className="text-xl font-bold text-text-primary">{campaign.name}</h1>
            <span
              className={`text-xs px-2 py-0.5 rounded-full font-medium capitalize ${
                campaign.status === "active"
                  ? "bg-green/15 text-green"
                  : campaign.status === "paused"
                  ? "bg-amber/15 text-amber"
                  : campaign.status === "completed"
                  ? "bg-border text-text-secondary"
                  : "bg-text-muted/15 text-text-muted"
              }`}
            >
              {campaign.status}
            </span>
            <span
              className={`text-xs px-2 py-0.5 rounded-full font-medium capitalize ${
                campaign.mode === "hunter"
                  ? "bg-accent/15 text-accent"
                  : "bg-amber/15 text-amber"
              }`}
            >
              {campaign.mode}
            </span>
            {!!campaign.dry_run && (
              <span className="text-xs px-2 py-0.5 rounded-full font-medium bg-border text-text-muted">
                dry run
              </span>
            )}
          </div>

          {/* Quick-stats strip */}
          <div className="flex flex-wrap gap-4 mt-3">
            {[
              { label: "Prospects", value: prospects.length },
              { label: "Sent", value: sentCount },
              { label: "Opened", value: openedCount },
              { label: "Replied", value: repliedCount },
            ].map((s) => (
              <div key={s.label} className="text-center">
                <p className="text-lg font-bold text-text-primary leading-tight">{s.value}</p>
                <p className="text-xs text-text-muted">{s.label}</p>
              </div>
            ))}
          </div>
        </div>

        <div className="shrink-0">
          <button
            onClick={() => { setLoading(true); load(); }}
            className="text-xs text-text-secondary hover:text-accent transition-colors"
          >
            Refresh
          </button>
        </div>
      </div>

      {/* Tabs */}
      <div className="flex gap-1 border-b border-border">
        {(
          [
            { key: "prospects" as const, label: `Prospects (${prospects.length})` },
            {
              key: "emails" as const,
              label: `Emails (${emails.length})`,
              badge: pendingCount > 0 ? pendingCount : undefined,
            },
            { key: "activity" as const, label: `Activity (${activity.length})` },
          ] as const
        ).map((t) => (
          <button
            key={t.key}
            onClick={() => setTab(t.key)}
            className={`px-4 py-2.5 text-sm transition-colors border-b-2 -mb-px flex items-center gap-2 ${
              tab === t.key
                ? "border-accent text-accent font-medium"
                : "border-transparent text-text-secondary hover:text-text-primary"
            }`}
          >
            {t.label}
            {(t as { badge?: number }).badge !== undefined && (
              <span className="bg-amber/20 text-amber text-xs px-1.5 py-0.5 rounded-full">
                {(t as { badge?: number }).badge}
              </span>
            )}
          </button>
        ))}
      </div>

      {/* ── Prospects Tab ─────────────────────────────────── */}
      {tab === "prospects" && (
        <div className="space-y-2">
          {prospects.length === 0 ? (
            <div className="text-center py-16 text-text-muted text-sm">No prospects yet</div>
          ) : (
            prospects.map((p) => {
              const summary = parseResearchSummary(p.research_notes);
              return (
                <div
                  key={p.id}
                  className="bg-surface border border-border rounded-xl px-5 py-4 flex items-start gap-4"
                >
                  <span
                    className={`shrink-0 text-xs px-2 py-0.5 rounded-full font-medium capitalize mt-0.5 ${
                      PROSPECT_STATUS_BADGE[p.status] || "bg-border text-text-muted"
                    }`}
                  >
                    {p.status.replace(/_/g, " ")}
                  </span>
                  <div className="flex-1 min-w-0">
                    <p className="text-sm font-medium text-text-primary">
                      {p.company_name}
                      {p.contact_name && (
                        <span className="text-text-muted font-normal"> — {p.contact_name}</span>
                      )}
                    </p>
                    {(p.contact_email || p.contact_role) && (
                      <p className="text-xs text-text-muted mt-0.5">
                        {[p.contact_role, p.contact_email].filter(Boolean).join(" · ")}
                      </p>
                    )}
                    {summary && (
                      <p className="text-xs text-text-secondary mt-1 line-clamp-2">{summary}</p>
                    )}
                  </div>
                  <div className="shrink-0 text-right">
                    <p className="text-xs text-text-muted">
                      {new Date(p.updated_at).toLocaleDateString()}
                    </p>
                  </div>
                </div>
              );
            })
          )}
        </div>
      )}

      {/* ── Emails Tab ─────────────────────────────────── */}
      {tab === "emails" && (
        <div className="space-y-3">
          {emails.length === 0 ? (
            <div className="text-center py-16 text-text-muted text-sm">No emails yet</div>
          ) : (
            emails.map((e) => {
              const prospect = prospects.find((p) => p.id === e.prospect_id);
              const isOpen = expandedEmail === e.id;
              const busy = acting === e.id;

              return (
                <div
                  key={e.id}
                  className="bg-surface border border-border rounded-xl overflow-hidden"
                >
                  <button
                    onClick={() => setExpandedEmail(isOpen ? null : e.id)}
                    className="w-full text-left px-5 py-4 flex items-center gap-4 hover:bg-surface-elevated/50 transition-colors"
                  >
                    <span
                      className={`shrink-0 text-xs px-2 py-0.5 rounded-full font-medium ${
                        EMAIL_STATUS_BADGE[e.status] || "bg-border text-text-muted"
                      }`}
                    >
                      {e.status.replace(/_/g, " ")}
                    </span>
                    <div className="flex-1 min-w-0">
                      <p className="text-sm font-medium text-text-primary truncate">
                        {prospect?.contact_name || prospect?.company_name || "Unknown"}{" "}
                        <span className="text-text-muted font-normal">
                          — {prospect?.contact_email || "no email"}
                        </span>
                      </p>
                      <p className="text-xs text-text-secondary truncate mt-0.5">{e.subject}</p>
                    </div>

                    {/* Open / click tracking badges */}
                    <div className="shrink-0 flex items-center gap-1.5 hidden sm:flex">
                      {e.opened_at && (
                        <span className="text-xs bg-green/10 text-green px-1.5 py-0.5 rounded">
                          opened
                        </span>
                      )}
                      {e.clicked_at && (
                        <span className="text-xs bg-accent/10 text-accent px-1.5 py-0.5 rounded">
                          clicked
                        </span>
                      )}
                    </div>

                    <div className="shrink-0 text-right hidden sm:block">
                      <p className="text-xs text-text-muted">{e.email_type.replace(/_/g, " ")}</p>
                      <p className="text-xs text-text-muted mt-0.5">
                        {new Date(e.created_at).toLocaleDateString()}
                      </p>
                    </div>
                    <span className="text-text-muted text-xs shrink-0">{isOpen ? "▲" : "▼"}</span>
                  </button>

                  {isOpen && (
                    <div className="border-t border-border px-5 py-4 space-y-4">
                      <div>
                        <p className="text-xs text-text-muted mb-1">Subject</p>
                        <p className="text-sm text-text-primary">{e.subject}</p>
                      </div>
                      <div>
                        <p className="text-xs text-text-muted mb-1">Body</p>
                        <div
                          className="text-sm text-text-secondary bg-background rounded-lg p-4 max-h-64 overflow-y-auto leading-relaxed"
                          dangerouslySetInnerHTML={{
                            __html: e.body_html || e.body_text.replace(/\n/g, "<br/>"),
                          }}
                        />
                      </div>
                      {e.personalisation_points && (
                        <div>
                          <p className="text-xs text-text-muted mb-1">Personalisation</p>
                          <p className="text-xs text-text-secondary">{e.personalisation_points}</p>
                        </div>
                      )}
                      {e.status === "pending_approval" && (
                        <div className="flex gap-2 pt-2">
                          <button
                            disabled={busy}
                            onClick={() => handleApprove(e.id)}
                            className="bg-green hover:bg-green/80 disabled:opacity-50 text-white text-sm px-4 py-2 rounded-lg transition-colors"
                          >
                            {busy ? "..." : "Approve"}
                          </button>
                          <button
                            disabled={busy}
                            onClick={() => handleRewrite(e.id)}
                            className="bg-accent hover:bg-accent-hover disabled:opacity-50 text-white text-sm px-4 py-2 rounded-lg transition-colors"
                          >
                            {busy ? "..." : "Rewrite"}
                          </button>
                          <button
                            disabled={busy}
                            onClick={() => handleReject(e.id)}
                            className="bg-red/10 hover:bg-red/20 disabled:opacity-50 text-red text-sm px-4 py-2 rounded-lg transition-colors"
                          >
                            {busy ? "..." : "Reject"}
                          </button>
                        </div>
                      )}
                      {e.sent_at && (
                        <p className="text-xs text-text-muted">
                          Sent {new Date(e.sent_at).toLocaleString()}
                          {e.opened_at && (
                            <> · Opened {new Date(e.opened_at).toLocaleString()}</>
                          )}
                          {e.clicked_at && (
                            <> · Clicked {new Date(e.clicked_at).toLocaleString()}</>
                          )}
                        </p>
                      )}
                    </div>
                  )}
                </div>
              );
            })
          )}
        </div>
      )}

      {/* ── Activity Tab ─────────────────────────────────── */}
      {tab === "activity" && (
        <div className="space-y-1">
          {activity.length === 0 ? (
            <div className="text-center py-16 text-text-muted text-sm">No activity yet</div>
          ) : (
            activity.map((a) => {
              const style = getActionStyle(a.action);
              const timeLabel = new Date(a.created_at).toLocaleTimeString(undefined, {
                hour: "2-digit",
                minute: "2-digit",
                second: "2-digit",
              });
              return (
                <div
                  key={a.id}
                  className="flex items-start gap-3 py-2 px-3 rounded-lg hover:bg-surface-elevated/40 transition-colors"
                >
                  <span className={`w-2 h-2 rounded-full shrink-0 mt-1.5 ${style.dot}`} />
                  <span className="text-xs text-text-muted font-mono shrink-0 mt-0.5 w-24">
                    {timeLabel}
                  </span>
                  <span className={`text-sm flex-1 min-w-0 ${style.text}`}>
                    {a.action.replace(/_/g, " ")}
                  </span>
                  {a.detail && (
                    <span className="text-xs text-text-muted truncate max-w-xs">{formatDetail(a.detail)}</span>
                  )}
                </div>
              );
            })
          )}
        </div>
      )}
    </div>
  );
}
