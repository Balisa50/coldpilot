"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { api } from "../../lib/api";
import type { Email } from "../../lib/types";

const STATUS_COLORS: Record<string, string> = {
  draft: "bg-text-muted/20 text-text-muted",
  pending_approval: "bg-amber/20 text-amber",
  approved: "bg-green/20 text-green",
  sent: "bg-green/20 text-green",
  bounced: "bg-red/20 text-red",
  failed: "bg-red/20 text-red",
};

export default function EmailList({ emails }: { emails: Email[] }) {
  const router = useRouter();
  const [expanded, setExpanded] = useState<string | null>(null);
  const [acting, setActing] = useState<string | null>(null);

  if (emails.length === 0) {
    return (
      <p className="text-sm text-text-muted bg-surface rounded-xl border border-border p-6 text-center">
        No emails yet
      </p>
    );
  }

  async function handleApprove(id: string) {
    setActing(id);
    try {
      await api.approveEmail(id);
      router.refresh();
    } catch {
      // ignore
    }
    setActing(null);
  }

  async function handleReject(id: string) {
    setActing(id);
    try {
      await api.rejectEmail(id);
      router.refresh();
    } catch {
      // ignore
    }
    setActing(null);
  }

  async function handleRewrite(id: string) {
    setActing(id);
    try {
      await api.rewriteEmail(id);
      router.refresh();
    } catch {
      // ignore
    }
    setActing(null);
  }

  return (
    <div className="space-y-2">
      {emails.map((email) => (
        <div
          key={email.id}
          className="bg-surface rounded-xl border border-border"
        >
          {/* Header row */}
          <button
            onClick={() =>
              setExpanded(expanded === email.id ? null : email.id)
            }
            className="w-full flex items-center justify-between px-4 py-3 text-left hover:bg-surface-elevated transition-colors rounded-xl"
          >
            <div className="flex-1 min-w-0">
              <p className="text-sm font-medium truncate">{email.subject}</p>
              <p className="text-xs text-text-muted mt-0.5 capitalize">
                {email.email_type.replace(/_/g, " ")}
                {email.prospect && ` — ${email.prospect.company_name}`}
              </p>
            </div>
            <span
              className={`text-xs px-2 py-0.5 rounded-full capitalize ml-3 shrink-0 ${STATUS_COLORS[email.status] ?? ""}`}
            >
              {email.status.replace(/_/g, " ")}
            </span>
          </button>

          {/* Expanded body */}
          {expanded === email.id && (
            <div className="px-4 pb-4 border-t border-border pt-3">
              <div
                className="text-sm text-text-secondary whitespace-pre-wrap mb-3"
                dangerouslySetInnerHTML={{
                  __html: email.body_html || email.body_text,
                }}
              />
              {email.personalisation_points && (
                <p className="text-xs text-text-muted mb-3">
                  <span className="font-medium">Personalisation:</span>{" "}
                  {email.personalisation_points}
                </p>
              )}

              {/* Actions for pending emails */}
              {email.status === "pending_approval" && (
                <div className="flex gap-2 pt-2 border-t border-border">
                  <button
                    onClick={() => handleApprove(email.id)}
                    disabled={acting === email.id}
                    className="text-xs bg-green/20 text-green hover:bg-green/30 px-3 py-1.5 rounded-lg transition-colors disabled:opacity-50"
                  >
                    Approve
                  </button>
                  <button
                    onClick={() => handleRewrite(email.id)}
                    disabled={acting === email.id}
                    className="text-xs bg-accent/20 text-accent hover:bg-accent/30 px-3 py-1.5 rounded-lg transition-colors disabled:opacity-50"
                  >
                    Rewrite
                  </button>
                  <button
                    onClick={() => handleReject(email.id)}
                    disabled={acting === email.id}
                    className="text-xs bg-red/20 text-red hover:bg-red/30 px-3 py-1.5 rounded-lg transition-colors disabled:opacity-50"
                  >
                    Reject
                  </button>
                </div>
              )}
            </div>
          )}
        </div>
      ))}
    </div>
  );
}
