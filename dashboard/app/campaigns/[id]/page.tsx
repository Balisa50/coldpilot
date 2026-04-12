import { api } from "../../lib/api";
import type { Campaign, Prospect, Email, ActionLog } from "../../lib/types";
import CampaignActions from "./CampaignActions";
import ProspectTable from "./ProspectTable";
import EmailList from "./EmailList";
import AddProspectForm from "./AddProspectForm";

export const dynamic = "force-dynamic";

export default async function CampaignDetailPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;

  let campaign: Campaign | null = null;
  let prospects: Prospect[] = [];
  let emails: Email[] = [];
  let activity: ActionLog[] = [];

  try {
    [campaign, prospects, emails, activity] = await Promise.all([
      api.getCampaign(id),
      api.listProspects(id),
      api.listEmails(id),
      api.listCampaignActivity(id, 50),
    ]);
  } catch {
    return (
      <div className="bg-surface rounded-xl border border-border p-8 text-center">
        <p className="text-text-muted">Campaign not found or backend offline</p>
      </div>
    );
  }

  const STATUS_COLORS: Record<string, string> = {
    draft: "bg-text-muted/20 text-text-muted",
    active: "bg-green/20 text-green",
    paused: "bg-amber/20 text-amber",
    completed: "bg-accent/20 text-accent",
  };

  return (
    <>
      {/* Header */}
      <div className="flex items-start justify-between mb-6">
        <div>
          <h1 className="text-2xl font-bold">{campaign!.name}</h1>
          <p className="text-sm text-text-muted capitalize mt-1">
            {campaign!.mode} &middot; {campaign!.autonomy}
            {campaign!.dry_run ? (
              <span className="text-amber ml-2">dry run</span>
            ) : null}
          </p>
        </div>
        <div className="flex items-center gap-3">
          <span
            className={`text-xs px-2.5 py-1 rounded-full capitalize ${STATUS_COLORS[campaign!.status] ?? ""}`}
          >
            {campaign!.status}
          </span>
          <CampaignActions campaign={campaign!} />
        </div>
      </div>

      {/* Info bar */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-8">
        <MiniCard label="Prospects" value={prospects.length} />
        <MiniCard
          label="Emails Drafted"
          value={emails.filter((e) => ["draft", "pending_approval"].includes(e.status)).length}
        />
        <MiniCard
          label="Sent"
          value={emails.filter((e) => e.status === "sent").length}
        />
        <MiniCard
          label="Replied"
          value={emails.filter((e) => e.replied_at).length}
        />
      </div>

      {/* Add prospect */}
      <AddProspectForm campaignId={id} />

      {/* Prospects */}
      <section className="mb-8">
        <h2 className="font-semibold mb-3">Prospects</h2>
        <ProspectTable prospects={prospects} />
      </section>

      {/* Emails */}
      <section className="mb-8">
        <h2 className="font-semibold mb-3">Emails</h2>
        <EmailList emails={emails} />
      </section>

      {/* Activity */}
      <section>
        <h2 className="font-semibold mb-3">Recent Activity</h2>
        {activity.length === 0 ? (
          <p className="text-sm text-text-muted">No activity yet</p>
        ) : (
          <div className="bg-surface rounded-xl border border-border divide-y divide-border max-h-64 overflow-y-auto">
            {activity.map((log) => (
              <div key={log.id} className="px-4 py-2 text-sm">
                <span className="font-medium">
                  {log.action.replace(/_/g, " ")}
                </span>
                {log.detail && (
                  <span className="text-text-secondary ml-1.5">
                    {log.detail}
                  </span>
                )}
                <span className="text-text-muted text-xs ml-2">
                  {new Date(log.created_at).toLocaleTimeString()}
                </span>
              </div>
            ))}
          </div>
        )}
      </section>
    </>
  );
}

function MiniCard({ label, value }: { label: string; value: number }) {
  return (
    <div className="bg-surface rounded-xl border border-border p-3">
      <p className="text-xs text-text-muted">{label}</p>
      <p className="text-lg font-bold mt-0.5">{value}</p>
    </div>
  );
}
