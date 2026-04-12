"use client";

import { useEffect, useState } from "react";
import { api } from "../lib/api";
import type { Email } from "../lib/types";

export default function ApprovalQueuePage() {
  const [emails, setEmails] = useState<Email[]>([]);
  const [loading, setLoading] = useState(true);
  const [acting, setActing] = useState<string | null>(null);

  async function load() {
    try {
      const data = await api.listPendingEmails();
      setEmails(data);
    } catch {
      // offline
    }
    setLoading(false);
  }

  useEffect(() => {
    load();
  }, []);

  async function handleApprove(id: string) {
    setActing(id);
    try {
      await api.approveEmail(id);
      setEmails((prev) => prev.filter((e) => e.id !== id));
    } catch {
      // ignore
    }
    setActing(null);
  }

  async function handleReject(id: string) {
    setActing(id);
    try {
      await api.rejectEmail(id);
      setEmails((prev) => prev.filter((e) => e.id !== id));
    } catch {
      // ignore
    }
    setActing(null);
  }

  async function handleRewrite(id: string) {
    setActing(id);
    try {
      await api.rewriteEmail(id);
      await load();
    } catch {
      // ignore
    }
    setActing(null);
  }

  if (loading) {
    return <p className="text-text-muted">Loading...</p>;
  }

  return (
    <>
      <h1 className="text-2xl font-bold mb-6">Approval Queue</h1>

      {emails.length === 0 ? (
        <div className="bg-surface rounded-xl border border-border p-8 text-center">
          <p className="text-text-muted">No emails pending approval</p>
        </div>
      ) : (
        <div className="space-y-4">
          {emails.map((email) => (
            <div
              key={email.id}
              className="bg-surface rounded-xl border border-border p-5"
            >
              <div className="flex items-start justify-between mb-3">
                <div>
                  <h3 className="font-medium">{email.subject}</h3>
                  <p className="text-xs text-text-muted capitalize mt-0.5">
                    {email.email_type.replace(/_/g, " ")}
                    {email.prospect &&
                      ` — ${email.prospect.contact_name ?? email.prospect.company_name}`}
                    {email.prospect?.contact_email &&
                      ` <${email.prospect.contact_email}>`}
                  </p>
                </div>
              </div>

              <div
                className="text-sm text-text-secondary whitespace-pre-wrap bg-background rounded-lg p-4 mb-3 max-h-48 overflow-y-auto"
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

              <div className="flex gap-2">
                <button
                  onClick={() => handleApprove(email.id)}
                  disabled={acting === email.id}
                  className="text-xs bg-green/20 text-green hover:bg-green/30 px-4 py-1.5 rounded-lg transition-colors disabled:opacity-50"
                >
                  Approve & Send
                </button>
                <button
                  onClick={() => handleRewrite(email.id)}
                  disabled={acting === email.id}
                  className="text-xs bg-accent/20 text-accent hover:bg-accent/30 px-4 py-1.5 rounded-lg transition-colors disabled:opacity-50"
                >
                  Rewrite
                </button>
                <button
                  onClick={() => handleReject(email.id)}
                  disabled={acting === email.id}
                  className="text-xs bg-red/20 text-red hover:bg-red/30 px-4 py-1.5 rounded-lg transition-colors disabled:opacity-50"
                >
                  Reject
                </button>
              </div>
            </div>
          ))}
        </div>
      )}
    </>
  );
}
