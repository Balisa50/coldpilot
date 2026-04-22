"use client";

import { useEffect, useState, useCallback } from "react";
import Link from "next/link";
import { api } from "../lib/api";
import type { Campaign, Stats } from "../lib/types";

const MODE_BADGE: Record<string, string> = {
  hunter: "bg-accent/15 text-accent",
  seeker: "bg-amber/15 text-amber",
};

const STATUS_BADGE: Record<string, string> = {
  draft: "bg-text-muted/15 text-text-muted",
  active: "bg-green/15 text-green",
  paused: "bg-amber/15 text-amber",
  completed: "bg-border text-text-secondary",
};

export default function CampaignsPage() {
  const [campaigns, setCampaigns] = useState<Campaign[]>([]);
  const [stats, setStats] = useState<Stats | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [deleting, setDeleting] = useState<string | null>(null);

  const load = useCallback(async () => {
    setError(null);
    try {
      const [camps, s] = await Promise.all([api.listCampaigns(), api.getStats()]);
      // Sort newest first
      camps.sort(
        (a, b) => new Date(b.created_at).getTime() - new Date(a.created_at).getTime(),
      );
      setCampaigns(camps);
      setStats(s);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load campaigns");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  async function handleDelete(id: string) {
    setDeleting(id);
    try {
      await api.deleteCampaign(id);
      setCampaigns((prev) => prev.filter((c) => c.id !== id));
    } catch {
      // ignore
    } finally {
      setDeleting(null);
    }
  }

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
        <p className="text-sm text-text-muted">
          {campaigns.length === 0
            ? "No campaigns yet"
            : `${campaigns.length} campaign${campaigns.length !== 1 ? "s" : ""}`}
        </p>
        <button
          onClick={() => { setLoading(true); load(); }}
          className="text-xs text-text-secondary hover:text-accent transition-colors"
        >
          Refresh
        </button>
      </div>

      {/* Subtle stats line */}
      {stats && stats.total_sent > 0 && (
        <p className="text-xs text-text-muted">
          {stats.sent_today} of {stats.limit_today} sent today
          {stats.total_sent > 0 && <> · {stats.total_sent} total</>}
          {stats.total_replied > 0 && <> · {stats.reply_rate.toFixed(1)}% replied</>}
          {stats.pending_approval > 0 && (
            <span className="text-accent"> · {stats.pending_approval} waiting in inbox</span>
          )}
        </p>
      )}

      {/* Campaign list */}
      {campaigns.length === 0 ? (
        <div className="text-center py-20">
          <Link
            href="/"
            className="bg-accent hover:bg-accent-hover text-white text-sm px-5 py-2.5 rounded-lg transition-colors"
          >
            Launch your first campaign
          </Link>
        </div>
      ) : (
        <div className="space-y-3">
          {campaigns.map((c) => (
            <div
              key={c.id}
              className="bg-surface border border-border rounded-xl hover:border-text-muted/40 transition-colors"
            >
              <div className="px-5 py-4 flex items-center gap-4">
                {/* Badges */}
                <div className="flex flex-col gap-1.5 shrink-0">
                  <span
                    className={`text-xs px-2 py-0.5 rounded-full font-medium capitalize ${MODE_BADGE[c.mode] || "bg-border text-text-muted"}`}
                  >
                    {c.mode}
                  </span>
                  <span
                    className={`text-xs px-2 py-0.5 rounded-full font-medium capitalize ${STATUS_BADGE[c.status] || "bg-border text-text-muted"}`}
                  >
                    {c.status}
                  </span>
                </div>

                {/* Name + meta */}
                <div className="flex-1 min-w-0">
                  <p className="text-sm font-semibold text-text-primary truncate">{c.name}</p>
                  <p className="text-xs text-text-muted mt-0.5">
                    {c.prospect_count ?? 0} prospect{c.prospect_count !== 1 ? "s" : ""} ·{" "}
                    {c.sent_count ?? 0} sent ·{" "}
                    {c.replied_count ?? 0} replied
                    {(c.bounce_count ?? 0) > 0 && (
                      <span className="text-red"> · {c.bounce_count} bounced</span>
                    )}
                    {c.dry_run ? " · dry run" : ""}
                  </p>
                  <p className="text-xs text-text-muted mt-0.5">
                    {new Date(c.created_at).toLocaleDateString(undefined, {
                      month: "short",
                      day: "numeric",
                      year: "numeric",
                    })}
                  </p>
                </div>

                {/* Actions */}
                <div className="flex items-center gap-2 shrink-0">
                  <Link
                    href={`/campaigns/${c.id}`}
                    className="text-xs text-accent hover:text-accent-hover transition-colors px-3 py-1.5 rounded-lg border border-accent/30 hover:border-accent/60"
                  >
                    View
                  </Link>
                  <button
                    onClick={() => handleDelete(c.id)}
                    disabled={deleting === c.id}
                    className="text-xs text-text-muted hover:text-red transition-colors px-3 py-1.5 rounded-lg border border-border hover:border-red/30 disabled:opacity-40"
                  >
                    {deleting === c.id ? "..." : "Delete"}
                  </button>
                </div>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
