import Link from "next/link";
import { api } from "../lib/api";
import type { Campaign } from "../lib/types";

export const dynamic = "force-dynamic";

const STATUS_COLORS: Record<string, string> = {
  draft: "bg-text-muted/20 text-text-muted",
  active: "bg-green/20 text-green",
  paused: "bg-amber/20 text-amber",
  completed: "bg-accent/20 text-accent",
};

export default async function CampaignsPage() {
  let campaigns: Campaign[] = [];
  try {
    campaigns = await api.listCampaigns();
  } catch {
    // offline
  }

  return (
    <>
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-2xl font-bold">Campaigns</h1>
        <Link
          href="/campaigns/new"
          className="bg-accent hover:bg-accent-hover text-white text-sm px-4 py-2 rounded-lg transition-colors"
        >
          + New Campaign
        </Link>
      </div>

      {campaigns.length === 0 ? (
        <div className="bg-surface rounded-xl border border-border p-12 text-center">
          <p className="text-text-muted mb-4">No campaigns yet</p>
          <Link
            href="/campaigns/new"
            className="text-accent hover:text-accent-hover text-sm"
          >
            Create your first campaign
          </Link>
        </div>
      ) : (
        <div className="space-y-3">
          {campaigns.map((c) => (
            <Link
              key={c.id}
              href={`/campaigns/${c.id}`}
              className="flex items-center justify-between bg-surface rounded-xl border border-border p-4 hover:bg-surface-elevated transition-colors"
            >
              <div className="flex items-center gap-4">
                <div>
                  <p className="font-medium">{c.name}</p>
                  <p className="text-xs text-text-muted capitalize mt-0.5">
                    {c.mode} &middot; {c.autonomy}{" "}
                    {c.dry_run ? (
                      <span className="text-amber">&middot; dry run</span>
                    ) : null}
                  </p>
                </div>
              </div>

              <div className="flex items-center gap-6 text-sm">
                <div className="text-right text-xs text-text-secondary">
                  <p>{c.prospect_count ?? 0} prospects</p>
                  <p>
                    {c.sent_count ?? 0} sent &middot; {c.replied_count ?? 0}{" "}
                    replied
                  </p>
                </div>
                <span
                  className={`text-xs px-2 py-0.5 rounded-full capitalize ${STATUS_COLORS[c.status] ?? ""}`}
                >
                  {c.status}
                </span>
              </div>
            </Link>
          ))}
        </div>
      )}
    </>
  );
}
