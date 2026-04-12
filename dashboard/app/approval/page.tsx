"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
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
    } catch {}
    setActing(null);
  }

  async function handleReject(id: string) {
    setActing(id);
    try {
      await api.rejectEmail(id);
      setEmails((prev) => prev.filter((e) => e.id !== id));
    } catch {}
    setActing(null);
  }

  async function handleRewrite(id: string) {
    setActing(id);
    try {
      await api.rewriteEmail(id);
      await load();
    } catch {}
    setActing(null);
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center min-h-[40vh]">
        <div className="w-8 h-8 border-3 border-border border-t-accent rounded-full animate-spin" />
      </div>
    );
  }

  return (
    <>
      <h1 className="text-2xl font-bold mb-6">Approval Queue</h1>

      {emails.length === 0 ? (
        <div className="bg-surface rounded-xl border border-border p-10 text-center">
          <div className="w-14 h-14 rounded-full bg-accent/10 flex items-center justify-center mx-auto mb-4">
            <svg className="w-7 h-7 text-accent" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
            </svg>
          </div>
          <p className="font-medium mb-2">No emails waiting for approval</p>
          <p className="text-sm text-text-muted mb-5 max-w-sm mx-auto">
            Your campaigns will generate emails here once running. In Copilot mode, every email needs your approval before sending.
          </p>
          <Link
            href="/campaigns/new"
            className="inline-flex bg-accent hover:bg-accent-hover text-white text-sm px-5 py-2.5 rounded-lg transition-colors"
          >
            Create a Campaign
          </Link>
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
