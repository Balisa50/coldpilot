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

interface ProspectRow {
  company: string;
  domain: string;
  name: string;
  email: string;
  role: string;
}

const EMPTY_ROW: ProspectRow = { company: "", domain: "", name: "", email: "", role: "" };

export default function NewCampaignPage() {
  const router = useRouter();
  const [mode, setMode] = useState<CampaignMode>("seeker");
  const [campaignName, setCampaignName] = useState("");
  const [autonomy, setAutonomy] = useState<AutonomyLevel>("full_auto");
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
  const [prospects, setProspects] = useState<ProspectRow[]>([{ ...EMPTY_ROW }]);
  const fileRef = useRef<HTMLInputElement>(null);

  function updateProspect(index: number, field: keyof ProspectRow, value: string) {
    setProspects((prev) =>
      prev.map((p, i) => (i === index ? { ...p, [field]: value } : p))
    );
  }

  function addProspect() {
    if (prospects.length >= 20) return;
    setProspects((prev) => [...prev, { ...EMPTY_ROW }]);
  }

  function removeProspect(index: number) {
    if (prospects.length <= 1) return;
    setProspects((prev) => prev.filter((_, i) => i !== index));
  }

  async function handleCvUpload(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    if (!file) return;
    setCvFile(file);
    setCvUploading(true);
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
      name: campaignName,
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
          roles: icpRoles.split(",").map((r) => r.trim()).filter(Boolean),
          keywords: icpKeywords.split(",").map((k) => k.trim()).filter(Boolean),
        };
      }
    } else {
      payload.cv_text = cvText;
      payload.desired_role = desiredRole || undefined;
      const validProspects = prospects.filter((p) => p.company.trim());
      if (validProspects.length > 0) {
        payload.target_companies = validProspects.map(
          (p): TargetCompany => ({
            company_name: p.company.trim(),
            company_domain: p.domain.trim() || undefined,
            contact_name: p.name.trim() || undefined,
            contact_email: p.email.trim() || undefined,
            contact_role: p.role.trim() || undefined,
          })
        );
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

  const validCount = prospects.filter((p) => p.company.trim()).length;

  return (
    <>
      <h1 className="text-2xl font-bold mb-6">New Campaign</h1>

      <form
        onSubmit={handleSubmit}
        className="bg-surface rounded-xl border border-border p-6 space-y-6 max-w-3xl"
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
            value={campaignName}
            onChange={(e) => setCampaignName(e.target.value)}
            placeholder={mode === "hunter" ? "Q2 SaaS outreach" : "AI engineer roles"}
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
            <p className="text-xs text-text-muted uppercase tracking-wider">Your Company</p>
            <Field label="Company Name" required>
              <input value={companyName} onChange={(e) => setCompanyName(e.target.value)}
                placeholder="Acme Inc." required className="input" />
            </Field>
            <Field label="Company URL">
              <input value={companyUrl} onChange={(e) => setCompanyUrl(e.target.value)}
                placeholder="https://yourcompany.com" className="input" />
            </Field>
            <Field label="Company Description">
              <textarea value={companyDesc} onChange={(e) => setCompanyDesc(e.target.value)}
                rows={3} placeholder="What does your company do?" className="input" />
            </Field>
            <p className="text-xs text-text-muted uppercase tracking-wider pt-2">Ideal Customer Profile</p>
            <div className="grid grid-cols-2 gap-4">
              <Field label="Industry">
                <input value={icpIndustry} onChange={(e) => setIcpIndustry(e.target.value)}
                  placeholder="SaaS, FinTech..." className="input" />
              </Field>
              <Field label="Company Size">
                <input value={icpSize} onChange={(e) => setIcpSize(e.target.value)}
                  placeholder="50-200" className="input" />
              </Field>
            </div>
            <Field label="Target Roles (comma-separated)">
              <input value={icpRoles} onChange={(e) => setIcpRoles(e.target.value)}
                placeholder="CTO, VP Engineering, Head of Product" className="input" />
            </Field>
            <Field label="Keywords (comma-separated)">
              <input value={icpKeywords} onChange={(e) => setIcpKeywords(e.target.value)}
                placeholder="API, developer tools, B2B" className="input" />
            </Field>
          </div>
        )}

        {/* Seeker fields */}
        {mode === "seeker" && (
          <div className="space-y-4 border-t border-border pt-4">
            <div className="bg-accent/5 border border-accent/20 rounded-lg p-4">
              <p className="text-sm text-text-secondary">
                Add your target companies below. If you already have a contact&apos;s name and email, add them — ColdPilot will skip searching and go straight to researching + writing.
              </p>
            </div>

            <Field label="Upload your CV" required>
              <div
                onClick={() => fileRef.current?.click()}
                className="border-2 border-dashed border-border rounded-lg p-6 text-center cursor-pointer hover:border-accent/50 transition-colors"
              >
                <input ref={fileRef} type="file" accept=".pdf,.doc,.docx,.txt"
                  onChange={handleCvUpload} className="hidden" />
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

            {/* ── Target Companies — proper form fields ── */}
            <div>
              <div className="flex items-center justify-between mb-3">
                <span className="text-sm text-text-secondary">
                  Target Companies
                  <span className="text-text-muted ml-1">({validCount}/20)</span>
                </span>
                {prospects.length < 20 && (
                  <button
                    type="button"
                    onClick={addProspect}
                    className="text-xs text-accent hover:text-accent-hover transition-colors"
                  >
                    + Add Another
                  </button>
                )}
              </div>

              <div className="space-y-3">
                {prospects.map((p, i) => (
                  <div
                    key={i}
                    className="border border-white/10 rounded-lg p-3 space-y-2 relative group"
                  >
                    {/* Remove button */}
                    {prospects.length > 1 && (
                      <button
                        type="button"
                        onClick={() => removeProspect(i)}
                        className="absolute top-2 right-2 text-white/20 hover:text-red text-xs opacity-0 group-hover:opacity-100 transition-opacity"
                        title="Remove"
                      >
                        <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                          <path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" />
                        </svg>
                      </button>
                    )}

                    {/* Row 1: Company + Domain */}
                    <div className="grid grid-cols-2 gap-2">
                      <input
                        value={p.company}
                        onChange={(e) => updateProspect(i, "company", e.target.value)}
                        placeholder="Company name *"
                        className="bg-bg border border-white/10 rounded-lg px-3 py-2 text-sm text-white placeholder:text-white/30 focus:outline-none focus:border-accent/50 transition-colors"
                      />
                      <input
                        value={p.domain}
                        onChange={(e) => updateProspect(i, "domain", e.target.value)}
                        placeholder="Domain (optional)"
                        className="bg-bg border border-white/10 rounded-lg px-3 py-2 text-sm text-white placeholder:text-white/30 focus:outline-none focus:border-accent/50 transition-colors"
                      />
                    </div>

                    {/* Row 2: Contact Name + Email + Role */}
                    <div className="grid grid-cols-3 gap-2">
                      <input
                        value={p.name}
                        onChange={(e) => updateProspect(i, "name", e.target.value)}
                        placeholder="Contact name"
                        className="bg-bg border border-white/10 rounded-lg px-3 py-2 text-sm text-white placeholder:text-white/30 focus:outline-none focus:border-accent/50 transition-colors"
                      />
                      <input
                        value={p.email}
                        onChange={(e) => updateProspect(i, "email", e.target.value)}
                        placeholder="Contact email"
                        type="email"
                        className="bg-bg border border-white/10 rounded-lg px-3 py-2 text-sm text-white placeholder:text-white/30 focus:outline-none focus:border-accent/50 transition-colors"
                      />
                      <input
                        value={p.role}
                        onChange={(e) => updateProspect(i, "role", e.target.value)}
                        placeholder="Role/title"
                        className="bg-bg border border-white/10 rounded-lg px-3 py-2 text-sm text-white placeholder:text-white/30 focus:outline-none focus:border-accent/50 transition-colors"
                      />
                    </div>
                  </div>
                ))}
              </div>

              {prospects.length < 20 && (
                <button
                  type="button"
                  onClick={addProspect}
                  className="mt-3 w-full border border-dashed border-white/10 hover:border-accent/40 rounded-lg py-2.5 text-xs text-white/40 hover:text-accent transition-colors"
                >
                  + Add Another Company
                </button>
              )}
            </div>
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
