import Link from "next/link";
import { api } from "./lib/api";
import type { Stats, Campaign } from "./lib/types";

export const dynamic = "force-dynamic";

export default async function DashboardPage() {
  let stats: Stats | null = null;
  let campaigns: Campaign[] = [];

  try {
    [stats, campaigns] = await Promise.all([
      api.getStats(),
      api.listCampaigns(),
    ]);
  } catch {
    // backend offline
  }

  const active = campaigns.filter((c) => c.status === "active");

  return (
    <>
      <h1 className="text-2xl font-bold mb-6">Dashboard</h1>

      {!stats ? (
        <div className="bg-surface rounded-xl border border-border p-8 text-center">
          <p className="text-xl font-bold mb-2">Backend Offline</p>
          <p className="text-text-muted text-sm">
            The ColdPilot server isn&apos;t responding. Please wait a moment and refresh — free instances take up to 50 seconds to wake up.
          </p>
        </div>
      ) : (
        <>
          {/* Stat cards */}
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-8">
            <StatCard label="Sent Today" value={`${stats.sent_today} / ${stats.limit_today}`} />
            <StatCard label="Total Sent" value={stats.total_sent} />
            <StatCard
              label="Reply Rate"
              value={`${(stats.reply_rate * 100).toFixed(1)}%`}
              accent={stats.reply_rate > 0.05}
            />
            <StatCard
              label="Pending Approval"
              value={stats.pending_approval}
              accent={stats.pending_approval > 0}
            />
          </div>

          <div className="grid md:grid-cols-2 gap-6">
            {/* Active campaigns */}
            <section className="bg-surface rounded-xl border border-border p-5">
              <div className="flex items-center justify-between mb-4">
                <h2 className="font-semibold">Active Campaigns</h2>
                <Link
                  href="/campaigns/new"
                  className="text-xs bg-accent hover:bg-accent-hover text-white px-3 py-1.5 rounded-lg transition-colors"
                >
                  + New
                </Link>
              </div>
              {active.length === 0 ? (
                <p className="text-sm text-text-muted">No active campaigns</p>
              ) : (
                <ul className="space-y-2">
                  {active.map((c) => (
                    <li key={c.id}>
                      <Link
                        href={`/campaigns/${c.id}`}
                        className="flex items-center justify-between p-3 rounded-lg hover:bg-surface-elevated transition-colors"
                      >
                        <div>
                          <p className="text-sm font-medium">{c.name}</p>
                          <p className="text-xs text-text-muted capitalize">{c.mode} &middot; {c.autonomy}</p>
                        </div>
                        <div className="text-right text-xs text-text-secondary">
                          <p>{c.prospect_count ?? 0} prospects</p>
                          <p>{c.sent_count ?? 0} sent</p>
                        </div>
                      </Link>
                    </li>
                  ))}
                </ul>
              )}
            </section>

            {/* Quick stats */}
            <section className="bg-surface rounded-xl border border-border p-5">
              <h2 className="font-semibold mb-4">Overview</h2>
              <dl className="space-y-3 text-sm">
                <Row label="Active Campaigns" value={stats.active_campaigns} />
                <Row label="Total Sent" value={stats.total_sent} />
                <Row label="Total Replied" value={stats.total_replied} />
                <Row label="Total Bounced" value={stats.total_bounced} />
                <Row
                  label="Bounce Rate"
                  value={`${(stats.bounce_rate * 100).toFixed(1)}%`}
                />
              </dl>
            </section>
          </div>
        </>
      )}
    </>
  );
}

function StatCard({
  label,
  value,
  accent,
}: {
  label: string;
  value: string | number;
  accent?: boolean;
}) {
  return (
    <div className="bg-surface rounded-xl border border-border p-4">
      <p className="text-xs text-text-muted mb-1">{label}</p>
      <p className={`text-xl font-bold ${accent ? "text-accent" : ""}`}>
        {value}
      </p>
    </div>
  );
}

function Row({ label, value }: { label: string; value: string | number }) {
  return (
    <div className="flex justify-between">
      <dt className="text-text-secondary">{label}</dt>
      <dd className="font-medium">{value}</dd>
    </div>
  );
}
