"use client";

import { useEffect, useState, useCallback } from "react";
import Link from "next/link";
import { api } from "./lib/api";
import type { Stats, Campaign } from "./lib/types";
import WakeUp from "./components/WakeUp";

export default function DashboardPage() {
  const [stats, setStats] = useState<Stats | null>(null);
  const [campaigns, setCampaigns] = useState<Campaign[]>([]);
  const [ready, setReady] = useState(false);
  const [loaded, setLoaded] = useState(false);

  const loadData = useCallback(async () => {
    try {
      const [s, c] = await Promise.all([api.getStats(), api.listCampaigns()]);
      setStats(s);
      setCampaigns(c);
      setReady(true);
      setLoaded(true);
    } catch {
      setReady(false);
    }
  }, []);

  useEffect(() => { loadData(); }, [loadData]);

  const handleReady = useCallback(() => {
    setReady(true);
    loadData();
  }, [loadData]);

  if (!ready && !loaded) {
    return <WakeUp brandName="ColdPilot" accentPart="Pilot" onReady={handleReady} />;
  }

  const active = campaigns.filter((c) => c.status === "active");
  const hasActivity = stats && (stats.total_sent > 0 || campaigns.length > 0);

  return (
    <>
      <h1 className="text-2xl font-bold mb-6">Dashboard</h1>

      {!hasActivity ? (
        /* Empty state — no campaigns yet */
        <div className="space-y-6">
          <div className="bg-surface rounded-xl border border-border p-10 text-center">
            <div className="w-16 h-16 rounded-full bg-accent/10 flex items-center justify-center mx-auto mb-5">
              <svg className="w-8 h-8 text-accent" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M3 8l7.89 5.26a2 2 0 002.22 0L21 8M5 19h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v10a2 2 0 002 2z" />
              </svg>
            </div>
            <h2 className="text-lg font-bold mb-2">Ready to start outreach?</h2>
            <p className="text-text-muted text-sm max-w-md mx-auto mb-6">
              Create your first campaign and ColdPilot will find contacts, research companies, write personalised emails, and send them on your behalf.
            </p>
            <Link
              href="/campaigns/new"
              className="inline-flex bg-accent hover:bg-accent-hover text-white text-sm px-6 py-3 rounded-lg transition-colors font-medium"
            >
              Create Your First Campaign
            </Link>
          </div>

          <div className="grid md:grid-cols-3 gap-4">
            <StepCard
              step={1}
              title="Configure email"
              description="Add your Gmail and App Password in Settings so ColdPilot can send on your behalf."
              href="/settings"
            />
            <StepCard
              step={2}
              title="Create a campaign"
              description="Choose Hunter (outbound sales) or Seeker (job hunt), define your targets, and set autonomy level."
              href="/campaigns/new"
            />
            <StepCard
              step={3}
              title="Watch it work"
              description="ColdPilot finds contacts, writes emails, and sends them. You approve in Copilot mode or let it run fully autonomous."
              href="/activity"
            />
          </div>
        </div>
      ) : (
        /* Active dashboard with real data */
        <>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-8">
            <StatCard label="Sent Today" value={`${stats!.sent_today} / ${stats!.limit_today}`} />
            <StatCard label="Total Sent" value={stats!.total_sent} />
            <StatCard
              label="Reply Rate"
              value={`${(stats!.reply_rate * 100).toFixed(1)}%`}
              accent={stats!.reply_rate > 0.05}
            />
            <StatCard
              label="Pending Approval"
              value={stats!.pending_approval}
              accent={stats!.pending_approval > 0}
            />
          </div>

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
              <p className="text-sm text-text-muted">No active campaigns right now.</p>
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

function StepCard({ step, title, description, href }: { step: number; title: string; description: string; href: string }) {
  return (
    <Link href={href} className="bg-surface rounded-xl border border-border p-5 hover:bg-surface-elevated transition-colors group">
      <div className="w-8 h-8 rounded-full bg-accent/10 text-accent flex items-center justify-center text-sm font-bold mb-3">
        {step}
      </div>
      <h3 className="font-semibold text-sm mb-1 group-hover:text-accent transition-colors">{title}</h3>
      <p className="text-xs text-text-muted">{description}</p>
    </Link>
  );
}
