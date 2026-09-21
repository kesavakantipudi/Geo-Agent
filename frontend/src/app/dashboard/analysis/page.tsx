import type { Metadata } from "next";

import { AnalysisWorkspace } from "@/components/analysis/AnalysisWorkspace";

export const metadata: Metadata = { title: "Analysis" };

export default function AnalysisPage() {
  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-zinc-900">Analysis</h1>
        <p className="mt-1 text-sm text-zinc-500">
          Draw or import an area of interest, choose agents and a time range, and save a draft to
          prepare an analysis.
        </p>
      </div>
      <AnalysisWorkspace />
    </div>
  );
}