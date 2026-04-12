import { api } from "../lib/api";
import type { ActionLog } from "../lib/types";

export const dynamic = "force-dynamic";

export default async function ActivityPage() {
  let logs: ActionLog[] = [];
  try {
    logs = await api.listActivity(200);
  } catch {
    // offline
  }

  return (
    <>
      <h1 className="text-2xl font-bold mb-6">Activity Log</h1>

      {logs.length === 0 ? (
        <div className="bg-surface rounded-xl border border-border p-8 text-center">
          <p className="text-text-muted">No activity yet</p>
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
