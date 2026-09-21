"use client";

import { useCallback, useEffect, useState } from "react";
import clsx from "clsx";
import {
  Check,
  Cloud,
  Loader2,
  PackageOpen,
  RefreshCw,
  Trash2,
  TriangleAlert,
} from "lucide-react";

import type {
  GeoJsonGeometry,
  RetrievalRecord,
  SatelliteProviderCode,
  SatelliteScene,
  SceneAsset,
} from "@/lib/api/types";
import {
  deleteRetrieval,
  listRetrievals,
  listSessionScenes,
  requestRetrieval,
  searchScenes,
} from "@/lib/api/satellite";
import { ApiError } from "@/lib/api/client";

function formatBytes(bytes: number | null | undefined): string {
  if (bytes === null || bytes === undefined) return "-";
  if (bytes < 1024) return bytes + " B";
  const units: Array<[number, string]> = [
    [1024, "KiB"],
    [1024 * 1024, "MiB"],
    [1024 ** 3, "GiB"],
    [1024 ** 4, "TiB"],
  ];
  let value = bytes / 1024;
  for (const [factor, label] of units) {
    if (value < factor) {
      return value.toFixed(1) + " " + label;
    }
    value = value / factor;
  }
  return value.toFixed(1) + " TiB";
}

interface SceneDiscoveryPanelProps {
  sessionId: number;
  aoi: GeoJsonGeometry | null;
  startDate: string;
  endDate: string;
  providers?: SatelliteProviderCode[];
}

export function SceneDiscoveryPanel({
  sessionId,
  aoi,
  startDate,
  endDate,
  providers,
}: SceneDiscoveryPanelProps) {
  const [scenes, setScenes] = useState<SatelliteScene[] | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [operationError, setOperationError] = useState<string | null>(null);
  const [truncated, setTruncated] = useState(false);
  const [cloudLimit, setCloudLimit] = useState(100);
  const [expandedIds, setExpandedIds] = useState<Set<number>>(new Set());
  const [retrievals, setRetrievals] = useState<Record<number, RetrievalRecord[]>>({});
  const [busySceneId, setBusySceneId] = useState<number | null>(null);

  const canSearch = aoi !== null;

  const handleSearch = useCallback(async () => {
    if (!canSearch) return;
    setLoading(true);
    setError(null);
    setOperationError(null);
    try {
      const result = await searchScenes(sessionId, {
        aoi,
        start_date: startDate,
        end_date: endDate,
        max_cloud_cover: cloudLimit,
        providers,
      });
      setScenes(result.scenes);
      setTruncated(result.truncated);
    } catch (err) {
      setScenes(null);
      setError(err instanceof ApiError ? err.message : "The scene search could not be completed.");
    } finally {
      setLoading(false);
    }
  }, [canSearch, sessionId, aoi, startDate, endDate, cloudLimit, providers]);

  async function handleLoadSaved() {
    setLoading(true);
    setError(null);
    setOperationError(null);
    try {
      setScenes(await listSessionScenes(sessionId));
      setTruncated(false);
    } catch (err) {
      setScenes(null);
      setError(err instanceof ApiError ? err.message : "The saved scenes could not be loaded.");
    } finally {
      setLoading(false);
    }
  }

  async function handleRetrieve(scene: SatelliteScene, asset: SceneAsset) {
    setBusySceneId(scene.id);
    setOperationError(null);
    try {
      const records = await requestRetrieval(scene.id, [asset.key], sessionId);
      setRetrievals((prev) => ({ ...prev, [scene.id]: records }));
    } catch (err) {
      setOperationError(err instanceof ApiError ? err.message : "The asset could not be retrieved.");
    } finally {
      setBusySceneId(null);
    }
  }

  async function handleRefreshRetrievals(scene: SatelliteScene) {
    setBusySceneId(scene.id);
    setOperationError(null);
    try {
      const records = await listRetrievals(scene.id);
      setRetrievals((prev) => ({ ...prev, [scene.id]: records }));
    } catch (err) {
      setOperationError(err instanceof ApiError ? err.message : "The retrieval history could not be loaded.");
    } finally {
      setBusySceneId(null);
    }
  }

  async function handleDeleteRetrieval(sceneId: number, retrievalId: number) {
    setOperationError(null);
    try {
      await deleteRetrieval(retrievalId);
      setRetrievals((prev) => ({
        ...prev,
        [sceneId]: (prev[sceneId] ?? []).filter((record) => record.id !== retrievalId),
      }));
    } catch (err) {
      setOperationError(err instanceof ApiError ? err.message : "The retrieval could not be deleted.");
    }
  }

  function toggleScene(sceneId: number) {
    setExpandedIds((current) => {
      const next = new Set(current);
      if (next.has(sceneId)) next.delete(sceneId);
      else next.add(sceneId);
      return next;
    });
  }

  return (
    <div className="space-y-3">

      <div className="flex flex-wrap items-center gap-2">
        <label className="flex items-center gap-2 text-xs text-zinc-600">
          Max cloud cover
          <input
            type="number"
            min={0}
            max={100}
            value={cloudLimit}
            onChange={(event) => setCloudLimit(Number(event.target.value) || 0)}
            className="w-16 rounded-md border border-zinc-300 px-2 py-1 text-xs text-zinc-800"
          />
        </label>
        <button
          type="button"
          onClick={() => void handleSearch()}
          disabled={!canSearch || loading}
          className="inline-flex items-center gap-1.5 rounded-lg bg-indigo-600 px-3 py-1.5 text-xs font-medium text-white transition hover:bg-indigo-700 disabled:cursor-not-allowed disabled:opacity-50"
        >
          {loading ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <PackageOpen className="h-3.5 w-3.5" />}
          {loading ? "Searching..." : "Discover scenes"}
        </button>
        <button
          type="button"
          onClick={() => void handleLoadSaved()}
          disabled={loading}
          className="inline-flex items-center gap-1.5 rounded-lg border border-zinc-300 px-3 py-1.5 text-xs font-medium text-zinc-600 transition hover:bg-zinc-50"
        >
          <RefreshCw className="h-3.5 w-3.5" />
          Load saved
        </button>
      </div>

      {!canSearch && (
        <p className="text-xs text-amber-700">Draw or select an AOI before searching scenes.</p>
      )}
      {error && <p className="text-xs text-red-600">{error}</p>}
      {operationError && <p className="text-xs text-red-600">{operationError}</p>}
      {truncated && (
        <p className="text-xs text-amber-700">
          Results were truncated to the maximum number of scenes.
        </p>
      )}
      {scenes && scenes.length === 0 && !loading && (
        <p className="text-xs text-zinc-500">
          No scenes matched the AOI and date range for the enabled providers.
        </p>
      )}

      {scenes && scenes.length > 0 && (
        <ul className="space-y-2">
          {scenes.map((scene) => (
            <SceneRow
              key={scene.id}
              scene={scene}
              expanded={expandedIds.has(scene.id)}
              busySceneId={busySceneId}
              retrievals={retrievals[scene.id] ?? []}
              onToggle={() => toggleScene(scene.id)}
              onRetrieve={(asset) => void handleRetrieve(scene, asset)}
              onRefresh={() => void handleRefreshRetrievals(scene)}
              onDeleteRetrieval={(retrievalId) => void handleDeleteRetrieval(scene.id, retrievalId)}
            />
          ))}
        </ul>
      )}
    </div>
  );
}

function SceneRow({
  scene,
  expanded,
  busySceneId,
  retrievals,
  onToggle,
  onRetrieve,
  onRefresh,
  onDeleteRetrieval,
}: {
  scene: SatelliteScene;
  expanded: boolean;
  busySceneId: number | null;
  retrievals: RetrievalRecord[];
  onToggle: () => void;
  onRetrieve: (asset: SceneAsset) => void;
  onRefresh: () => void;
  onDeleteRetrieval: (retrievalId: number) => void;
}) {
  const [busyAssetKey, setBusyAssetKey] = useState<string | null>(null);
  const [refreshing, setRefreshing] = useState(false);

  return (
    <li className="rounded-lg border border-zinc-200 bg-white p-3">
      <button
        type="button"
        onClick={onToggle}
        className="flex w-full items-center justify-between gap-2 text-left"
      >
        <span
          className={clsx(
            "rounded-full px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wide",
            scene.platform && scene.platform.startsWith("sentinel-2")
              ? "bg-sky-50 text-sky-700"
              : "bg-zinc-100 text-zinc-600",
          )}
        >
          {scene.provider}
        </span>
        <span className="flex items-center gap-2 text-[11px] text-zinc-500">
          {scene.cloud_cover !== null && (
            <span className="flex items-center gap-0.5">
              <Cloud className="h-3 w-3" /> {scene.cloud_cover.toFixed(1)}%
            </span>
          )}
          {scene.acquisition_date}
          <RefreshCw className={clsx("h-3 w-3", expanded && "rotate-180 transition-transform")} />
        </span>
      </button>

      {expanded && (
        <div className="mt-3 space-y-2">
          <div className="flex flex-wrap gap-1.5">
            {scene.assets.map((asset) => (
              <button
                key={asset.key}
                type="button"
                disabled={busySceneId === scene.id || busyAssetKey !== null}
                onClick={() => {
                  setBusyAssetKey(asset.key);
                  void onRetrieve(asset);
                }}
                className="inline-flex items-center gap-1.5 rounded-md border border-indigo-200 bg-indigo-50 px-2 py-1 text-[11px] font-medium text-indigo-700 transition hover:bg-indigo-100 disabled:opacity-50"
              >
                {busyAssetKey === asset.key ? (
                  <Loader2 className="h-3 w-3 animate-spin" />
                ) : (
                  <PackageOpen className="h-3 w-3" />
                )}
                {asset.key}
              </button>
            ))}
          </div>

          <div className="flex items-center justify-between">
            <span className="text-[11px] font-medium text-zinc-500">Retrieval history</span>
            <button
              type="button"
              onClick={() => void onRefresh()}
              disabled={refreshing}
              className="inline-flex items-center gap-1 text-[11px] font-medium text-indigo-600 hover:text-indigo-700 disabled:opacity-50"
            >
              <RefreshCw className={clsx("h-3 w-3", refreshing && "animate-spin")} />
              Refresh
            </button>
          </div>

          {retrievals.length === 0 && (
            <p className="text-[11px] text-zinc-400">No retrieval records yet.</p>
          )}

          {retrievals.length > 0 && (
            <table className="w-full text-left text-[11px]">
              <thead>
                <tr className="border-b border-zinc-100 text-[10px] uppercase text-zinc-400">
                  <th className="py-1 pr-2 font-medium">Asset</th>
                  <th className="py-1 pr-2 font-medium">Status</th>
                  <th className="py-1 pr-2 font-medium">Size</th>
                  <th className="py-1 font-medium"></th>
                </tr>
              </thead>
              <tbody>
                {retrievals.map((record) => (
                  <tr key={record.id} className="border-t border-zinc-100">
                    <td className="py-1 pr-2 text-zinc-500">{record.asset_key}</td>
                    <td className="py-1 pr-2">
                      <span
                        className={clsx(
                          "inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-[10px] font-medium",
                          record.status === "completed"
                            ? "bg-emerald-50 text-emerald-700"
                            : "bg-red-50 text-red-700",
                        )}
                      >
                        {record.status === "completed" ? (
                          <Check className="h-3 w-3" />
                        ) : (
                          <TriangleAlert className="h-3 w-3" />
                        )}
                        {record.status}
                      </span>
                    </td>
                    <td className="py-1 pr-2 text-zinc-500">
                      {record.size_bytes !== null ? formatBytes(record.size_bytes) : "-"}
                    </td>
                    <td className="py-1 text-right">
                      <button
                        type="button"
                        onClick={() => onDeleteRetrieval(record.id)}
                        title="Delete retrieval record"
                        className="text-zinc-400 transition hover:text-red-600"
                      >
                        <Trash2 className="h-3.5 w-3.5" />
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
      )}
    </li>
  );
}

function FetchButton({ icon, label, onClick, disabled, loading }: {
  icon: string;
  label: string;
  onClick: () => void;
  disabled: boolean;
  loading: boolean;
}) {
  return (
    <button type="button" onClick={onClick} disabled={disabled || loading} className={clsx("rounded-md px-2 py-1 text-[11px]", disabled ? "opacity-40" : "text-indigo-600")}>
      {icon} {label}
    </button>
  );
}
