"use client";

import { useEffect, useState } from "react";
import { api } from "../lib/api";
import type { Settings } from "../lib/types";
import WakeUp from "../components/WakeUp";

type SaveStatus = "idle" | "saving" | "verifying" | "success" | "error";

function StatusDot({ ok }: { ok: boolean }) {
  return ok ? (
    <span className="inline-flex items-center gap-1.5 text-xs font-medium text-green bg-green/10 px-2.5 py-1 rounded-full">
      <span className="w-1.5 h-1.5 rounded-full bg-green" /> Active
    </span>
  ) : (
    <span className="inline-flex items-center gap-1.5 text-xs font-medium text-text-muted bg-surface-elevated px-2.5 py-1 rounded-full">
      <span className="w-1.5 h-1.5 rounded-full bg-text-muted" /> Not configured
    </span>
  );
}

export default function SettingsPage() {
  const [settings, setSettings] = useState<Settings | null>(null);
  const [loading, setLoading] = useState(true);
  const [ready, setReady] = useState(false);

  // Form state
  const [smtpUser, setSmtpUser] = useState("");
  const [smtpPass, setSmtpPass] = useState("");
  const [senderName, setSenderName] = useState("");

  // Save + verify state (combined into one flow)
  const [status, setStatus] = useState<SaveStatus>("idle");
  const [errorMsg, setErrorMsg] = useState("");

  useEffect(() => {
    api
      .getSettings()
      .then((s) => {
        setSettings(s);
        setSmtpUser(s.smtp_user || "");
        setSenderName((s as any).sender_name || "");
        setReady(true);
      })
      .catch(() => setReady(false))
      .finally(() => setLoading(false));
  }, []);

  async function handleSave(e: React.FormEvent) {
    e.preventDefault();
    setStatus("saving");
    setErrorMsg("");

    // Step 1: Save credentials
    try {
      await api.updateSettings({
        smtp_user: smtpUser,
        smtp_app_password: smtpPass,
        sender_name: senderName,
      });
    } catch (err) {
      setStatus("error");
      setErrorMsg(err instanceof Error ? err.message : "Failed to save. Please try again.");
      return;
    }

    // Step 2: Immediately verify they actually work
    setStatus("verifying");
    try {
      const result = await api.validateSmtp();
      if (result.ok) {
        setStatus("success");
        const s = await api.getSettings();
        setSettings(s);
      } else {
        setStatus("error");
        setErrorMsg(
          result.message?.toLowerCase().includes("auth")
            ? "Authentication failed. Check your Gmail address and App Password."
            : result.message || "Could not connect. Check your credentials and try again."
        );
      }
    } catch {
      setStatus("error");
      setErrorMsg(
        "Could not reach the email server. Check your credentials and make sure your Gmail App Password is correct."
      );
    }
  }

  const isAlreadyConfigured = !!settings?.smtp_configured;
  const isBusy = status === "saving" || status === "verifying";

  const statusLabel = {
    idle: isAlreadyConfigured ? "Save Changes" : "Save & Connect",
    saving: "Saving...",
    verifying: "Verifying connection...",
    success: "Save & Connect",
    error: "Save & Connect",
  }[status];

  if (!ready && !loading) {
    return <WakeUp brandName="ColdPilot" accentPart="Pilot" onReady={() => window.location.reload()} />;
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center min-h-[40vh]">
        <div className="w-8 h-8 border-2 border-border border-t-accent rounded-full animate-spin" />
      </div>
    );
  }

  return (
    <div className="max-w-2xl mx-auto space-y-6">

      {/* Sending email */}
      <div className="bg-surface border border-border rounded-xl p-6">
        <div className="flex items-center justify-between mb-1">
          <p className="text-sm font-semibold text-text-primary">Sending account</p>
          <StatusDot ok={isAlreadyConfigured} />
        </div>
        <p className="text-xs text-text-muted mb-5">
          ColdPilot sends all campaign emails directly from your Gmail inbox.
          You need a{" "}
          <a
            href="https://support.google.com/accounts/answer/185833"
            target="_blank"
            rel="noreferrer"
            className="text-accent underline"
          >
            Gmail App Password
          </a>
          {" "}— a separate password Gmail generates for third-party apps. It takes about 30 seconds to create.
        </p>

        <form onSubmit={handleSave} className="space-y-4">
          <label className="block">
            <span className="text-sm text-text-secondary">Gmail address</span>
            <input
              type="email"
              value={smtpUser}
              onChange={(e) => { setSmtpUser(e.target.value); setStatus("idle"); }}
              placeholder="you@gmail.com"
              required
              className="input mt-1"
            />
          </label>

          <label className="block">
            <span className="text-sm text-text-secondary">App Password</span>
            <input
              type="password"
              value={smtpPass}
              onChange={(e) => { setSmtpPass(e.target.value); setStatus("idle"); }}
              placeholder={isAlreadyConfigured ? "Enter new password to update" : "xxxx xxxx xxxx xxxx"}
              required={!isAlreadyConfigured}
              className="input mt-1"
            />
            {isAlreadyConfigured && (
              <span className="text-xs text-text-muted mt-1 block">
                Only fill this in if you want to update your password.
              </span>
            )}
          </label>

          <label className="block">
            <span className="text-sm text-text-secondary">Your name</span>
            <input
              type="text"
              value={senderName}
              onChange={(e) => { setSenderName(e.target.value); setStatus("idle"); }}
              placeholder="Jane Smith"
              className="input mt-1"
            />
            <span className="text-xs text-text-muted mt-1 block">
              This is what recipients see in the From field.
            </span>
          </label>

          {/* Save button + feedback */}
          <div className="pt-1 space-y-3">
            <button
              type="submit"
              disabled={isBusy}
              className="bg-accent hover:bg-accent-hover disabled:opacity-60 text-white text-sm px-5 py-2.5 rounded-lg transition-colors flex items-center gap-2"
            >
              {isBusy && (
                <span className="w-3.5 h-3.5 border-2 border-white/30 border-t-white rounded-full animate-spin" />
              )}
              {statusLabel}
            </button>

            {/* Success */}
            {status === "success" && (
              <div className="flex items-center gap-2 text-sm text-green bg-green/10 rounded-lg px-4 py-3">
                <svg className="w-4 h-4 shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2.5}>
                  <path strokeLinecap="round" strokeLinejoin="round" d="M5 13l4 4L19 7" />
                </svg>
                Connected. Your campaigns will send from {smtpUser}.
              </div>
            )}

            {/* Error */}
            {status === "error" && (
              <div className="flex items-start gap-2 text-sm text-red bg-red/10 rounded-lg px-4 py-3">
                <svg className="w-4 h-4 shrink-0 mt-0.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2.5}>
                  <path strokeLinecap="round" strokeLinejoin="round" d="M12 9v4m0 4h.01M10.29 3.86L1.82 18a2 2 0 001.71 3h16.94a2 2 0 001.71-3L13.71 3.86a2 2 0 00-3.42 0z" />
                </svg>
                <span>{errorMsg}</span>
              </div>
            )}

            {/* Verifying indicator */}
            {status === "verifying" && (
              <p className="text-xs text-text-muted">Checking connection to Gmail...</p>
            )}
          </div>
        </form>
      </div>

      {/* Platform services — read-only status, no tool names exposed */}
      <div className="bg-surface border border-border rounded-xl p-5 space-y-4">
        <div>
          <p className="text-xs text-text-muted uppercase tracking-wider font-medium">Platform services</p>
          <p className="text-xs text-text-muted mt-1">
            These are managed by ColdPilot. No action needed on your part.
          </p>
        </div>
        {[
          {
            label: "Email writing",
            note: "AI that writes and personalises every outreach email",
            ok: !!settings?.groq_configured,
          },
          {
            label: "Company research",
            note: "Researches each target company before writing the email",
            ok: !!settings?.tavily_configured,
          },
          {
            label: "Contact finder",
            note: "Finds the right person to contact at each company",
            ok: !!settings?.hunter_configured,
          },
        ].map((s) => (
          <div key={s.label} className="flex items-center justify-between">
            <div>
              <p className="text-sm font-medium text-text-primary">{s.label}</p>
              <p className="text-xs text-text-muted">{s.note}</p>
            </div>
            <StatusDot ok={s.ok} />
          </div>
        ))}
      </div>

    </div>
  );
}
