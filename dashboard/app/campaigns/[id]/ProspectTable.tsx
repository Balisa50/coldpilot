"use client";

import type { Prospect } from "../../lib/types";

const STATUS_COLORS: Record<string, string> = {
  pending: "text-text-muted",
  researching: "text-accent",
  contact_found: "text-accent",
  email_drafted: "text-amber",
  email_approved: "text-green",
  email_sent: "text-green",
  replied: "text-green",
  bounced: "text-red",
  opted_out: "text-text-muted",
  failed: "text-red",
};

export default function ProspectTable({ prospects }: { prospects: Prospect[] }) {
  if (prospects.length === 0) {
    return (
      <p className="text-sm text-text-muted bg-surface rounded-xl border border-border p-6 text-center">
        No prospects yet — add companies above to get started
      </p>
    );
  }

  return (
    <div className="bg-surface rounded-xl border border-border overflow-x-auto">
      <table className="w-full text-sm">
        <thead>
          <tr className="border-b border-border text-text-muted text-xs text-left">
            <th className="px-4 py-2.5 font-medium">Company</th>
            <th className="px-4 py-2.5 font-medium">Contact</th>
            <th className="px-4 py-2.5 font-medium">Email</th>
            <th className="px-4 py-2.5 font-medium">Status</th>
          </tr>
        </thead>
        <tbody className="divide-y divide-border">
          {prospects.map((p) => (
            <tr key={p.id} className="hover:bg-surface-elevated transition-colors">
              <td className="px-4 py-2.5">
                <p className="font-medium">{p.company_name}</p>
                {p.company_domain && (
                  <p className="text-xs text-text-muted">{p.company_domain}</p>
                )}
              </td>
              <td className="px-4 py-2.5">
                {p.contact_name ? (
                  <>
                    <p>{p.contact_name}</p>
                    {p.contact_role && (
                      <p className="text-xs text-text-muted">{p.contact_role}</p>
                    )}
                  </>
                ) : (
                  <span className="text-text-muted">—</span>
                )}
              </td>
              <td className="px-4 py-2.5 text-text-secondary">
                {p.contact_email ?? <span className="text-text-muted">—</span>}
              </td>
              <td className="px-4 py-2.5">
                <span
                  className={`text-xs capitalize ${STATUS_COLORS[p.status] ?? "text-text-muted"}`}
                >
                  {p.status.replace(/_/g, " ")}
                </span>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
