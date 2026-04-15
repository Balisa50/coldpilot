"use client";

import { useState, useRef, useEffect, useCallback } from "react";
import { api } from "./lib/api";
import type {
  CampaignMode,
  AutonomyLevel,
  CampaignCreatePayload,
  TargetCompany,
  PipelineEvent,
  Email,
} from "./lib/types";

// ── Prospect Row type ──
interface ProspectRow {
  company: string;
  domain: string;
  name: string;
  email: string;
  role: string;
}
const EMPTY_ROW: ProspectRow = { company: "", domain: "", name: "", email: "", role: "" };

// ── Feed item for live activity ──
interface FeedItem {
  id: number;
  ts: string;
  text: string;
  type: "info" | "success" | "warn" | "action" | "error";
}

export default function NewCampaignPage() {
  // ── Form state ──
  const [mode, setMode] = useState<CampaignMode>("hunter");
  const [autonomy, setAutonomy] = useState<AutonomyLevel>("copilot");
  const [dryRun, setDryRun] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");

  // Hunter
  const [companyName, setCompanyName] = useState("");
  const [companyDesc, setCompanyDesc] = useState("");
  const [targetIndustry, setTargetIndustry] = useState("");
  const [targetJobTitle, setTargetJobTitle] = useState("");

  // Seeker
  const [cvFile, setCvFile] = useState<File | null>(null);
  const [cvText, setCvText] = useState("");
  const [cvUploading, setCvUploading] = useState(false);
  const [desiredRole, setDesiredRole] = useState("");
  const [prospects, setProspects] = useState<ProspectRow[]>([{ ...EMPTY_ROW }]);
  const fileRef = useRef<HTMLInputElement>(null);

  // ── Live feed state ──
  const [launched, setLaunched] = useState(false);
  const [campaignId, setCampaignId] = useState<string | null>(null);
  const [feed, setFeed] = useState<FeedItem[]>([]);
  const [streamDone, setStreamDone] = useState(false);
  const [pendingEmail, setPendingEmail] = useState<Email | null>(null);
  const [editingBody, setEditingBody] = useState("");
  const [approving, setApproving] = useState(false);
  const feedEndRef = useRef<HTMLDivElement>(null);
  const feedIdRef = useRef(0);

  // Auto-scroll feed
  useEffect(() => {
    feedEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [feed]);

  // ── Prospect helpers ──
  function updateProspect(index: number, field: keyof ProspectRow, value: string) {
    setProspects((prev) => prev.map((p, i) => (i === index ? { ...p, [field]: value } : p)));
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
      setCvText("[CV uploaded]");
    }
    setCvUploading(false);
  }

  // ── Add feed item ──
  const addFeed = useCallback(
    (text: string, type: FeedItem["type"] = "info") => {
      feedIdRef.current += 1;
      const item: FeedItem = {
        id: feedIdRef.current,
        ts: new Date().toLocaleTimeString(),
        text,
        type,
      };
      setFeed((prev) => [...prev, item]);
    },
    []
  );

  // ── SSE listener ──
  useEffect(() => {
    if (!campaignId || streamDone) return;

    const url = api.streamUrl(campaignId);
    const es = new EventSource(url);

    es.onmessage = (ev) => {
      try {
        const data: PipelineEvent = JSON.parse(ev.data);
        const event = data.event;

        switch (event) {
          case "finding_contact":
            addFeed(`Finding contact at ${data.company_name || "company"}...`, "info");
            break;
          case "contact_found":
            addFeed(
              `Found: ${data.contact_name || "Contact"}, ${data.contact_role || "Role"} -- ${data.contact_email || ""}`,
              "success"
            );
            break;
          case "researching":
            addFeed(`Researching ${data.company_name || "company"}...`, "info");
            break;
          case "writing_email":
            addFeed("Writing personalised email...", "info");
            break;
          case "email_drafted":
            if (autonomy === "copilot" && data.email_id) {
              addFeed("Email drafted -- awaiting your approval", "action");
              api.getEmail(data.email_id as string).then((email) => {
                setPendingEmail(email);
                setEditingBody(email.body_text);
              }).catch(() => {});
            } else {
              addFeed("Email drafted", "info");
            }
            break;
          case "email_sent":
            addFeed(`Email sent to ${data.contact_email || "contact"}`, "success");
            break;
          case "dry_run_skip":
            addFeed("Dry run -- email skipped", "warn");
            break;
          case "email_approved":
            addFeed("Email approved", "success");
            break;
          case "prospect_failed":
            addFeed(`Failed: ${data.detail || "unknown error"}`, "error");
            break;
          case "campaign_complete":
            addFeed("Campaign complete!", "success");
            setStreamDone(true);
            break;
          case "error":
            addFeed(`Error: ${data.detail || data.message || "unknown"}`, "error");
            break;
          default:
            addFeed(`${event}: ${data.detail || JSON.stringify(data)}`, "info");
        }
      } catch {
        // ignore parse errors
      }
    };

    es.onerror = () => {
      addFeed("Stream disconnected", "warn");
      setStreamDone(true);
      es.close();
    };

    return () => es.close();
  }, [campaignId, streamDone, autonomy, addFeed]);

  // ── Launch ──
  async function handleLaunch(e: React.FormEvent) {
    e.preventDefault();
    setSaving(true);
    setError("");

    const campaignName =
      mode === "hunter"
        ? `${companyName || "Hunter"} outreach`
        : `${desiredRole || "Seeker"} campaign`;

    const payload: CampaignCreatePayload = {
      mode,
      name: campaignName,
      autonomy,
      dry_run: dryRun,
    };

    if (mode === "hunter") {
      payload.company_name = companyName;
      payload.company_description = companyDesc || undefined;
      if (targetIndustry || targetJobTitle) {
        payload.ideal_customer_profile = {
          industry: targetIndustry,
          company_size: "",
          roles: targetJobTitle ? [targetJobTitle] : [],
          keywords: [],
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
      setCampaignId(campaign.id);
      addFeed("Campaign created. Starting...", "info");

      await api.startCampaign(campaign.id);
      addFeed("Campaign started -- connecting to live stream...", "success");

      setLaunched(true);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to launch");
    }
    setSaving(false);
  }

  // ── Approve / Reject email ──
  async function handleApprove() {
    if (!pendingEmail) return;
    setApproving(true);
    try {
      await api.approveEmail(pendingEmail.id);
      addFeed("Email approved -- sending...", "success");
      setPendingEmail(null);
    } catch {
      addFeed("Failed to approve email", "error");
    }
    setApproving(false);
  }

  async function handleReject() {
    if (!pendingEmail) return;
    setApproving(true);
    try {
      await api.rejectEmail(pendingEmail.id, "Rejected by user");
      addFeed("Email rejected", "warn");
      setPendingEmail(null);
    } catch {
      addFeed("Failed to reject email", "error");
    }
    setApproving(false);
  }

  function handleNewCampaign() {
    setLaunched(false);
    setCampaignId(null);
    setFeed([]);
    setStreamDone(false);
    setPendingEmail(null);
    setError("");
    setSaving(false);
  }

  const validCount = prospects.filter((p) => p.company.trim()).length;

  // ────────────────────────────────────────
  // LIVE FEED VIEW (after launch)
  // ────────────────────────────────────────
  if (launched) {
    return (
      <div className="max-w-3xl mx-auto">
        <div className="flex items-center justify-between mb-6">
          <h1 className="text-2xl font-bold">Live Campaign</h1>
          {streamDone && (
            <button
              onClick={handleNewCampaign}
              className="text-sm bg-accent hover:bg-accent-hover text-white px-4 py-2 rounded-lg transition-colors"
            >
              New Campaign
            </button>
          )}
        </div>

        {/* Feed */}
        <div className="bg-surface rounded-xl border border-border p-5 min-h-[400px] max-h-[600px] overflow-y-auto">
          {feed.length === 0 && (
            <div className="flex items-center justify-center h-40">
              <div className="text-center">
                <div className="w-8 h-8 border-3 border-border border-t-accent rounded-full animate-spin mx-auto mb-3" />
                <p className="text-sm text-text-muted">Connecting to stream...</p>
              </div>
            </div>
          )}

          <div className="space-y-2">
            {feed.map((item) => (
              <div
                key={item.id}
                className={`flex items-start gap-3 text-sm py-2 px-3 rounded-lg ${
                  item.type === "success"
                    ? "bg-green/5 text-green"
                    : item.type === "warn"
                      ? "bg-amber/5 text-amber"
                      : item.type === "error"
                        ? "bg-red/5 text-red"
                        : item.type === "action"
                          ? "bg-accent/5 text-accent"
                          : "text-text-secondary"
                }`}
              >
                <span className="text-text-muted text-xs shrink-0 mt-0.5 font-mono">
                  {item.ts}
                </span>
                <span
                  className={`w-2 h-2 rounded-full shrink-0 mt-1.5 ${
                    item.type === "success"
                      ? "bg-green"
                      : item.type === "warn"
                        ? "bg-amber"
                        : item.type === "error"
                          ? "bg-red"
                          : item.type === "action"
                            ? "bg-accent"
                            : "bg-text-muted"
                  }`}
                />
                <span>{item.text}</span>
              </div>
            ))}
            <div ref={feedEndRef} />
          </div>

          {/* Stream active indicator */}
          {!streamDone && feed.length > 0 && (
            <div className="flex items-center gap-2 mt-4 pt-3 border-t border-border">
              <div className="w-2 h-2 bg-green rounded-full animate-pulse" />
              <span className="text-xs text-text-muted">Stream active</span>
            </div>
          )}

          {streamDone && (
            <div className="mt-4 pt-3 border-t border-border text-center">
              <p className="text-sm text-text-muted">Campaign finished</p>
            </div>
          )}
        </div>

        {/* Pending email approval (copilot) */}
        {pendingEmail && (
          <div className="mt-6 bg-surface rounded-xl border border-accent/30 p-5">
            <h3 className="text-sm font-medium text-accent mb-3">Review Email</h3>
            <div className="mb-3">
              <p className="text-xs text-text-muted mb-1">Subject</p>
              <p className="text-sm text-text-primary">{pendingEmail.subject}</p>
            </div>
            <div className="mb-4">
              <p className="text-xs text-text-muted mb-1">Body</p>
              <textarea
                value={editingBody}
                onChange={(e) => setEditingBody(e.target.value)}
                rows={8}
                className="input font-mono text-xs"
              />
            </div>
            <div className="flex gap-3">
              <button
                onClick={handleApprove}
                disabled={approving}
                className="bg-green hover:bg-green/80 disabled:opacity-50 text-white text-sm px-5 py-2.5 rounded-lg transition-colors"
              >
                {approving ? "..." : "Approve & Send"}
              </button>
              <button
                onClick={handleReject}
                disabled={approving}
                className="bg-surface-elevated hover:bg-border text-text-secondary text-sm px-5 py-2.5 rounded-lg border border-border transition-colors"
              >
                Reject
              </button>
            </div>
          </div>
        )}
      </div>
    );
  }

  // ────────────────────────────────────────
  // CAMPAIGN FORM
  // ────────────────────────────────────────
  return (
    <div className="max-w-3xl mx-auto">
      <h1 className="text-2xl font-bold mb-6">New Campaign</h1>

      <form onSubmit={handleLaunch} className="space-y-6">
        {/* Mode toggle */}
        <div className="grid grid-cols-2 gap-4">
          {(["hunter", "seeker"] as const).map((m) => (
            <button
              key={m}
              type="button"
              onClick={() => setMode(m)}
              className={`py-6 rounded-xl text-center border-2 transition-all ${
                mode === m
                  ? "border-accent bg-accent/10"
                  : "border-border bg-surface hover:border-text-muted"
              }`}
            >
              <span className={`text-lg font-semibold ${mode === m ? "text-accent" : "text-text-primary"}`}>
                {m === "hunter" ? "Hunter Mode" : "Seeker Mode"}
              </span>
              <span className="block text-xs text-text-muted mt-1">
                {m === "hunter" ? "Find leads for your business" : "Find jobs for yourself"}
              </span>
            </button>
          ))}
        </div>

        {/* Hunter fields */}
        {mode === "hunter" && (
          <div className="bg-surface rounded-xl border border-border p-6 space-y-4">
            <p className="text-xs text-text-muted uppercase tracking-wider font-medium">Your Company</p>

            <label className="block">
              <span className="text-sm text-text-secondary">
                Company Name <span className="text-red">*</span>
              </span>
              <input
                value={companyName}
                onChange={(e) => setCompanyName(e.target.value)}
                placeholder="Acme Inc."
                required
                className="input mt-1"
              />
            </label>

            <label className="block">
              <span className="text-sm text-text-secondary">Company Description</span>
              <textarea
                value={companyDesc}
                onChange={(e) => setCompanyDesc(e.target.value)}
                rows={3}
                placeholder="What does your company do? What problem do you solve?"
                className="input mt-1"
              />
            </label>

            <label className="block">
              <span className="text-sm text-text-secondary">Target Industry</span>
              <input
                value={targetIndustry}
                onChange={(e) => setTargetIndustry(e.target.value)}
                placeholder="SaaS, FinTech, E-commerce..."
                className="input mt-1"
              />
            </label>

            <label className="block">
              <span className="text-sm text-text-secondary">Target Job Title</span>
              <input
                value={targetJobTitle}
                onChange={(e) => setTargetJobTitle(e.target.value)}
                placeholder="CTO, VP Engineering, Head of Product..."
                className="input mt-1"
              />
            </label>
          </div>
        )}

        {/* Seeker fields */}
        {mode === "seeker" && (
          <div className="bg-surface rounded-xl border border-border p-6 space-y-5">
            {/* CV Upload */}
            <div>
              <span className="text-sm text-text-secondary block mb-1">
                Upload your CV <span className="text-red">*</span>
              </span>
              <div
                onClick={() => fileRef.current?.click()}
                className="border-2 border-dashed border-border rounded-xl p-8 text-center cursor-pointer hover:border-accent/50 transition-colors"
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
                    <svg
                      className="w-8 h-8 text-text-muted mx-auto mb-2"
                      fill="none"
                      viewBox="0 0 24 24"
                      stroke="currentColor"
                      strokeWidth={1.5}
                    >
                      <path
                        strokeLinecap="round"
                        strokeLinejoin="round"
                        d="M7 16a4 4 0 01-.88-7.903A5 5 0 1115.9 6L16 6a5 5 0 011 9.9M15 13l-3-3m0 0l-3 3m3-3v12"
                      />
                    </svg>
                    <p className="text-sm text-text-muted">Drop your CV here or click to browse</p>
                    <p className="text-xs text-text-muted mt-1">PDF, DOC, or TXT</p>
                  </div>
                )}
              </div>
            </div>

            {/* Target Companies */}
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
                    className="border border-border rounded-lg p-3 space-y-2 relative group"
                  >
                    {prospects.length > 1 && (
                      <button
                        type="button"
                        onClick={() => removeProspect(i)}
                        className="absolute top-2 right-2 text-text-muted hover:text-red text-xs opacity-0 group-hover:opacity-100 transition-opacity"
                        title="Remove"
                      >
                        <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                          <path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" />
                        </svg>
                      </button>
                    )}

                    <div className="grid grid-cols-2 gap-2">
                      <input
                        value={p.company}
                        onChange={(e) => updateProspect(i, "company", e.target.value)}
                        placeholder="Company name *"
                        className="input"
                      />
                      <input
                        value={p.domain}
                        onChange={(e) => updateProspect(i, "domain", e.target.value)}
                        placeholder="Domain (optional)"
                        className="input"
                      />
                    </div>

                    <div className="grid grid-cols-3 gap-2">
                      <input
                        value={p.name}
                        onChange={(e) => updateProspect(i, "name", e.target.value)}
                        placeholder="Contact name"
                        className="input"
                      />
                      <input
                        value={p.email}
                        onChange={(e) => updateProspect(i, "email", e.target.value)}
                        placeholder="Contact email"
                        type="email"
                        className="input"
                      />
                      <input
                        value={p.role}
                        onChange={(e) => updateProspect(i, "role", e.target.value)}
                        placeholder="Role/title"
                        className="input"
                      />
                    </div>
                  </div>
                ))}
              </div>

              {prospects.length < 20 && (
                <button
                  type="button"
                  onClick={addProspect}
                  className="mt-3 w-full border border-dashed border-border hover:border-accent/40 rounded-lg py-2.5 text-xs text-text-muted hover:text-accent transition-colors"
                >
                  + Add Another Company
                </button>
              )}
            </div>

            {/* Desired Role */}
            <label className="block">
              <span className="text-sm text-text-secondary">
                Desired Role <span className="text-red">*</span>
              </span>
              <input
                value={desiredRole}
                onChange={(e) => setDesiredRole(e.target.value)}
                placeholder="e.g. Software Engineer, Data Analyst, Product Manager"
                required
                className="input mt-1"
              />
            </label>
          </div>
        )}

        {/* Autonomy Level */}
        <div>
          <p className="text-sm text-text-secondary mb-3">Autonomy Level</p>
          <div className="grid grid-cols-3 gap-3">
            {(
              [
                {
                  key: "copilot" as const,
                  title: "Copilot",
                  desc: "Approve each email before sending",
                },
                {
                  key: "supervised" as const,
                  title: "Supervised",
                  desc: "Watch the agent work in real-time",
                },
                {
                  key: "full_auto" as const,
                  title: "Full Auto",
                  desc: "Agent handles everything",
                },
              ] as const
            ).map((a) => (
              <button
                key={a.key}
                type="button"
                onClick={() => setAutonomy(a.key)}
                className={`p-4 rounded-xl border-2 text-left transition-all ${
                  autonomy === a.key
                    ? "border-accent bg-accent/10"
                    : "border-border bg-surface hover:border-text-muted"
                }`}
              >
                <span
                  className={`text-sm font-semibold block ${
                    autonomy === a.key ? "text-accent" : "text-text-primary"
                  }`}
                >
                  {a.title}
                </span>
                <span className="text-xs text-text-muted mt-1 block">{a.desc}</span>
              </button>
            ))}
          </div>
        </div>

        {/* Dry Run */}
        <label className="flex items-center gap-3 text-sm cursor-pointer select-none bg-surface rounded-xl border border-border p-4">
          <input
            type="checkbox"
            checked={dryRun}
            onChange={(e) => setDryRun(e.target.checked)}
            className="accent-accent w-4 h-4"
          />
          <div>
            <span className="text-text-primary font-medium">Dry Run</span>
            <span className="block text-xs text-text-muted mt-0.5">
              Simulate the campaign without sending any emails
            </span>
          </div>
        </label>

        {/* Error */}
        {error && <p className="text-sm text-red bg-red/10 rounded-lg p-3">{error}</p>}

        {/* Launch */}
        <button
          type="submit"
          disabled={saving}
          className="w-full bg-accent hover:bg-accent-hover disabled:opacity-50 text-white py-3 rounded-xl text-sm font-semibold transition-colors"
        >
          {saving ? "Launching..." : "Launch Campaign"}
        </button>
      </form>
    </div>
  );
}
