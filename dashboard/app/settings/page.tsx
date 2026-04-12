"use client";

import { useEffect, useState } from "react";
import { api } from "../lib/api";
import type { Settings } from "../lib/types";

export default function SettingsPage() {
  const [settings, setSettings] = useState<Settings | null>(null);
  const [loading, setLoading] = useState(true);
  const [smtpResult, setSmtpResult] = useState<{ ok: boolean; message: string } | null>(null);
  const [keysResult, setKeysResult] = useState<Record<string, { ok: boolean }> | null>(null);
  const [testing, setTesting] = useState<string | null>(null);

  useEffect(() => {
    api
      .getSettings()
      .then(setSettings)
      .catch(() => setSettings(null))
      .finally(() => setLoading(false));
  }, []);

  async function testSmtp() {
    setTesting("smtp");
    setSmtpResult(null);
    try {
      const res = await api.validateSmtp();
      setSmtpResult(res);
    } catch (err) {
      setSmtpResult({ ok: false, message: err instanceof Error ? err.message : "Failed" });
    }
    setTesting(null);
  }

  async function testKeys() {
    setTesting("keys");
    setKeysResult(null);
    try {
      const res = await api.validateKeys();
      setKeysResult(res);
    } catch {
      setKeysResult(null);
    }
    setTesting(null);
  }

  if (loading) {
    return <p className="text-text-muted">Loading settings...</p>;
  }

  if (!settings) {
    return (
      <div className="bg-surface rounded-xl border border-border p-8 text-center">
        <p className="text-xl font-bold mb-2">Backend Offline</p>
        <p className="text-text-muted text-sm">The ColdPilot server isn&apos;t responding. Please wait a moment and refresh — free instances take up to 50 seconds to wake up.</p>
      </div>
    );
  }

  return (
    <>
      <h1 className="text-2xl font-bold mb-2">Settings</h1>
      <p className="text-text-muted text-sm mb-6">Manage your email and API service connections.</p>

      <div className="space-y-6 max-w-2xl">
        {/* Service status */}
        <section className="bg-surface rounded-xl border border-border p-5">
          <h2 className="font-semibold mb-4">Service Status</h2>
          <div className="space-y-3">
            <ServiceRow
              label="Email (SMTP)"
              configured={settings.smtp_configured}
              detail={settings.smtp_user || undefined}
              hint="Gmail address and App Password are needed to send outreach emails."
            />
            <ServiceRow
              label="Hunter.io"
              configured={settings.hunter_configured}
              hint="Finds professional email addresses for your prospects."
            />
            <ServiceRow
              label="Tavily"
              configured={settings.tavily_configured}
              hint="Researches prospects and companies for personalized emails."
            />
            <ServiceRow
              label="Groq AI"
              configured={settings.groq_configured}
              hint="Powers email writing and subject line generation."
            />
          </div>
        </section>

        {/* Connection tests */}
        <section className="bg-surface rounded-xl border border-border p-5">
          <h2 className="font-semibold mb-3">Test Connections</h2>
          <p className="text-sm text-text-muted mb-4">Verify your services are working correctly.</p>
          <div className="flex flex-wrap gap-3">
            <button
              onClick={testSmtp}
              disabled={testing === "smtp"}
              className="bg-accent hover:bg-accent-hover disabled:opacity-50 text-white text-sm px-4 py-2 rounded-lg transition-colors"
            >
              {testing === "smtp" ? "Testing..." : "Test Email"}
            </button>
            <button
              onClick={testKeys}
              disabled={testing === "keys"}
              className="bg-surface-elevated hover:bg-border text-text-primary text-sm px-4 py-2 rounded-lg border border-border transition-colors"
            >
              {testing === "keys" ? "Testing..." : "Test API Keys"}
            </button>
          </div>

          {smtpResult && (
            <div className={`mt-4 p-3 rounded-lg text-sm ${smtpResult.ok ? "bg-green/10 text-green" : "bg-red/10 text-red"}`}>
              {smtpResult.ok ? "Email connection successful — you can send outreach." : smtpResult.message}
            </div>
          )}
          {keysResult && (
            <div className="mt-4 space-y-2">
              {Object.entries(keysResult).map(([key, val]) => (
                <div key={key} className={`p-3 rounded-lg text-sm flex items-center gap-2 ${val.ok ? "bg-green/10 text-green" : "bg-red/10 text-red"}`}>
                  <span className={`w-2 h-2 rounded-full ${val.ok ? "bg-green" : "bg-red"}`} />
                  {key}: {val.ok ? "Connected" : "Failed — check your key"}
                </div>
              ))}
            </div>
          )}
        </section>
      </div>
    </>
  );
}

function ServiceRow({
  label,
  configured,
  detail,
  hint,
}: {
  label: string;
  configured: boolean;
  detail?: string;
  hint: string;
}) {
  return (
    <div className="flex items-start justify-between gap-4 py-2">
      <div className="flex-1 min-w-0">
        <p className="text-sm font-medium">{label}</p>
        {detail && <p className="text-xs text-accent mt-0.5">{detail}</p>}
        {!configured && (
          <p className="text-xs text-text-muted mt-0.5">{hint}</p>
        )}
      </div>
      <span
        className={`text-xs px-2.5 py-1 rounded-full font-medium shrink-0 ${
          configured
            ? "bg-green/15 text-green"
            : "bg-amber-500/15 text-amber-400"
        }`}
      >
        {configured ? "Connected" : "Not configured"}
      </span>
    </div>
  );
}
