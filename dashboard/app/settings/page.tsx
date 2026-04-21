"use client";

import { useEffect, useState } from "react";
import { api } from "../lib/api";
import type { Settings } from "../lib/types";
import WakeUp from "../components/WakeUp";

function StatusBadge({ ok }: { ok: boolean }) {
  return ok ? (
    <span className="inline-flex items-center gap-1.5 text-xs font-medium text-green bg-green/10 px-2.5 py-1 rounded-full">
      <span className="w-1.5 h-1.5 rounded-full bg-green" /> Ready
    </span>
  ) : (
    <span className="inline-flex items-center gap-1.5 text-xs font-medium text-red bg-red/10 px-2.5 py-1 rounded-full">
      <span className="w-1.5 h-1.5 rounded-full bg-red" /> Not configured
    </span>
  );
}

export default function SettingsPage() {
  const [settings, setSettings] = useState<Settings | null>(null);
  const [loading, setLoading] = useState(true);
  const [ready, setReady] = useState(false);
  const [testing, setTesting] = useState(false);
  const [testResult, setTestResult] = useState<{ ok: boolean; message: string } | null>(null);

  useEffect(() => {
    api
      .getSettings()
      .then((s) => { setSettings(s); setReady(true); })
      .catch(() => setReady(false))
      .finally(() => setLoading(false));
  }, []);

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

  const allReady = settings?.smtp_configured && settings?.groq_configured && settings?.tavily_configured;

  return (
    <div className="max-w-2xl mx-auto">
      <h1 className="text-2xl font-bold mb-2">Settings</h1>
      <p className="text-sm text-text-muted mb-6">Service status for this ColdPilot instance.</p>

      {/* Overall status */}
      <div className={`rounded-xl border p-4 mb-6 ${allReady ? "bg-green/5 border-green/20" : "bg-amber-400/5 border-amber-400/20"}`}>
        <div className="flex items-center gap-2">
          <span className={`w-2 h-2 rounded-full ${allReady ? "bg-green" : "bg-amber-400"}`} />
          <p className={`text-sm font-medium ${allReady ? "text-green" : "text-amber-400"}`}>
            {allReady ? "All systems ready — campaigns can send." : "Some services not configured — check below."}
          </p>
        </div>
      </div>

      {/* Service status cards */}
      <div className="space-y-3">
        {/* Email */}
        <div className="bg-surface rounded-xl border border-border p-5">
          <div className="flex items-center justify-between mb-2">
            <div>
              <p className="text-sm font-semibold">Email (SMTP)</p>
              <p className="text-xs text-text-muted mt-0.5">
                {settings?.smtp_user ? `Sending from ${settings.smtp_user}` : "Gmail credentials — set SMTP_USER and SMTP_APP_PASSWORD on Render"}
              </p>
            </div>
            <StatusBadge ok={!!settings?.smtp_configured} />
          </div>

          {settings?.smtp_configured && (
            <div className="flex items-center gap-3 mt-3 pt-3 border-t border-border">
              <button
                onClick={handleTest}
                disabled={testing}
                className="text-xs bg-surface-elevated hover:bg-border border border-border px-4 py-2 rounded-lg transition-colors disabled:opacity-50"
              >
                {testing ? "Testing..." : "Test connection"}
              </button>
              {testResult && (
                <p className={`text-xs ${testResult.ok ? "text-green" : "text-red"}`}>
                  {testResult.ok ? "Connection successful" : testResult.message}
                </p>
              )}
            </div>
          )}

          {!settings?.smtp_configured && (
            <div className="mt-3 pt-3 border-t border-border">
              <p className="text-xs text-text-muted">
                Go to your{" "}
                <a href="https://render.com/dashboard" target="_blank" rel="noreferrer" className="text-accent underline">
                  Render dashboard
                </a>
                {" "}→ coldpilot-api → Environment → add:
              </p>
              <div className="mt-2 font-mono text-xs bg-background rounded-lg p-3 space-y-1">
                <p><span className="text-text-muted">SMTP_USER</span> = your-gmail@gmail.com</p>
                <p><span className="text-text-muted">SMTP_APP_PASSWORD</span> = xxxx-xxxx-xxxx-xxxx</p>
              </div>
            </div>
          )}
        </div>

        {/* Groq */}
        <div className="bg-surface rounded-xl border border-border p-5">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm font-semibold">Groq (LLM)</p>
              <p className="text-xs text-text-muted mt-0.5">Writes personalised emails — set GROQ_API_KEY on Render</p>
            </div>
            <StatusBadge ok={!!settings?.groq_configured} />
          </div>
        </div>

        {/* Tavily */}
        <div className="bg-surface rounded-xl border border-border p-5">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm font-semibold">Tavily (Research)</p>
              <p className="text-xs text-text-muted mt-0.5">Company research before writing — set TAVILY_API_KEY on Render</p>
            </div>
            <StatusBadge ok={!!settings?.tavily_configured} />
          </div>
        </div>

        {/* Hunter */}
        <div className="bg-surface rounded-xl border border-border p-5">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm font-semibold">Hunter.io (Contact Finder)</p>
              <p className="text-xs text-text-muted mt-0.5">Finds email addresses for Hunter mode — set HUNTER_API_KEY on Render</p>
            </div>
            <StatusBadge ok={!!settings?.hunter_configured} />
          </div>
        </div>
      </div>

      <p className="text-xs text-text-muted text-center mt-6">
        All credentials are managed on Render — never entered here. Users never see or configure API keys.
      </p>
    </div>
  );
}
