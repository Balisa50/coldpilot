"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { api } from "../../lib/api";

export default function AddProspectForm({ campaignId }: { campaignId: string }) {
  const router = useRouter();
  const [open, setOpen] = useState(false);
  const [companyName, setCompanyName] = useState("");
  const [companyDomain, setCompanyDomain] = useState("");
  const [saving, setSaving] = useState(false);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!companyName.trim()) return;
    setSaving(true);
    try {
      await api.createProspect(campaignId, {
        company_name: companyName.trim(),
        company_domain: companyDomain.trim() || undefined,
      });
      setCompanyName("");
      setCompanyDomain("");
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
    <form
      onSubmit={handleSubmit}
      className="bg-surface rounded-xl border border-border p-4 mb-6 flex gap-3 items-end"
    >
      <label className="flex-1">
        <span className="text-xs text-text-muted">Company Name *</span>
        <input
          value={companyName}
          onChange={(e) => setCompanyName(e.target.value)}
          required
          className="input mt-1"
          placeholder="Acme Inc"
        />
      </label>
      <label className="flex-1">
        <span className="text-xs text-text-muted">Domain (optional)</span>
        <input
          value={companyDomain}
          onChange={(e) => setCompanyDomain(e.target.value)}
          className="input mt-1"
          placeholder="acme.com"
        />
      </label>
      <button
        type="submit"
        disabled={saving}
        className="bg-accent hover:bg-accent-hover disabled:opacity-50 text-white text-xs px-4 py-2 rounded-lg transition-colors h-9"
      >
        {saving ? "Adding..." : "Add"}
      </button>
      <button
        type="button"
        onClick={() => setOpen(false)}
        className="text-text-muted hover:text-text-secondary text-xs px-2 py-2 h-9"
      >
        Cancel
      </button>
    </form>
  );
}
