"use client";

import { CheckCircle2, Loader2, Plus, Save } from "lucide-react";
import { useState } from "react";

import type { AgentCode, SavedLocation, Workspace } from "@/lib/api/types";

export interface AnalysisConfig {
  title: string;
  workspaceId: string;
  startDate: string;
  endDate: string;
  agents: AgentCode[];
}

export const AGENT_OPTIONS: { code: AgentCode; label: string; hint: string }[] = [
  { code: "agri", label: "Agriculture", hint: "Crops, vegetation & land use" },
  { code: "aqua", label: "Aqua", hint: "Water bodies, rainfall & moisture" },
  { code: "weather", label: "Weather", hint: "Temperature, winds & climate" },
  { code: "change", label: "Change", hint: "Change detection over time" },
];

interface AnalysisConfigPanelProps {
  config: AnalysisConfig;
  onChange: (partial: Partial<AnalysisConfig>) => void;
  onSave: () => void;
  onNew: () => void;
  onUseSavedLocation: (location: SavedLocation | null) => void;
  workspaces: Workspace[];
  savedLocations: SavedLocation[];
  canSave: boolean;
  saving: boolean;
  saveState: "idle" | "saved" | "error";
  saveError: string | null;
  canCancelSave: boolean;
}

export function AnalysisConfigPanel({
  config,
  onChange,
  onSave,
  onNew,
  onUseSavedLocation,
  workspaces,
  savedLocations,
  canSave,
  saving,
  saveState,
  saveError,
  canCancelSave,
}: AnalysisConfigPanelProps) {
  const [pickedSavedLocation, setPickedSavedLocation] = useState("");

  function handleWorkspace(value: string) {
    onChange({ workspaceId: value });
    // Reuse the workspace's locations for the picker.
    onUseSavedLocation(null);
  }

  function handleSavedLocation(value: string) {
    setPickedSavedLocation(value);
    const location = savedLocations.find((item) => item.id === Number(value)) ?? null;
    onUseSavedLocation(location);
  }

  function toggleAgent(code: AgentCode) {
    const agents = config.agents.includes(code)
      ? config.agents.filter((item) => item !== code)
      : [...config.agents, code];
    onChange({ agents });
  }

  return (
    <div className="space-y-4">
      <div>
        <label htmlFor="analysis-title" className="mb-1 block text-xs font-medium text-zinc-600">
          Title
        </label>
        <input
          id="analysis-title"
          type="text"
          value={config.title}
          onChange={(event) => onChange({ title: event.target.value })}
          placeholder="e.g. Rice field health check"
          className="w-full rounded-lg border border-zinc-300 bg-white px-3 py-2 text-sm text-zinc-900 outline-none focus:border-brand-500"
        />
      </div>

      <div className="grid grid-cols-2 gap-3">
        <div>
          <label htmlFor="analysis-start" className="mb-1 block text-xs font-medium text-zinc-600">
            Start date
          </label>
          <input
            id="analysis-start"
            type="date"
            value={config.startDate}
            onChange={(event) => onChange({ startDate: event.target.value })}
            className="w-full rounded-lg border border-zinc-300 bg-white px-3 py-2 text-sm text-zinc-900 outline-none focus:border-brand-500"
          />
        </div>
        <div>
          <label htmlFor="analysis-end" className="mb-1 block text-xs font-medium text-zinc-600">
            End date
          </label>
          <input
            id="analysis-end"
            type="date"
            value={config.endDate}
            onChange={(event) => onChange({ endDate: event.target.value })}
            className="w-full rounded-lg border border-zinc-300 bg-white px-3 py-2 text-sm text-zinc-900 outline-none focus:border-brand-500"
          />
        </div>
      </div>

      <div>
        <label htmlFor="analysis-workspace" className="mb-1 block text-xs font-medium text-zinc-600">
          Workspace
        </label>
        <select
          id="analysis-workspace"
          value={config.workspaceId}
          onChange={(event) => handleWorkspace(event.target.value)}
          className="w-full rounded-lg border border-zinc-300 bg-white px-3 py-2 text-sm text-zinc-900 outline-none focus:border-brand-500"
        >
          <option value="">No workspace (private)</option>
          {workspaces.map((workspace) => (
            <option key={workspace.id} value={String(workspace.id)}>
              {workspace.name}
            </option>
          ))}
        </select>
      </div>

      <div>
        <label htmlFor="analysis-location" className="mb-1 block text-xs font-medium text-zinc-600">
          Reuse a saved location as the AOI
        </label>
        <select
          id="analysis-location"
          value={pickedSavedLocation}
          onChange={(event) => handleSavedLocation(event.target.value)}
          className="w-full rounded-lg border border-zinc-300 bg-white px-3 py-2 text-sm text-zinc-900 outline-none focus:border-brand-500"
        >
          <option value="">Select a saved location…</option>
          {savedLocations.map((location) => (
            <option key={location.id} value={String(location.id)}>
              {location.name}
            </option>
          ))}
        </select>
      </div>

      <fieldset>
        <legend className="mb-1 block text-xs font-medium text-zinc-600">Agents to include</legend>
        <div className="space-y-2">
          {AGENT_OPTIONS.map((option) => {
            const checked = config.agents.includes(option.code);
            return (
              <label
                key={option.code}
                className="flex cursor-pointer items-start gap-2.5 rounded-lg border border-zinc-200 px-3 py-2.5 transition hover:border-brand-300"
              >
                <input
                  type="checkbox"
                  checked={checked}
                  onChange={() => toggleAgent(option.code)}
                  className="mt-0.5 h-4 w-4 rounded border-zinc-300 text-brand-600 focus:ring-brand-500"
                />
                <span>
                  <span className="block text-sm font-medium text-zinc-800">{option.label}</span>
                  <span className="block text-xs text-zinc-500">{option.hint}</span>
                </span>
              </label>
            );
          })}
        </div>
      </fieldset>

      <div className="flex items-center gap-2 pt-1">
        <button
          type="button"
          onClick={onSave}
          disabled={!canSave || saving}
          className="inline-flex items-center gap-1.5 rounded-lg bg-brand-600 px-4 py-2 text-sm font-medium text-white transition enabled:hover:bg-brand-700 disabled:opacity-40"
        >
          {saving ? (
            <Loader2 className="h-4 w-4 animate-spin" />
          ) : (
            <Save className="h-4 w-4" />
          )}
          Save draft
        </button>
        {canCancelSave && (
          <button
            type="button"
            onClick={onNew}
            className="inline-flex items-center gap-1.5 rounded-lg border border-zinc-300 bg-white px-3 py-2 text-sm font-medium text-zinc-700 transition hover:bg-zinc-50"
          >
            <Plus className="h-4 w-4" />
            New
          </button>
        )}
      </div>

      {saveState === "saved" && (
        <p className="inline-flex items-center gap-1.5 rounded-lg bg-emerald-50 px-3 py-2 text-xs font-medium text-emerald-700">
          <CheckCircle2 className="h-4 w-4" /> Draft saved. You can reopen it from the session list.
        </p>
      )}
      {saveState === "error" && saveError && (
        <p className="rounded-lg bg-red-50 px-3 py-2 text-xs text-red-700" role="alert">
          {saveError}
        </p>
      )}
      {!config.workspaceId && (
        <p className="text-[11px] text-zinc-400">
          Without a workspace the session is private to you.
        </p>
      )}
    </div>
  );
}