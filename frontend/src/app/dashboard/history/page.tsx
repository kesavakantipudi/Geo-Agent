import type { Metadata } from "next";

export const metadata: Metadata = { title: "History" };

export default function HistoryPage() {
  return (
    <div className="mx-auto max-w-4xl">
      <h1 className="text-2xl font-bold text-zinc-900">History</h1>
      <p className="mt-2 text-sm text-zinc-500">Past analyses, saved queries, and agent sessions.</p>

      <div className="mt-8 rounded-xl border border-zinc-200 bg-white p-10 text-center shadow-sm">
        <p className="text-sm font-medium text-zinc-700">Nothing here yet</p>
        <p className="mx-auto mt-2 max-w-md text-xs leading-relaxed text-zinc-500">
          Once Phase 3 ships analyses and agent sessions, completed runs will appear here along
          with their output artifacts.
        </p>
      </div>
    </div>
  );
}