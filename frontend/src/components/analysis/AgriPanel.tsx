"use client";

import { useCallback, useEffect, useState } from "react";
import clsx from "clsx";
import { Check, Loader2, RefreshCw, Sprout, TriangleAlert } from "lucide-react";

import { analyzeAgri, getAgriAnalysis, listSessionAgriAnalyses } from "@/lib/api/agri";
import { listRetrievals, listSessionScenes } from "@/lib/api/satellite";
import { ApiError } from "@/lib/api/client";
import type {
  AgriAnalysisResult,
  AgriAnalysisSummary,
  AgriTier,
  GeoJsonGeometry,
  RetrievalRecord,
  SatelliteScene,
} from "@/lib/api/types";
import { WeatherContextCard } from "./WeatherContextCard";

const NDVI_INDEX = { name: "ndvi", label: "NDVI — Normalized Difference Vegetation Index" };
const REQUIRED_BANDS = ["B04", "B08", "SCL"];

const TIER_COLORS: Record<string, string> = {
  very_low: "bg-amber-200",
  low: "bg-orange-300",
  moderate: "bg-yellow-300",
  high: "bg-lime-400",
  very_high: "bg-emerald-500",
};

function formatArea(m2: number | null | undefined): string {
  if (m2 === null || m2 === undefined) return "—";
  if (m2 >= 1_000_000) return `${(m2 / 1_000_000).toFixed(2)} km²`;
  if (m2 >= 10_000) return `${(m2 / 10_000).toFixed(1)} ha`;
  return `${m2.toFixed(0)} m²`;
}

function formatNumber(value: number | null | undefined, digits = 3): string {
  if (value === null || value === undefined || Number.isNaN(value)) return "—";
  return value.toFixed(digits);
}

function tierColor(tier: string): string {
  return TIER_COLORS[tier] ?? "bg-zinc-300";
}

interface AgriPanelProps {
  sessionId: number;
  aoi: GeoJsonGeometry | null;
}

export function AgriPanel({ sessionId, aoi }: AgriPanelProps) {
  const [scenes, setScenes] = useState<SatelliteScene[] | null>(null);
  const [summaries, setSummaries] = useState<AgriAnalysisSummary[] | null>(null);
  const [selectedSceneId, setSelectedSceneId] = useState<string>("");
  const [maskClouds, setMaskClouds] = useState(true);
  const [retrievals, setRetrievals] = useState<RetrievalRecord[]>([]);
  const [result, setResult] = useState<AgriAnalysisResult | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const selectedScene = scenes?.find((scene) => String(scene.id) === selectedSceneId) ?? null;
  const requiredReady = REQUIRED_BANDS.every((key) =>
    retrievals.some((record) => record.asset_key === key && record.status === "completed"),
  );
  const canAnalyze = aoi !== null && selectedScene !== null && !loading;

  useEffect(() => {
    let cancelled = false;
    async function load() {
      setLoading(true);
      setError(null);
      try {
        const [sceneList, analysisList] = await Promise.all([
          listSessionScenes(sessionId),
          listSessionAgriAnalyses(sessionId),
        ]);
        if (cancelled) return;
        setScenes(sceneList);
        setSummaries(analysisList);
        setSelectedSceneId((current) => (current && sceneList.some((s) => String(s.id) === current) ? current : String(sceneList[0]?.id ?? "")));
      } catch (err) {
        if (!cancelled) setError(err instanceof ApiError ? err.message : "The agri data could not be loaded.");
      } finally {
        if (!cancelled) setLoading(false);
      }
    }
    void load();
    return () => {
      cancelled = true;
    };
  }, [sessionId]);

  useEffect(() => {
    const sceneId = selectedScene?.id ?? null;
    if (!sceneId) {
      setRetrievals([]);
      setResult(null);
      return;
    }
    let cancelled = false;
    const targetSceneId: number = sceneId;
    async function loadRetrievals() {
      try {
        const records = await listRetrievals(targetSceneId);
        if (!cancelled) setRetrievals(records);
      } catch {
        // The scene panel surfaces retrieval errors; stay quiet here.
      }
    }
    void loadRetrievals();
    return () => {
      cancelled = true;
    };
  }, [selectedScene?.id]);

  const handleAnalyze = useCallback(async () => {
    if (!selectedScene) return;
    setLoading(true);
    setError(null);
    setResult(null);
    try {
      const response = await analyzeAgri(sessionId, selectedScene.id, {
        mask_clouds: maskClouds,
      });
      setResult(response.results[0] ?? null);
      setSummaries(await listSessionAgriAnalyses(sessionId));
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "The analysis could not be computed.");
    } finally {
      setLoading(false);
    }
  }, [sessionId, selectedScene, maskClouds]);

  const handleViewSummary = useCallback(async (analysisId: number) => {
    setLoading(true);
    setError(null);
    try {
      setResult(await getAgriAnalysis(analysisId));
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "The saved analysis could not be loaded.");
    } finally {
      setLoading(false);
    }
  }, []);

  return (
    <div className="space-y-3">
      <div className="flex flex-wrap items-center gap-2">
        <select
          value={selectedSceneId}
          onChange={(event) => setSelectedSceneId(event.target.value)}
          className="rounded-md border border-zinc-300 px-2 py-1 text-xs text-zinc-800"
          aria-label="Satellite scene"
        >
          <option value="">Select a scene…</option>
          {scenes?.map((scene) => (
            <option key={scene.id} value={String(scene.id)}>
              {scene.acquisition_date ?? "?"} · {scene.provider}
              {scene.cloud_cover !== null ? ` · ${scene.cloud_cover.toFixed(0)}% cloud` : ""}
            </option>
          ))}
        </select>
        <label className="flex items-center gap-1.5 text-xs text-zinc-600">
          <input
            type="checkbox"
            checked={maskClouds}
            onChange={(event) => setMaskClouds(event.target.checked)}
            className="h-3.5 w-3.5"
          />
          Mask clouds (SCL)
        </label>
        <button
          type="button"
          onClick={() => void handleAnalyze()}
          disabled={!canAnalyze}
          className="inline-flex items-center gap-1.5 rounded-lg bg-indigo-600 px-3 py-1.5 text-xs font-medium text-white transition hover:bg-indigo-700 disabled:cursor-not-allowed disabled:opacity-50"
        >
          {loading ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Sprout className="h-3.5 w-3.5" />}
          {loading ? "Analyzing..." : "Analyze NDVI"}
        </button>
        <button
          type="button"
          onClick={() => {
            if (selectedScene) void loadRetrievalsForScene(selectedScene.id);
          }}
          disabled={loading}
          className="inline-flex items-center gap-1.5 rounded-lg border border-zinc-300 px-3 py-1.5 text-xs font-medium text-zinc-600 transition hover:bg-zinc-50"
        >
          <RefreshCw className="h-3.5 w-3.5" />
          Refresh bands
        </button>
      </div>

      {!canAnalyze && aoi === null && (
        <p className="text-xs text-amber-700">Draw or select an AOI before analyzing.</p>
      )}

      <div className="flex flex-wrap gap-1.5">
        {REQUIRED_BANDS.map((key) => {
          const record = retrievals.find((item) => item.asset_key === key);
          const ready = record?.status === "completed";
          return (
            <span
              key={key}
              title={ready ? `${key} band downloaded` : `${key} band not retrieved yet`}
              className={clsx(
                "inline-flex items-center gap-1 rounded-full border px-2 py-0.5 text-[11px] font-medium",
                ready ? "border-emerald-200 bg-emerald-50 text-emerald-700" : "border-zinc-200 text-zinc-500",
              )}
            >
              {ready ? <Check className="h-3 w-3" /> : <TriangleAlert className="h-3 w-3" />}
              {key}
            </span>
          );
        })}
        {selectedScene && !requiredReady && (
          <span className="text-[11px] text-zinc-500">
            Missing bands will be reported as unavailable — use the Scene panel to download B04,
            B08 and SCL for this scene.
          </span>
        )}
      </div>

      <p className="text-[11px] text-zinc-500">{NDVI_INDEX.label}</p>

      {error && <p className="text-xs text-red-600">{error}</p>}

      {result && result.status === "unavailable" && result.unavailable && (
        <div className="rounded-lg border border-amber-200 bg-amber-50 p-3">
          <p className="flex items-center gap-1.5 text-xs font-medium text-amber-800">
            <TriangleAlert className="h-4 w-4" /> Analysis unavailable
          </p>
          <p className="mt-1 text-[11px] text-amber-800">{result.unavailable.reason}</p>
          {result.unavailable.details.length > 0 && (
            <ul className="mt-1 list-inside list-disc text-[11px] text-amber-700">
              {result.unavailable.details.map((detail) => (
                <li key={detail}>{detail}</li>
              ))}
            </ul>
          )}
        </div>
      )}

      {result && result.status === "unavailable" && (
        <WeatherContextCard context={result.weather_context} />
      )}

      {result?.status === "completed" && result.statistics && result.classification && (
        <>
          <AnalysisResultCard result={result} />
          <WeatherContextCard context={result.weather_context} />
        </>
      )}

      {summaries && summaries.length > 0 && (
        <div className="rounded-lg border border-zinc-200 bg-white p-3">
          <p className="mb-2 text-[11px] font-semibold text-zinc-600">Saved analyses</p>
          <ul className="space-y-1">
            {summaries.map((summary) => (
              <li key={summary.id} className="flex items-center justify-between gap-2 text-[11px]">
                <span className="flex items-center gap-1.5 text-zinc-600">
                  {summary.acquisition_date}
                  <span
                    className={clsx(
                      "rounded-full px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wide",
                      summary.overall_tier ? "bg-indigo-50 text-indigo-700" : "bg-zinc-100 text-zinc-500",
                    )}
                  >
                    {summary.overall_tier ?? "n/a"}
                  </span>
                  <span className="text-zinc-400">{formatNumber(summary.mean_value)}</span>
                </span>
                <button
                  type="button"
                  onClick={() => void handleViewSummary(summary.id)}
                  className="font-medium text-indigo-600 hover:text-indigo-700"
                >
                  View
                </button>
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );

  async function loadRetrievalsForScene(sceneId: number) {
    setError(null);
    try {
      setRetrievals(await listRetrievals(sceneId));
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "The retrieval status could not be loaded.");
    }
  }
}

function AnalysisResultCard({ result }: { result: AgriAnalysisResult }) {
  const stats = result.statistics!;
  const classification = result.classification!;
  const cloud = result.cloud;
  return (
    <div className="space-y-3 rounded-lg border border-zinc-200 bg-white p-3">
      <div className="flex flex-wrap items-center gap-2">
        <span className="rounded-full bg-green-100 px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wide text-green-800">
          {classification.overall.tier}
        </span>
        <span className="text-xs font-medium text-zinc-800">NDVI</span>
        <span className="text-[11px] text-zinc-500">
          Scene {result.scene.acquisition_date} · {result.scene.provider}
        </span>
      </div>

      <div className="grid grid-cols-2 gap-2 sm:grid-cols-3">
        <Stat label="Mean" value={formatNumber(stats.mean)} />
        <Stat label="Median" value={formatNumber(stats.median)} />
        <Stat label="Std dev" value={formatNumber(stats.stddev)} />
        <Stat label="Min" value={formatNumber(stats.min)} />
        <Stat label="Max" value={formatNumber(stats.max)} />
        <Stat label="Valid pixels" value={`${formatNumber(stats.valid_pixel_pct, 1)}%`} />
      </div>

      <div>
        <p className="mb-1 text-[10px] font-semibold uppercase tracking-wide text-zinc-400">
          Vegetation-condition share (heuristic)
        </p>
        <div className="flex h-2.5 w-full overflow-hidden rounded-full bg-zinc-100">
          {classification.tiers.map((tier) => (
            <div
              key={tier.tier}
              className={clsx(tierColor(tier.tier))}
              style={{ width: `${tier.pixel_pct}%` }}
              title={`${tier.label} (${tier.pixel_pct}%)`}
            />
          ))}
        </div>
        <div className="mt-2 grid grid-cols-2 gap-x-4 gap-y-1 sm:grid-cols-3">
          {classification.tiers.map((tier: AgriTier) => (
            <div key={tier.tier} className="flex items-center gap-1.5 text-[11px] text-zinc-600">
              <span className={clsx("h-2 w-2 rounded-full", tierColor(tier.tier))} />
              <span className="capitalize">{tier.label}</span>
              <span className="text-zinc-400">{tier.pixel_pct.toFixed(1)}%</span>
            </div>
          ))}
        </div>
      </div>

      {(result.warnings ?? []).length > 0 && (
        <ul className="list-inside list-disc text-[11px] text-amber-700">
          {result.warnings.map((warning) => (
            <li key={warning}>{warning}</li>
          ))}
        </ul>
      )}

      <div className="rounded-md bg-zinc-50 p-2 text-[11px] leading-relaxed text-zinc-500">
        <p className="font-medium text-zinc-600">{result.index?.formula}</p>
        <p>{classification.threshold_source}</p>
        {result.bands && result.bands.length > 0 && (
          <p className="mt-1">
            Bands: {result.bands.map((band) => `${band.role} (${band.asset_key})`).join(", ")}
            {cloud?.mask_clouds
              ? ` · cloud classes ${cloud.masked_classes.join(", ")} masked`
              : " · no cloud masking"}
          </p>
        )}
        {result.processing && (
          <p className="mt-1">
            Sampled ~{formatArea(Number(result.processing.valid_pixel_area_m2))} ·{" "}
            {String(result.processing.algorithm)}
          </p>
        )}
        <p className="mt-1 text-zinc-400">
          Vegetation-condition signal only — not a validated crop-health or yield model.
        </p>
      </div>
    </div>
  );
}

function Stat({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-md bg-zinc-50 px-2 py-1.5">
      <p className="text-[10px] font-semibold uppercase tracking-wide text-zinc-400">{label}</p>
      <p className="text-sm font-semibold text-zinc-800">{value}</p>
    </div>
  );
}