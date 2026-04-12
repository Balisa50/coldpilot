"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { api } from "../../lib/api";
import type { Campaign } from "../../lib/types";

export default function CampaignActions({ campaign }: { campaign: Campaign }) {
  const router = useRouter();
  const [loading, setLoading] = useState<string | null>(null);

  async function handleStart() {
    setLoading("start");
    try {
      await api.startCampaign(campaign.id);
      router.refresh();
    } catch {
      // ignore
    }
    setLoading(null);
  }

  async function handlePause() {
    setLoading("pause");
    try {
      await api.pauseCampaign(campaign.id);
      router.refresh();
    } catch {
      // ignore
    }
    setLoading(null);
  }

  async function handleDelete() {
    if (!confirm("Delete this campaign? This cannot be undone.")) return;
    setLoading("delete");
    try {
      await api.deleteCampaign(campaign.id);
      router.push("/campaigns");
    } catch {
      setLoading(null);
    }
  }

  return (
    <div className="flex gap-2">
      {(campaign.status === "draft" || campaign.status === "paused") && (
        <button
          onClick={handleStart}
          disabled={loading === "start"}
          className="text-xs bg-green/20 text-green hover:bg-green/30 px-3 py-1.5 rounded-lg transition-colors disabled:opacity-50"
        >
          {loading === "start" ? "Starting..." : "Start"}
        </button>
      )}
      {campaign.status === "active" && (
        <button
          onClick={handlePause}
          disabled={loading === "pause"}
          className="text-xs bg-amber/20 text-amber hover:bg-amber/30 px-3 py-1.5 rounded-lg transition-colors disabled:opacity-50"
        >
          {loading === "pause" ? "Pausing..." : "Pause"}
        </button>
      )}
      <button
        onClick={handleDelete}
        disabled={loading === "delete"}
        className="text-xs bg-red/20 text-red hover:bg-red/30 px-3 py-1.5 rounded-lg transition-colors disabled:opacity-50"
      >
        {loading === "delete" ? "Deleting..." : "Delete"}
      </button>
    </div>
  );
}
