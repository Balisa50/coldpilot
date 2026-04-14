"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { api } from "../../lib/api";

export default function AddProspectForm({ campaignId }: { campaignId: string }) {
  const router = useRouter();
  const [open, setOpen] = useState(false);
  const [mode, setMode] = useState<"single" | "bulk">("single");
  const [saving, setSaving] = useState(false);

  // Single prospect fields
  const [companyName, setCompanyName] = useState("");
  const [companyDomain, setCompanyDomain] = useState("");
  const [contactName, setContactName] = useState("");
  const [contactEmail, setContactEmail] = useState("");
  const [contactRole, setContactRole] = useState("");

  // Bulk paste
  const [bulkText, setBulkText] = useState("");

  async function handleSingleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!companyName.trim()) return;
    setSaving(true);
    try {
      await api.createProspect(campaignId, {
        company_name: companyName.trim(),
        company_domain: companyDomain.trim() || undefined,
        contact_name: contactName.trim() || undefined,
        contact_email: contactEmail.trim() || undefined,
        contact_role: contactRole.trim() || undefined,
      });
      setCompanyName("");
      setCompanyDomain("");
      setContactName("");
      setContactEmail("");
      setContactRole("");
      router.refresh();
    } catch {
      // ignore
    }
    setSaving(false);
  }

  async function handleBulkSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!bulkText.trim()) return;
    setSaving(true);
    try {
      const lines = bulkText
        .split("\n")
        .map((l) => l.trim())
        .filter(Boolean);

      for (const line of lines) {
        const parts = line.split(",").map((s) => s.trim());
        const [company, domain, name, email, role] = parts;
        if (!company) continue;
        await api.createProspect(campaignId, {
          company_name: company,
          company_domain: domain || undefined,
          contact_name: name || undefined,
          contact_email: email || undefined,
          contact_role: role || undefined,
        });
      }
      setBulkText("");
      setOpen(false);
      router.refresh();
    } catch {
      // ignore
    }
    setSaving(false);
  }

  if (!open) {
    return (
      <button
        onClick={() => setOpen(true)}
        className="text-xs text-accent hover:text-accent-hover mb-4 transition-colors"
      >
        + Add Prospect
      </button>
    );
  }

  return (
    <div className="bg-surface rounded-xl border border-border p-4 mb-6">
      {/* Mode tabs */}
      <div className="flex gap-2 mb-4">
        <button
          type="button"
          onClick={() => setMode("single")}
          className={`text-xs px-3 py-1.5 rounded-lg transition-colors ${
            mode === "single"
              ? "bg-accent/10 text-accent border border-accent/30"
              : "text-text-muted hover:text-text-secondary"
          }`}
        >
          Single
        </button>
        <button
          type="button"
          onClick={() => setMode("bulk")}
          className={`text-xs px-3 py-1.5 rounded-lg transition-colors ${
            mode === "bulk"
              ? "bg-accent/10 text-accent border border-accent/30"
              : "text-text-muted hover:text-text-secondary"
          }`}
        >
          Bulk Paste
        </button>
        <div className="flex-1" />
        <button
          type="button"
          onClick={() => setOpen(false)}
          className="text-text-muted hover:text-text-secondary text-xs"
        >
          Cancel
        </button>
      </div>

      {mode === "single" ? (
        <form onSubmit={handleSingleSubmit} className="space-y-3">
          <div className="grid grid-cols-2 gap-3">
            <label>
              <span className="text-xs text-text-muted">Company *</span>
              <input
                value={companyName}
                onChange={(e) => setCompanyName(e.target.value)}
                required
                className="input mt-1"
                placeholder="Acme Inc"
              />
            </label>
            <label>
              <span className="text-xs text-text-muted">Domain</span>
              <input
                value={companyDomain}
                onChange={(e) => setCompanyDomain(e.target.value)}
                className="input mt-1"
                placeholder="acme.com"
              />
            </label>
          </div>
          <div className="grid grid-cols-3 gap-3">
            <label>
              <span className="text-xs text-text-muted">Contact Name</span>
              <input
                value={contactName}
                onChange={(e) => setContactName(e.target.value)}
                className="input mt-1"
                placeholder="Jane Smith"
              />
            </label>
            <label>
              <span className="text-xs text-text-muted">Contact Email</span>
              <input
                value={contactEmail}
                onChange={(e) => setContactEmail(e.target.value)}
                type="email"
                className="input mt-1"
                placeholder="jane@acme.com"
              />
            </label>
            <label>
              <span className="text-xs text-text-muted">Role</span>
              <input
                value={contactRole}
                onChange={(e) => setContactRole(e.target.value)}
                className="input mt-1"
                placeholder="VP Engineering"
              />
            </label>
          </div>
          <div className="flex gap-2 pt-1">
            <button
              type="submit"
              disabled={saving}
              className="bg-accent hover:bg-accent-hover disabled:opacity-50 text-white text-xs px-4 py-2 rounded-lg transition-colors"
            >
              {saving ? "Adding..." : "Add Prospect"}
            </button>
            <p className="text-xs text-text-muted self-center">
              If you have the email, add it — we&apos;ll skip contact finding and go straight to research + email writing.
            </p>
          </div>
        </form>
      ) : (
        <form onSubmit={handleBulkSubmit} className="space-y-3">
          <p className="text-xs text-text-muted">
            One prospect per line: <code className="bg-bg px-1 rounded">Company, domain, Contact Name, email, role</code>
          </p>
          <textarea
            value={bulkText}
            onChange={(e) => setBulkText(e.target.value)}
            rows={8}
            className="input font-mono text-xs"
            placeholder={`Google, google.com, John Doe, john@google.com, Recruiter
Microsoft, microsoft.com, Jane Smith, jane@microsoft.com, HR Manager
Stripe, stripe.com
Meta, meta.com, , hiring@meta.com`}
          />
          <div className="flex items-center gap-3">
            <button
              type="submit"
              disabled={saving}
              className="bg-accent hover:bg-accent-hover disabled:opacity-50 text-white text-xs px-4 py-2 rounded-lg transition-colors"
            >
              {saving
                ? "Adding..."
                : `Add ${bulkText.split("\n").filter((l) => l.trim()).length} Prospects`}
            </button>
            <p className="text-xs text-text-muted">
              Only Company is required. Leave fields empty with commas to skip them.
            </p>
          </div>
        </form>
      )}
    </div>
  );
}
