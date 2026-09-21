import Link from "next/link";

export default function HomePage() {
  return (
    <main className="flex min-h-screen flex-col items-center justify-center px-6 text-center">
      <div className="max-w-2xl">
        <p className="text-sm font-semibold uppercase tracking-widest text-brand-600">
          Geospatial Analysis Workbench
        </p>
        <h1 className="mt-4 text-4xl font-bold tracking-tight text-zinc-900 sm:text-5xl">
          GeoAgent
        </h1>
        <p className="mt-6 text-lg text-zinc-600">
          Define areas of interest, layer satellite and weather data, and let
          agents help you turn imagery into insight.
        </p>
        <div className="mt-10 flex items-center justify-center gap-4">
          <Link
            href="/dashboard"
            className="rounded-lg bg-brand-600 px-5 py-2.5 text-sm font-medium text-white shadow-sm transition hover:bg-brand-700"
          >
            Open dashboard
          </Link>
          <Link
            href="/login"
            className="rounded-lg border border-zinc-300 px-5 py-2.5 text-sm font-medium text-zinc-700 transition hover:bg-zinc-100"
          >
            Sign in
          </Link>
        </div>
        <p className="mt-14 text-xs text-zinc-400">
          Phase 2 foundation · organizations, workspaces, and saved locations
        </p>
      </div>
    </main>
  );
}