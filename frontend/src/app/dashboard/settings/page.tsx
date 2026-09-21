"use client";

import { useAuth } from "@/lib/auth";

export default function SettingsPage() {
  const { user } = useAuth();

  return (
    <div className="mx-auto max-w-4xl">
      <h1 className="text-2xl font-bold text-zinc-900">Settings</h1>
      <p className="mt-2 text-sm text-zinc-500">Account and workspace preferences.</p>

      <div className="mt-8 max-w-lg rounded-xl border border-zinc-200 bg-white shadow-sm">
        <dl className="divide-y divide-zinc-200">
          <div className="px-5 py-4">
            <dt className="text-xs font-medium uppercase tracking-wide text-zinc-400">Username</dt>
            <dd className="mt-1 text-sm font-medium text-zinc-900">{user?.username ?? "—"}</dd>
          </div>
          <div className="px-5 py-4">
            <dt className="text-xs font-medium uppercase tracking-wide text-zinc-400">Email</dt>
            <dd className="mt-1 text-sm font-medium text-zinc-900">{user?.email ?? "—"}</dd>
          </div>
          <div className="px-5 py-4">
            <dt className="text-xs font-medium uppercase tracking-wide text-zinc-400">
              Full name
            </dt>
            <dd className="mt-1 text-sm font-medium text-zinc-900">
              {user?.full_name ?? "—"}
            </dd>
          </div>
        </dl>
      </div>
      <p className="mt-4 text-xs text-zinc-400">
        Organization management, API keys, and notification preferences arrive in later phases.
      </p>
    </div>
  );
}