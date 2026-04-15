"use client";

import { useEffect, useState } from "react";
import { api } from "../lib/api";
import type { Settings } from "../lib/types";
import WakeUp from "../components/WakeUp";

export default function SettingsPage() {
  const [settings, setSettings] = useState<Settings | null>(null);
  const [loading, setLoading] = useState(true);
  const [ready, setReady] = useState(false);

  // SMTP form
  const [gmailAddress, setGmailAddress] = useState("");
  const [appPassword, setAppPassword] = useState("");
  const [savingSmtp, setSavingSmtp] = useState(false);
  const [saveResult, setSaveResult] = useState<{ ok: boolean; message: string } | null>(null);

  // Test
  const [testing, setTesting] = useState(false);
  const [testResult, setTestResult] = useState<{ ok: boolean; message: string } | null>(null);

  useEffect(() => {
    api
      .getSettings()
      .then((s) => {
        setSettings(s);
        setReady(true);
        if (s.smtp_user) setGmailAddress(s.smtp_user);
      })
      .catch(() => setReady(false))
      .finally(() => setLoading(false));
  }, []);

  async function handleSave() {
    if (!gmailAddress.trim()) return;
    setSavingSmtp(true);
    setSaveResult(null);
    try {
      await api.updateSettings({
        smtp_user: gmailAddress.trim(),
        smtp_pass: appPassword.trim() || undefined,
        sender_email: gmailAddress.trim(),
      });
      const s = await api.getSettings();
      setSettings(s);
      setSaveResult({ ok: true, message: "Email settings saved." });
      setAppPassword("");
    } catch (err) {
      setSaveResult({ ok: false, message: err instanceof Error ? err.message : "Failed to save" });
    }
    setSavingSmtp(false);
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
        <div className="w-8 h-8 border-3 border-border border-t-accent rounded-full animate-spin" />
      </div>
    );
  }

  return (
    <div className="max-w-2xl mx-auto">
      <h1 className="text-2xl font-bold mb-2">Settings</h1>
      <p className="text-text-muted text-sm mb-6">Configure your email to start sending outreach.</p>

      <section className="bg-surface rounded-xl border border-border p-6">
        <div className="flex items-center justify-between mb-5">
          <h2 className="text-lg font-semibold">Email Setup</h2>
          {settings?.smtp_configured && (
            <span className="text-xs px-3 py-1 rounded-full font-medium bg-green/15 text-green">
              Email Connected
            </span>
          )}
        </div>

        {!settings?.smtp_configured && (
          <div className="bg-accent/5 border border-accent/20 rounded-lg p-3 mb-5">
            <p className="text-sm text-text-secondary">
              To send emails, enter your Gmail address and an App Password.
              Generate one at Google Account &rarr; Security &rarr; 2-Step Verification &rarr; App Passwords.
            </p>
          </div>
        )}

        <div className="space-y-4">
          <label className="block">
            <span className="text-sm text-text-secondary">Gmail Address</span>
            <input
              className="input mt-1"
              type="email"
              placeholder="you@gmail.com"
              value={gmailAddress}
              onChange={(e) => setGmailAddress(e.target.value)}
            />
          </label>

          <label className="block">
            <span className="text-sm text-text-secondary">App Password</span>
            <input
              className="input mt-1"
              type="password"
              placeholder="xxxx xxxx xxxx xxxx"
              value={appPassword}
              onChange={(e) => setAppPassword(e.target.value)}
            />
            {settings?.smtp_configured && !appPassword && (
              <p className="text-xs text-text-muted mt-1">Leave blank to keep existing password</p>
            )}
          </label>

          <div className="flex gap-3 pt-2">
            <button
              onClick={handleSave}
              disabled={savingSmtp || !gmailAddress.trim()}
              className="bg-accent hover:bg-accent-hover disabled:opacity-50 text-white text-sm px-5 py-2.5 rounded-lg transition-colors"
            >
              {savingSmtp ? "Saving..." : "Save"}
            </button>

            <button
              onClick={handleTest}
              disabled={testing || !settings?.smtp_configured}
              className="bg-surface-elevated hover:bg-border disabled:opacity-50 text-text-primary text-sm px-5 py-2.5 rounded-lg border border-border transition-colors"
            >
              {testing ? "Testing..." : "Test Connection"}
            </button>
          </div>

          {saveResult && (
            <div className={`p-3 rounded-lg text-sm ${saveResult.ok ? "bg-green/10 text-green" : "bg-red/10 text-red"}`}>
              {saveResult.message}
            </div>
          )}

          {testResult && (
            <div className={`p-3 rounded-lg text-sm ${testResult.ok ? "bg-green/10 text-green" : "bg-red/10 text-red"}`}>
              {testResult.ok ? "Connection successful -- emails are ready to send." : testResult.message}
            </div>
          )}
        </div>
      </section>
    </div>
  );
}
