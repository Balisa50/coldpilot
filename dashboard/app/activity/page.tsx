"use client";

import { useEffect, useState, useCallback } from "react";
import { api } from "../lib/api";
import type { ActionLog, Stats } from "../lib/types";

const ACTION_ICON: Record<string, { dot: string; text: string }> = {
  email_sent: { dot: "bg-green", text: "text-green" },
  email_approved: { dot: "bg-green", text: "text-green" },
  contact_found: { dot: "bg-accent", text: "text-accent" },
  email_drafted: { dot: "bg-accent", text: "text-accent" },
  research_complete: { dot: "bg-text-muted", text: "text-text-secondary" },
  prospect_failed: { dot: "bg-red", text: "text-red" },
  send_failed: { dot: "bg-red", text: "text-red" },
  email_bounced: { dot: "bg-red", text: "text-red" },
  email_rejected: { dot: "bg-amber", text: "text-amber" },
  campaign_started: { dot: "bg-accent", text: "text-accent" },
  campaign_completed: { dot: "bg-green", text: "text-green" },
  daily_limit_reached: { dot: "bg-amber", text: "text-amber" },
};

function getStyle(action: string) {
  return ACTION_ICON[action] || { dot: "bg-text-muted", text: "text-text-secondary" };
}

function StatCard({ label, value, sub }: { label: string; value: string | number; sub?: string }) {
  return (
    <div className="bg-surface rounded-xl border border-border p-4">
      <p className="text-xs text-text-muted uppercase tracking-wider mb-1">{label}</p>
      <p className="text-2xl font-bold text-text-primary">{value}</p>
      {sub && <p className="text-xs text-text-muted mt-1">{sub}</p>}
    </div>
  );
}

export default function ActivityPage() {
  const [activity, setActivity] = useState<ActionLog[]>([]);
  const [stats, setStats] = useState<Stats | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [filter, setFilter] = useState("");

  const load = useCallback(async () => {
    setError(null);
    try {
      const [logs, s] = await Promise.all([api.listActivity(500), api.getStats()]);
      setActivity(logs);
      setStats(s);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load activity");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  const filtered = filter
    ? activity.filter(
        (a) =>
          a.action.toLowerCase().includes(filter.toLowerCase()) ||
          (a.detail?.toLowerCase().includes(filter.toLowerCase()) ?? false),
      )
    : activity;

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
          <h1 className="text-xl font-bold text-text-primary">Activity</h1>
          <p className="text-sm text-text-muted mt-1">
            {activity.length === 0 ? "No activity yet" : `${activity.length} events`}
          </p>
        </div>
        <button
          onClick={() => { setLoading(true); load(); }}
          className="text-xs text-text-secondary hover:text-accent transition-colors"
        >
          Refresh
        </button>
      </div>

      {/* Stats row */}
      {stats && (
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
          <StatCard
            label="Sent Today"
            value={stats.sent_today}
            sub={`limit: ${stats.limit_today}/day`}
          />
          <StatCard label="Total Sent" value={stats.total_sent} />
          <StatCard
            label="Reply Rate"
            value={`${(stats.reply_rate * 100).toFixed(1)}%`}
            sub={`${stats.total_replied} replies`}
          />
          <StatCard
            label="Pending Review"
            value={stats.pending_approval}
            sub={stats.pending_approval > 0 ? "check inbox" : "all clear"}
          />
        </div>
      )}

      {/* Filter */}
      {activity.length > 0 && (
        <input
          type="text"
          placeholder="Filter by action or detail..."
          value={filter}
          onChange={(e) => setFilter(e.target.value)}
          className="input max-w-sm"
        />
      )}

      {/* Feed */}
      {filtered.length === 0 ? (
        <div className="text-center py-16 text-text-muted text-sm">
          {filter ? "No matching events" : "No activity yet — start a campaign first"}
        </div>
      ) : (
        <div className="bg-surface border border-border rounded-xl divide-y divide-border">
          {filtered.map((a) => {
            const style = getStyle(a.action);
            return (
              <div key={a.id} className="flex items-start gap-4 px-5 py-3">
                <span
                  className={`w-2 h-2 rounded-full shrink-0 mt-1.5 ${style.dot}`}
                />
                <span className="text-xs text-text-muted font-mono shrink-0 mt-0.5 w-28">
                  {new Date(a.created_at).toLocaleTimeString()}
                </span>
                <div className="flex-1 min-w-0">
                  <span className={`text-sm font-medium ${style.text}`}>
                    {a.action.replace(/_/g, " ")}
                  </span>
                  {a.detail && (
                    <p className="text-xs text-text-muted mt-0.5 truncate">{a.detail}</p>
                  )}
                </div>
                <span className="text-xs text-text-muted shrink-0 hidden sm:inline">
                  {new Date(a.created_at).toLocaleDateString()}
                </span>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
