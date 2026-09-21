"use client";

import { FolderOpen, Loader2 } from "lucide-react";

import { AGENT_OPTIONS } from "@/components/analysis/AnalysisConfigPanel";
import { formatArea } from "@/components/map/AoiPanel";
import type { AnalysisSession } from "@/lib/api/types";
import clsx from "clsx";

interface SessionsListProps {
  sessions: AnalysisSession[];
  activeSessionId: number | null;
  loading: boolean;
  onReopen: (session: AnalysisSession) => void;
}

const STATUS_STYLES: Record<string, string> = {
  draft: "bg-zinc-100 text-zinc-600",
  queued: "bg-amber-50 text-amber-700",
  running: "bg-blue-50 text-blue-700",
  completed: "bg-emerald-50 text-emerald-700",
  failed: "bg-red-50 text-red-700",
};

export function SessionsList({ sessions, activeSessionId, loading, onReopen }: SessionsListProps) {
  if (loading) {
    return (
      <p className="flex items-center gap-2 text-xs text-zinc-500">
        <Loader2 className="h-3.5 w-3.5 animate-spin" /> Loading your analysis sessions…
      </p>
    );
  }

  if (sessions.length === 0) {
    return <p className="text-xs text-zinc-500">No analysis sessions yet. Draw an AOI and save a draft.</p>;
  }

  return (
    <ul className="space-y-2">
      {sessions.map((session) => {
        const active = session.id === activeSessionId;
        return (
          <li
            key={session.id}
            className={clsx(
              "rounded-lg border bg-white p-3 transition",
              active ? "border-brand-400 ring-1 ring-brand-100" : "border-zinc-200",
            )}
          >
            <div className="flex items-start justify-between gap-2">
              <div className="min-w-0">
                <p className="truncate text-sm font-medium text-zinc-900">{session.title}</p>
                <p className="mt-0.5 text-[11px] text-zinc-500">
                  {session.start_date ?? "—"} → {session.end_date ?? "—"}
                  {session.area_m2_approx > 0 ? ` · ${formatArea(session.area_m2_approx)}` : ""}
                </p>
              </div>
              <span
                className={clsx(
                  "shrink-0 rounded-full px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wide",
                  STATUS_STYLES[session.status] ?? "bg-zinc-100 text-zinc-600",
                )}
              >
                {session.status}
              </span>
            </div>
            {session.agents && session.agents.length > 0 && (
              <div className="mt-2 flex flex-wrap gap-1">
                {session.agents.map((code) => {
                  const option = AGENT_OPTIONS.find((item) => item.code === code);
                  return (
                    <span
                      key={code}
                      className="rounded-full bg-brand-50 px-2 py-0.5 text-[10px] font-medium text-brand-700"
                    >
                      {option?.label ?? code}
                    </span>
                  );
                })}
              </div>
            )}
            <button
              type="button"
              onClick={() => onReopen(session)}
              className="mt-2 inline-flex items-center gap-1.5 rounded-lg border border-zinc-300 px-2.5 py-1 text-[11px] font-medium text-zinc-700 transition hover:border-brand-400 hover:text-brand-600"
            >
              <FolderOpen className="h-3 w-3" />
              Reopen
            </button>
          </li>
        );
      })}
    </ul>
  );
}