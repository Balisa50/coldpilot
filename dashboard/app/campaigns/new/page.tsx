"use client";

import { useState, useRef } from "react";
import { useRouter } from "next/navigation";
import { api } from "../../lib/api";
import type {
  CampaignMode,
  AutonomyLevel,
  CampaignCreatePayload,
  TargetCompany,
} from "../../lib/types";

export default function NewCampaignPage() {
  const router = useRouter();
  const [mode, setMode] = useState<CampaignMode>("hunter");
  const [name, setName] = useState("");
  const [autonomy, setAutonomy] = useState<AutonomyLevel>("copilot");
  const [dryRun, setDryRun] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");

  // Hunter fields
  const [companyName, setCompanyName] = useState("");
  const [companyUrl, setCompanyUrl] = useState("");
  const [companyDesc, setCompanyDesc] = useState("");
  const [icpIndustry, setIcpIndustry] = useState("");
  const [icpSize, setIcpSize] = useState("");
  const [icpRoles, setIcpRoles] = useState("");
  const [icpKeywords, setIcpKeywords] = useState("");

  // Seeker fields
  const [cvFile, setCvFile] = useState<File | null>(null);
  const [cvText, setCvText] = useState("");
  const [cvUploading, setCvUploading] = useState(false);
  const [desiredRole, setDesiredRole] = useState("");
  const [targetCompanies, setTargetCompanies] = useState("");
  const fileRef = useRef<HTMLInputElement>(null);

  async function handleCvUpload(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    if (!file) return;
    setCvFile(file);
    setCvUploading(true);

    // Read PDF text client-side for preview
    try {
      const text = await file.text();
      setCvText(text.slice(0, 3000));
    } catch {
      setCvText("[CV uploaded — will be parsed on submit]");
    }
    setCvUploading(false);
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setSaving(true);
    setError("");

    const payload: CampaignCreatePayload = {
      mode,
      name,
      autonomy,
      dry_run: dryRun,
    };

    if (mode === "hunter") {
      payload.company_name = companyName;
      payload.company_url = companyUrl || undefined;
      payload.company_description = companyDesc || undefined;
      if (icpIndustry || icpSize || icpRoles || icpKeywords) {
        payload.ideal_customer_profile = {
          industry: icpIndustry,
          company_size: icpSize,
          roles: icpRoles
            .split(",")
            .map((r) => r.trim())
            .filter(Boolean),
          keywords: icpKeywords
            .split(",")
            .map((k) => k.trim())
            .filter(Boolean),
        };
      }
    } else {
      payload.cv_text = cvText;
      payload.desired_role = desiredRole || undefined;
      if (targetCompanies.trim()) {
        payload.target_companies = targetCompanies
          .split("\n")
          .map((line) => line.trim())
          .filter(Boolean)
          .map((line): TargetCompany => {
            const parts = line.split(",").map((s) => s.trim());
            const [company_name, company_domain, contact_name, contact_email, contact_role] = parts;
            return {
              company_name,
              company_domain: company_domain || undefined,
              contact_name: contact_name || undefined,
              contact_email: contact_email || undefined,
              contact_role: contact_role || undefined,
            };
          });
      }
    }

    try {
      const campaign = await api.createCampaign(payload);
      router.push(`/campaigns/${campaign.id}`);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to create");
      setSaving(false);
    }
  }

  return (
    <>
      <h1 className="text-2xl font-bold mb-6">New Campaign</h1>

      <form
        onSubmit={handleSubmit}
        className="bg-surface rounded-xl border border-border p-6 space-y-6 max-w-2xl"
      >
        {/* Mode */}
        <fieldset>
          <legend className="text-sm font-medium mb-2">Mode</legend>
          <div className="flex gap-3">
            {(["hunter", "seeker"] as const).map((m) => (
              <button
                key={m}
                type="button"
                onClick={() => setMode(m)}
                className={`flex-1 py-3 rounded-lg text-sm border transition-colors ${
                  mode === m
                    ? "border-accent bg-accent/10 text-accent"
                    : "border-border text-text-secondary hover:border-text-muted"
                }`}
              >
                <span className="font-medium">{m === "hunter" ? "Hunter" : "Seeker"}</span>
                <span className="block text-xs mt-0.5 opacity-70">
                  {m === "hunter" ? "Business Outreach" : "Job Hunting"}
                </span>
              </button>
            ))}
          </div>
        </fieldset>

        {/* Name */}
        <Field label="Campaign Name" required>
          <input
            value={name}
            onChange={(e) => setName(e.target.value)}
            placeholder={mode === "hunter" ? "Q2 SaaS outreach" : "Software engineer roles"}
            required
            className="input"
          />
        </Field>

        {/* Autonomy */}
        <fieldset>
          <legend className="text-sm font-medium mb-2">Autonomy Level</legend>
          <div className="flex gap-3">
            {(["copilot", "supervised", "full_auto"] as const).map((a) => (
              <button
                key={a}
                type="button"
                onClick={() => setAutonomy(a)}
                className={`flex-1 py-2 rounded-lg text-xs border transition-colors ${
                  autonomy === a
                    ? "border-accent bg-accent/10 text-accent"
                    : "border-border text-text-secondary hover:border-text-muted"
                }`}
              >
                {a === "copilot"
                  ? "Copilot (approve each)"
                  : a === "supervised"
                    ? "Supervised (watch live)"
                    : "Full Auto"}
              </button>
            ))}
          </div>
        </fieldset>

        {/* Dry run */}
        <label className="flex items-center gap-2 text-sm cursor-pointer">
          <input
            type="checkbox"
            checked={dryRun}
            onChange={(e) => setDryRun(e.target.checked)}
            className="accent-accent"
          />
          Dry run (no emails sent)
        </label>

        {/* Hunter fields */}
        {mode === "hunter" && (
          <div className="space-y-4 border-t border-border pt-4">
            <p className="text-xs text-text-muted uppercase tracking-wider">
              Your Company
            </p>
            <Field label="Company Name" required>
              <input
                value={companyName}
                onChange={(e) => setCompanyName(e.target.value)}
                placeholder="Acme Inc."
                required
                className="input"
              />
            </Field>
            <Field label="Company URL">
              <input
                value={companyUrl}
                onChange={(e) => setCompanyUrl(e.target.value)}
                placeholder="https://yourcompany.com"
                className="input"
              />
            </Field>
            <Field label="Company Description">
              <textarea
                value={companyDesc}
                onChange={(e) => setCompanyDesc(e.target.value)}
                rows={3}
                placeholder="What does your company do? Who do you serve?"
                className="input"
              />
            </Field>
            <p className="text-xs text-text-muted uppercase tracking-wider pt-2">
              Ideal Customer Profile
            </p>
            <div className="grid grid-cols-2 gap-4">
              <Field label="Industry">
                <input
                  value={icpIndustry}
                  onChange={(e) => setIcpIndustry(e.target.value)}
                  placeholder="SaaS, FinTech..."
                  className="input"
                />
              </Field>
              <Field label="Company Size">
                <input
                  value={icpSize}
                  onChange={(e) => setIcpSize(e.target.value)}
                  placeholder="50-200"
                  className="input"
                />
              </Field>
            </div>
            <Field label="Target Roles (comma-separated)">
              <input
                value={icpRoles}
                onChange={(e) => setIcpRoles(e.target.value)}
                placeholder="CTO, VP Engineering, Head of Product"
                className="input"
              />
            </Field>
            <Field label="Keywords (comma-separated)">
              <input
                value={icpKeywords}
                onChange={(e) => setIcpKeywords(e.target.value)}
                placeholder="API, developer tools, B2B"
                className="input"
              />
            </Field>
          </div>
        )}

        {/* Seeker fields */}
        {mode === "seeker" && (
          <div className="space-y-4 border-t border-border pt-4">
            <div className="bg-accent/5 border border-accent/20 rounded-lg p-4">
              <p className="text-sm text-text-secondary">
                ColdPilot will find the right person to contact at each company, research what they are working on right now, and write a personalised email that connects your background directly to their current situation.
              </p>
            </div>

            <Field label="Upload your CV" required>
              <div
                onClick={() => fileRef.current?.click()}
                className="border-2 border-dashed border-border rounded-lg p-6 text-center cursor-pointer hover:border-accent/50 transition-colors"
              >
                <input
                  ref={fileRef}
                  type="file"
                  accept=".pdf,.doc,.docx,.txt"
                  onChange={handleCvUpload}
                  className="hidden"
                />
                {cvUploading ? (
                  <p className="text-sm text-accent animate-pulse">Reading your CV...</p>
                ) : cvFile ? (
                  <div>
                    <p className="text-sm text-accent font-medium">{cvFile.name}</p>
                    <p className="text-xs text-text-muted mt-1">Click to replace</p>
                  </div>
                ) : (
                  <div>
                    <svg className="w-8 h-8 text-text-muted mx-auto mb-2" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
                      <path strokeLinecap="round" strokeLinejoin="round" d="M7 16a4 4 0 01-.88-7.903A5 5 0 1115.9 6L16 6a5 5 0 011 9.9M15 13l-3-3m0 0l-3 3m3-3v12" />
                    </svg>
                    <p className="text-sm text-text-muted">Drop your CV here or click to browse</p>
                    <p className="text-xs text-text-muted mt-1">PDF, DOC, or TXT</p>
                  </div>
                )}
              </div>
            </Field>

            <Field label="Desired Role" required>
              <input
                value={desiredRole}
                onChange={(e) => setDesiredRole(e.target.value)}
                placeholder="e.g. Software Engineer, Data Analyst, Product Manager"
                required
                className="input"
              />
            </Field>

            <Field label="Target Companies (one per line, up to 20)">
              <textarea
                value={targetCompanies}
                onChange={(e) => setTargetCompanies(e.target.value)}
                rows={8}
                placeholder={`Google, google.com, John Doe, john@google.com, Recruiter
Microsoft, microsoft.com, Jane Smith, jane@microsoft.com, HR
Stripe, stripe.com
Vercel
Linear, linear.app, , hiring@linear.app`}
                className="input font-mono text-xs"
              />
              <p className="text-xs text-text-muted mt-1">
                Format: <code className="bg-bg px-1 rounded">Company, domain, Contact Name, email, role</code> — only Company is required.
                {" "}{targetCompanies.split("\n").filter((l) => l.trim()).length}/20 companies
              </p>
            </Field>
          </div>
        )}

        {error && (
          <p className="text-sm text-red bg-red/10 rounded-lg p-3">{error}</p>
        )}

        <button
          type="submit"
          disabled={saving}
          className="w-full bg-accent hover:bg-accent-hover disabled:opacity-50 text-white py-2.5 rounded-lg text-sm font-medium transition-colors"
        >
          {saving ? "Creating..." : "Create Campaign"}
        </button>
      </form>
    </>
  );
}

function Field({
  label,
  required,
  children,
}: {
  label: string;
  required?: boolean;
  children: React.ReactNode;
}) {
  return (
    <label className="block">
      <span className="text-sm text-text-secondary">
        {label}
        {required && <span className="text-red ml-0.5">*</span>}
      </span>
      <div className="mt-1">{children}</div>
    </label>
  );
}
