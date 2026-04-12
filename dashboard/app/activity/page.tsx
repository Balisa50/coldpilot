"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { api } from "../lib/api";
import type { ActionLog } from "../lib/types";

export default function ActivityPage() {
  const [logs, setLogs] = useState<ActionLog[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    api
      .listActivity(200)
      .then(setLogs)
      .catch(() => {})
      .finally(() => setLoading(false));
  }, []);

  if (loading) {
    return (
      <div className="flex items-center justify-center min-h-[40vh]">
        <div className="w-8 h-8 border-3 border-border border-t-accent rounded-full animate-spin" />
      </div>
    );
  }

  return (
    <>
      <h1 className="text-2xl font-bold mb-6">Activity Log</h1>

      {logs.length === 0 ? (
        <div className="bg-surface rounded-xl border border-border p-10 text-center">
          <div className="w-14 h-14 rounded-full bg-accent/10 flex items-center justify-center mx-auto mb-4">
            <svg className="w-7 h-7 text-accent" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z" />
            </svg>
          </div>
          <p className="font-medium mb-2">No activity yet</p>
          <p className="text-sm text-text-muted mb-5 max-w-sm mx-auto">
            Every action the agent takes will be logged here in real time once a campaign is running — emails sent, prospects found, replies received.
          </p>
          <Link
            href="/campaigns/new"
            className="inline-flex bg-accent hover:bg-accent-hover text-white text-sm px-5 py-2.5 rounded-lg transition-colors"
          >
            Create a Campaign
          </Link>
        </div>
      ) : (
        <div className="bg-surface rounded-xl border border-border divide-y divide-border">
          {logs.map((log) => (
            <div key={log.id} className="px-4 py-3 flex items-start gap-3">
              <ActionIcon action={log.action} />
              <div className="flex-1 min-w-0">
                <p className="text-sm">
                  <span className="font-medium">{formatAction(log.action)}</span>
                  {log.detail && (
                    <span className="text-text-secondary ml-1.5">
                      {log.detail}
                    </span>
                  )}
                </p>
                <p className="text-xs text-text-muted mt-0.5">
                  {new Date(log.created_at).toLocaleString()}
                </p>
              </div>
            </div>
          ))}
        </div>
      )}
    </>
  );
}

function formatAction(action: string): string {
  return action
    .replace(/_/g, " ")
    .replace(/\b\w/g, (c) => c.toUpperCase());
}

const ACTION_COLORS: Record<string, string> = {
  email_sent: "text-green",
  email_approved: "text-green",
  email_bounced: "text-red",
  email_failed: "text-red",
  prospect_failed: "text-red",
  campaign_started: "text-accent",
  campaign_paused: "text-amber",
};

function ActionIcon({ action }: { action: string }) {
  const color = ACTION_COLORS[action] ?? "text-text-muted";
  return (
    <div
      className={`w-2 h-2 rounded-full mt-1.5 shrink-0 ${color}`}
      style={{ backgroundColor: "currentColor" }}
    />
  );
}
