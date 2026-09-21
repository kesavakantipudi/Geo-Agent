"use client";

import { MapPin, Layers, History } from "lucide-react";

import { useAuth } from "@/lib/auth";

const PLACEHOLDER_CARDS = [
  {
    icon: Layers,
    title: "Workspaces",
    description: "Organize locations and analyses into shared workspaces per organization.",
  },
  {
    icon: MapPin,
    title: "Saved locations",
    description: "Save points, polygons, and lines with geometry stored natively in PostGIS.",
  },
  {
    icon: History,
    title: "Analysis history",
    description: "Track imagery, weather, and agent activity over time (coming in Phase 3).",
  },
];

export default function DashboardHomePage() {
  const { user, loading } = useAuth();

  return (
    <div className="mx-auto max-w-4xl">
      <h1 className="text-2xl font-bold text-zinc-900">
        {loading ? "Welcome" : `Welcome, ${user?.full_name ?? user?.username ?? "there"}`}
      </h1>
      <p className="mt-2 text-sm text-zinc-500">
        Phase 2 foundation is live: organizations, workspaces, and saved locations. Map and
        imagery tooling lands in Phase 3.
      </p>

      <div className="mt-8 grid gap-4 sm:grid-cols-3">
        {PLACEHOLDER_CARDS.map((card) => {
          const Icon = card.icon;
          return (
            <div
              key={card.title}
              className="rounded-xl border border-zinc-200 bg-white p-5 shadow-sm"
            >
              <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-brand-50">
                <Icon className="h-5 w-5 text-brand-600" />
              </div>
              <h2 className="mt-4 text-sm font-semibold text-zinc-900">{card.title}</h2>
              <p className="mt-1.5 text-xs leading-relaxed text-zinc-500">{card.description}</p>
            </div>
          );
        })}
      </div>
    </div>
  );
}