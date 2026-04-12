"use client";

import { useEffect, useState } from "react";
import { api } from "../lib/api";
import type { Settings } from "../lib/types";
import WakeUp from "../components/WakeUp";

export default function SettingsPage() {
  const [settings, setSettings] = useState<Settings | null>(null);
  const [loading, setLoading] = useState(true);
  const [ready, setReady] = useState(false);
  const [smtpResult, setSmtpResult] = useState<{ ok: boolean; message: string } | null>(null);
  const [testing, setTesting] = useState(false);

  // SMTP form fields
  const [gmailAddress, setGmailAddress] = useState("");
  const [appPassword, setAppPassword] = useState("");
  const [senderName, setSenderName] = useState("");
  const [savingSmtp, setSavingSmtp] = useState(false);
  const [saveResult, setSaveResult] = useState<{ ok: boolean; message: string } | null>(null);

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

  async function testSmtp() {
    setTesting(true);
    setSmtpResult(null);
    try {
      const res = await api.validateSmtp();
      setSmtpResult(res);
    } catch (err) {
      setSmtpResult({ ok: false, message: err instanceof Error ? err.message : "Connection failed" });
    }
    setTesting(false);
  }

  async function handleSaveSmtp() {
    if (!gmailAddress.trim()) return;
    setSavingSmtp(true);
    setSaveResult(null);
    try {
      await api.updateSettings({
        smtp_user: gmailAddress.trim(),
        smtp_pass: appPassword.trim(),
        sender_name: senderName.trim(),
        sender_email: gmailAddress.trim(),
      });
      const s = await api.getSettings();
      setSettings(s);
      setSaveResult({ ok: true, message: "Email settings saved successfully." });
      setAppPassword("");
    } catch (err) {
      setSaveResult({ ok: false, message: err instanceof Error ? err.message : "Failed to save" });
    }
    setSavingSmtp(false);
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
    <>
      <h1 className="text-2xl font-bold mb-2">Settings</h1>
      <p className="text-text-muted text-sm mb-6">Configure your email to start sending outreach.</p>

      <div className="space-y-6 max-w-2xl">
        {/* Email Configuration */}
        <section className="bg-surface rounded-xl border border-border p-5">
          <div className="flex items-center justify-between mb-4">
            <h2 className="font-semibold">Email Configuration</h2>
            <span
              className={`text-xs px-2.5 py-1 rounded-full font-medium ${
                settings?.smtp_configured
                  ? "bg-green/15 text-green"
                  : "bg-amber-500/15 text-amber-400"
              }`}
            >
              {settings?.smtp_configured ? "Connected" : "Not configured"}
            </span>
          </div>

          {!settings?.smtp_configured && (
            <div className="bg-accent/5 border border-accent/20 rounded-lg p-3 mb-4">
              <p className="text-sm text-text-secondary">
                To send emails, you need a Gmail address and an App Password.
                Go to your Google Account &rarr; Security &rarr; 2-Step Verification &rarr; App Passwords to generate one.
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

            <label className="block">
              <span className="text-sm text-text-secondary">Sender Name</span>
              <input
                className="input mt-1"
                type="text"
                placeholder="Abdoulie Balisa"
                value={senderName}
                onChange={(e) => setSenderName(e.target.value)}
              />
            </label>

            <div className="flex gap-3 pt-2">
              <button
                onClick={handleSaveSmtp}
                disabled={savingSmtp || !gmailAddress.trim()}
                className="bg-accent hover:bg-accent-hover disabled:opacity-50 text-white text-sm px-5 py-2.5 rounded-lg transition-colors"
              >
                {savingSmtp ? "Saving..." : "Save"}
              </button>

              {settings?.smtp_configured && (
                <button
                  onClick={testSmtp}
                  disabled={testing}
                  className="bg-surface-elevated hover:bg-border text-text-primary text-sm px-5 py-2.5 rounded-lg border border-border transition-colors"
                >
                  {testing ? "Testing..." : "Test Connection"}
                </button>
              )}
            </div>

            {saveResult && (
              <div className={`p-3 rounded-lg text-sm ${saveResult.ok ? "bg-green/10 text-green" : "bg-red/10 text-red"}`}>
                {saveResult.message}
              </div>
            )}

            {smtpResult && (
              <div className={`p-3 rounded-lg text-sm ${smtpResult.ok ? "bg-green/10 text-green" : "bg-red/10 text-red"}`}>
                {smtpResult.ok ? "Connection successful — emails are ready to send." : smtpResult.message}
              </div>
            )}
          </div>
        </section>
      </div>
    </>
  );
}
