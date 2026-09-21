import type { Metadata } from "next";

export const metadata: Metadata = { title: "Analysis" };

export default function AnalysisPage() {
  return (
    <div className="mx-auto max-w-4xl">
      <h1 className="text-2xl font-bold text-zinc-900">Analysis</h1>
      <p className="mt-2 text-sm text-zinc-500">
        Build analyses over areas of interest with satellite and weather layers.
      </p>

      <div className="mt-8 rounded-xl border border-dashed border-zinc-300 bg-white p-10 text-center">
        <p className="text-sm font-medium text-zinc-700">Analysis canvas</p>
        <p className="mx-auto mt-2 max-w-md text-xs leading-relaxed text-zinc-500">
          The map canvas, AOI selection, and satellite/weather layer pickers arrive in Phase 3.
          Backend endpoints for analyses, satellite scenes, and weather observations are already
          prepared (they migrate in with the data model).
        </p>
      </div>
    </div>
  );
}