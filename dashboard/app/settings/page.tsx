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
        <p className="text-text-muted">Backend offline</p>
      </div>
    );
  }

  return (
    <>
      <h1 className="text-2xl font-bold mb-6">Settings</h1>

      <div className="space-y-6 max-w-2xl">
        {/* Service status */}
        <section className="bg-surface rounded-xl border border-border p-5">
          <h2 className="font-semibold mb-4">Service Configuration</h2>
          <div className="space-y-3">
            <ServiceRow
              label="SMTP (Email Sending)"
              configured={settings.smtp_configured}
              detail={settings.smtp_user || undefined}
            />
            <ServiceRow label="Hunter.io (Contact Finding)" configured={settings.hunter_configured} />
            <ServiceRow label="Tavily (Research)" configured={settings.tavily_configured} />
            <ServiceRow label="Groq (AI Writing)" configured={settings.groq_configured} />
          </div>
        </section>

        {/* SMTP test */}
        <section className="bg-surface rounded-xl border border-border p-5">
          <h2 className="font-semibold mb-3">Test SMTP Connection</h2>
          <button
            onClick={testSmtp}
            disabled={testing === "smtp"}
            className="bg-accent hover:bg-accent-hover disabled:opacity-50 text-white text-sm px-4 py-2 rounded-lg transition-colors"
          >
            {testing === "smtp" ? "Testing..." : "Test SMTP"}
          </button>
          {smtpResult && (
            <p
              className={`text-sm mt-3 ${smtpResult.ok ? "text-green" : "text-red"}`}
            >
              {smtpResult.ok ? "Connected successfully" : smtpResult.message}
            </p>
          )}
        </section>

        {/* API key test */}
        <section className="bg-surface rounded-xl border border-border p-5">
          <h2 className="font-semibold mb-3">Test API Keys</h2>
          <button
            onClick={testKeys}
            disabled={testing === "keys"}
            className="bg-accent hover:bg-accent-hover disabled:opacity-50 text-white text-sm px-4 py-2 rounded-lg transition-colors"
          >
            {testing === "keys" ? "Testing..." : "Test All Keys"}
          </button>
          {keysResult && (
            <div className="mt-3 space-y-1 text-sm">
              {Object.entries(keysResult).map(([key, val]) => (
                <p key={key} className={val.ok ? "text-green" : "text-red"}>
                  {key}: {val.ok ? "valid" : "invalid"}
                </p>
              ))}
            </div>
          )}
        </section>

        {/* .env hint */}
        <section className="bg-surface rounded-xl border border-border p-5">
          <h2 className="font-semibold mb-3">Configuration</h2>
          <p className="text-sm text-text-secondary mb-2">
            Set these in your <code className="text-accent">.env</code> file:
          </p>
          <pre className="text-xs text-text-muted bg-background rounded-lg p-3 overflow-x-auto">
{`SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=you@gmail.com
SMTP_PASS=app-password
SENDER_NAME=Your Name
SENDER_EMAIL=you@gmail.com

HUNTER_API_KEY=...
TAVILY_API_KEY=...
GROQ_API_KEY=...`}
          </pre>
        </section>
      </div>
    </>
  );
}

function ServiceRow({
  label,
  configured,
  detail,
}: {
  label: string;
  configured: boolean;
  detail?: string;
}) {
  return (
    <div className="flex items-center justify-between py-1">
      <div>
        <p className="text-sm">{label}</p>
        {detail && <p className="text-xs text-text-muted">{detail}</p>}
      </div>
      <span
        className={`text-xs px-2 py-0.5 rounded-full ${
          configured
            ? "bg-green/20 text-green"
            : "bg-red/20 text-red"
        }`}
      >
        {configured ? "Configured" : "Missing"}
      </span>
    </div>
  );
}
