"use client";

import { useEffect, useState } from "react";
import { api } from "../lib/api";
import type { Settings } from "../lib/types";
import WakeUp from "../components/WakeUp";

function StatusBadge({ ok }: { ok: boolean }) {
  return ok ? (
    <span className="inline-flex items-center gap-1.5 text-xs font-medium text-green bg-green/10 px-2.5 py-1 rounded-full">
      <span className="w-1.5 h-1.5 rounded-full bg-green" /> Connected
    </span>
  ) : (
    <span className="inline-flex items-center gap-1.5 text-xs font-medium text-amber-400 bg-amber-400/10 px-2.5 py-1 rounded-full">
      <span className="w-1.5 h-1.5 rounded-full bg-amber-400" /> Not configured
    </span>
  );
}

export default function SettingsPage() {
  const [settings, setSettings] = useState<Settings | null>(null);
  const [loading, setLoading] = useState(true);
  const [ready, setReady] = useState(false);

  // SMTP form state
  const [smtpUser, setSmtpUser] = useState("");
  const [smtpPass, setSmtpPass] = useState("");
  const [senderName, setSenderName] = useState("");
  const [saving, setSaving] = useState(false);
  const [saveMsg, setSaveMsg] = useState<{ ok: boolean; text: string } | null>(null);

  // Test connection
  const [testing, setTesting] = useState(false);
  const [testResult, setTestResult] = useState<{ ok: boolean; message: string } | null>(null);

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
    setSaving(true);
    setSaveMsg(null);
    try {
      await api.updateSettings({ smtp_user: smtpUser, smtp_app_password: smtpPass, sender_name: senderName });
      setSaveMsg({ ok: true, text: "Saved. Test the connection below." });
      const s = await api.getSettings();
      setSettings(s);
    } catch (err) {
      setSaveMsg({ ok: false, text: err instanceof Error ? err.message : "Save failed" });
    }
    setSaving(false);
  }

  async function handleTest() {
    setTesting(true);
    setTestResult(null);
    try {
      const res = await api.validateSmtp();
      setTestResult(res);
    } catch (err) {
      setTestResult({ ok: false, message: err instanceof Error ? err.message : "Connection failed" });
    }
    setTesting(false);
  }

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

      {/* Email setup */}
      <div className="bg-surface border border-border rounded-xl p-6">
        <div className="flex items-center justify-between mb-1">
          <p className="text-sm font-semibold">Your sending email</p>
          <StatusBadge ok={!!settings?.smtp_configured} />
        </div>
        <p className="text-xs text-text-muted mb-5">
          ColdPilot sends campaigns from your Gmail. Use a{" "}
          <a
            href="https://support.google.com/accounts/answer/185833"
            target="_blank"
            rel="noreferrer"
            className="text-accent underline"
          >
            Gmail App Password
          </a>
          {" "}(not your regular password).
        </p>

        <form onSubmit={handleSave} className="space-y-4">
          <label className="block">
            <span className="text-sm text-text-secondary">Gmail address</span>
            <input
              type="email"
              value={smtpUser}
              onChange={(e) => setSmtpUser(e.target.value)}
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
              onChange={(e) => setSmtpPass(e.target.value)}
              placeholder={settings?.smtp_configured ? "••••••••••••••••" : "xxxx xxxx xxxx xxxx"}
              required={!settings?.smtp_configured}
              className="input mt-1"
            />
            <span className="text-xs text-text-muted mt-1 block">
              Leave blank to keep existing password.
            </span>
          </label>

          <label className="block">
            <span className="text-sm text-text-secondary">Your name (appears in From: field)</span>
            <input
              type="text"
              value={senderName}
              onChange={(e) => setSenderName(e.target.value)}
              placeholder="Jane Smith"
              className="input mt-1"
            />
          </label>

          <div className="flex items-center gap-4 pt-1">
            <button
              type="submit"
              disabled={saving}
              className="bg-accent hover:bg-accent-hover disabled:opacity-50 text-white text-sm px-5 py-2.5 rounded-lg transition-colors"
            >
              {saving ? "Saving..." : "Save"}
            </button>
            {settings?.smtp_configured && (
              <button
                type="button"
                onClick={handleTest}
                disabled={testing}
                className="text-sm text-text-secondary hover:text-accent transition-colors disabled:opacity-50"
              >
                {testing ? "Testing..." : "Test connection"}
              </button>
            )}
            {saveMsg && (
              <p className={`text-xs ${saveMsg.ok ? "text-green" : "text-red"}`}>{saveMsg.text}</p>
            )}
            {testResult && (
              <p className={`text-xs ${testResult.ok ? "text-green" : "text-red"}`}>
                {testResult.ok ? "Connected" : testResult.message}
              </p>
            )}
          </div>
        </form>
      </div>

      {/* API service status — read-only, operator configures these */}
      <div className="bg-surface border border-border rounded-xl p-5 space-y-3">
        <p className="text-xs text-text-muted uppercase tracking-wider font-medium">Service status</p>
        {[
          { label: "AI (Groq)", ok: !!settings?.groq_configured, note: "Writes and personalises emails" },
          { label: "Research (Tavily)", ok: !!settings?.tavily_configured, note: "Researches companies before writing" },
          { label: "Contact finder (Hunter.io)", ok: !!settings?.hunter_configured, note: "Finds email addresses for Hunter mode" },
        ].map((s) => (
          <div key={s.label} className="flex items-center justify-between">
            <div>
              <p className="text-sm font-medium">{s.label}</p>
              <p className="text-xs text-text-muted">{s.note}</p>
            </div>
            <StatusBadge ok={s.ok} />
          </div>
        ))}
      </div>

    </div>
  );
}
