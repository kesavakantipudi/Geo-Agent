"use client";

import { useCallback, useEffect, useState } from "react";
import clsx from "clsx";
import {
  ArrowRight,
  Check,
  Diff,
  Loader2,
  Map as MapIcon,
  TriangleAlert,
} from "lucide-react";

import { analyzeChange } from "@/lib/api/change";
import { ApiError } from "@/lib/api/client";
import { listRetrievals, listSessionScenes } from "@/lib/api/satellite";
import type {
  ChangeClassification,
  ChangeDetectionResponse,
  ChangeMask,
  ChangeType,
  ChangeTypeBlock,
  GeoJsonGeometry,
  RetrievalRecord,
  SatelliteScene,
  WeatherContext,
} from "@/lib/api/types";
import { WeatherContextCard } from "./WeatherContextCard";

const REQUIRED_BAND_KEYS = ["B03", "B04", "B08", "SCL"];

const CLASS_COLORS: Record<string, string> = {
  "0": "bg-zinc-300",
  "1": "bg-emerald-500",
  "2": "bg-rose-400",
  "3": "bg-blue-700",
};

function formatArea(m2: number | null | undefined): string {
  if (m2 === null || m2 === undefined || Number.isNaN(m2)) return "—";
  if (m2 >= 1_000_000) return `${(m2 / 1_000_000).toFixed(2)} km²`;
  if (m2 >= 10_000) return `${(m2 / 10_000).toFixed(2)} ha`;
  return `${m2.toFixed(0)} m²`;
}

function formatNumber(value: number | null | undefined, digits = 3): string {
  if (value === null || value === undefined || Number.isNaN(value)) return "—";
  return value.toFixed(digits);
}

function formatPct(value: number | null | undefined): string {
  if (value === null || value === undefined || Number.isNaN(value)) return "—";
  return `${value.toFixed(1)}%`;
}

export interface ChangeOverlay {
  type: ChangeType;
  mask: ChangeMask;
}

interface ChangeDetectionPanelProps {
  sessionId: number;
  aoi: GeoJsonGeometry | null;
  overlay: ChangeOverlay | null;
  onOverlayChange: (overlay: ChangeOverlay | null) => void;
}

export function ChangeDetectionPanel({
  sessionId,
  aoi,
  overlay,
  onOverlayChange,
}: ChangeDetectionPanelProps) {
  const [scenes, setScenes] = useState<SatelliteScene[] | null>(null);
  const [beforeSceneId, setBeforeSceneId] = useState("");
  const [afterSceneId, setAfterSceneId] = useState("");
  const [types, setTypes] = useState<ChangeType[]>(["vegetation", "water"]);
  const [maskClouds, setMaskClouds] = useState(true);
  const [includeWeather, setIncludeWeather] = useState(true);
  const [vegetationThreshold, setVegetationThreshold] = useState("0.10");
  const [waterThreshold, setWaterThreshold] = useState("0");
  const [retrievalsBefore, setRetrievalsBefore] = useState<RetrievalRecord[]>([]);
  const [retrievalsAfter, setRetrievalsAfter] = useState<RetrievalRecord[]>([]);
  const [result, setResult] = useState<ChangeDetectionResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const beforeScene = scenes?.find((scene) => String(scene.id) === beforeSceneId) ?? null;
  const afterScene = scenes?.find((scene) => String(scene.id) === afterSceneId) ?? null;

  const vegThreshold = Number.parseFloat(vegetationThreshold);
  const waterThresholdValue = Number.parseFloat(waterThreshold);
  const validVegThreshold = Number.isFinite(vegThreshold) && vegThreshold > 0 && vegThreshold <= 2;
  const validWaterThreshold =
    Number.isFinite(waterThresholdValue) &&
    waterThresholdValue >= -1 &&
    waterThresholdValue <= 1;
  const orderOk =
    beforeSceneId !== "" &&
    afterSceneId !== "" &&
    beforeSceneId !== afterSceneId &&
    (beforeScene?.acquisition_date ?? "") < (afterScene?.acquisition_date ?? "");
  const canAnalyze = aoi !== null && beforeScene !== null && afterScene !== null && orderOk && !loading;

  useEffect(() => {
    let cancelled = false;
    async function load() {
      setLoading(true);
      setError(null);
      try {
        const sceneList = await listSessionScenes(sessionId);
        if (cancelled) return;
        const ascending = [...sceneList].sort((a, b) =>
          (a.acquisition_date ?? "").localeCompare(b.acquisition_date ?? ""),
        );
        setScenes(sceneList);
        setBeforeSceneId((current) =>
          ascending.some((scene) => String(scene.id) === current)
            ? current
            : String(ascending[0]?.id ?? ""),
        );
        setAfterSceneId((current) =>
          ascending.some((scene) => String(scene.id) === current)
            ? current
            : String(ascending.length > 1 ? ascending[ascending.length - 1].id : ""),
        );
      } catch (err) {
        if (!cancelled) {
          setError(err instanceof ApiError ? err.message : "Scenes could not be loaded.");
        }
      } finally {
        if (!cancelled) setLoading(false);
      }
    }
    void load();
    return () => {
      cancelled = true;
    };
  }, [sessionId]);

  const loadRetrievals = useCallback(
    async (sceneId: string, setter: (records: RetrievalRecord[]) => void) => {
      if (!sceneId) {
        setter([]);
        return;
      }
      try {
        setter(await listRetrievals(Number(sceneId)));
      } catch {
        setter([]);
      }
    },
    [],
  );

  useEffect(() => {
    void loadRetrievals(beforeSceneId, setRetrievalsBefore);
  }, [beforeSceneId, loadRetrievals]);

  useEffect(() => {
    void loadRetrievals(afterSceneId, setRetrievalsAfter);
  }, [afterSceneId, loadRetrievals]);

  function toggleType(type: ChangeType) {
    setTypes((current) =>
      current.includes(type) ? current.filter((item) => item !== type) : [...current, type],
    );
  }

  const handleAnalyze = useCallback(async () => {
    if (!beforeScene || !afterScene) return;
    setLoading(true);
    setError(null);
    setResult(null);
    try {
      const response = await analyzeChange(sessionId, beforeScene.id, afterScene.id, {
        types,
        mask_clouds: maskClouds,
        include_weather: includeWeather,
        vegetation_threshold: validVegThreshold ? vegThreshold : null,
        water_threshold: validWaterThreshold ? waterThresholdValue : null,
      });
      setResult(response);
      const completed = (["vegetation", "water"] as ChangeType[]).find(
        (type) =>
          response.types_requested.includes(type) && response[type]?.status === "completed",
      );
      if (completed && response[completed]?.mask) {
        onOverlayChange({ type: completed, mask: response[completed]!.mask! });
      }
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "The change could not be computed.");
    } finally {
      setLoading(false);
    }
  }, [
    sessionId,
    beforeScene,
    afterScene,
    types,
    maskClouds,
    includeWeather,
    validVegThreshold,
    vegThreshold,
    validWaterThreshold,
    waterThresholdValue,
    onOverlayChange,
  ]);

  return (
    <div className="space-y-3">
      <div className="flex flex-wrap items-center gap-2">
        <SceneSelect
          label="Before"
          scenes={scenes ?? []}
          value={beforeSceneId}
          onChange={setBeforeSceneId}
        />
        <ArrowRight className="h-3.5 w-3.5 text-zinc-400" />
        <SceneSelect
          label="After"
          scenes={scenes ?? []}
          value={afterSceneId}
          onChange={setAfterSceneId}
        />
      </div>

      <div className="flex flex-wrap items-center gap-3">
        <div className="flex items-center gap-1 text-[11px] text-zinc-600">
          {(Object.keys(TYPE_LABELS) as ChangeType[]).map((type) => (
            <label key={type} className="inline-flex items-center gap-1">
              <input
                type="checkbox"
                checked={types.includes(type)}
                onChange={() => toggleType(type)}
                className="h-3.5 w-3.5"
              />
              {TYPE_LABELS[type]}
            </label>
          ))}
        </div>
        <label className="flex items-center gap-1.5 text-xs text-zinc-600">
          <input
            type="checkbox"
            checked={maskClouds}
            onChange={(event) => setMaskClouds(event.target.checked)}
            className="h-3.5 w-3.5"
          />
          Mask clouds (SCL)
        </label>
        <label className="flex items-center gap-1.5 text-xs text-zinc-600">
          <input
            type="checkbox"
            checked={includeWeather}
            onChange={(event) => setIncludeWeather(event.target.checked)}
            className="h-3.5 w-3.5"
          />
          Weather context
        </label>
      </div>

      <div className="flex flex-wrap items-center gap-3">
        <label className="text-[11px] text-zinc-600">
          NDVI delta ≥&nbsp;
          <input
            type="number"
            step="0.05"
            value={vegetationThreshold}
            onChange={(event) => setVegetationThreshold(event.target.value)}
            className={clsx(
              "w-16 rounded-md border px-1.5 py-0.5 text-xs",
              validVegThreshold ? "border-zinc-300" : "border-rose-300 bg-rose-50",
            )}
          />
        </label>
        <label className="text-[11px] text-zinc-600">
          Water NDWI ≥&nbsp;
          <input
            type="number"
            step="0.05"
            value={waterThreshold}
            onChange={(event) => setWaterThreshold(event.target.value)}
            className={clsx(
              "w-16 rounded-md border px-1.5 py-0.5 text-xs",
              validWaterThreshold ? "border-zinc-300" : "border-rose-300 bg-rose-50",
            )}
          />
        </label>
      </div>

      <div className="flex flex-wrap items-center gap-2">
        <button
          type="button"
          onClick={() => void handleAnalyze()}
          disabled={!canAnalyze}
          className="inline-flex items-center gap-1.5 rounded-lg bg-indigo-600 px-3 py-1.5 text-xs font-medium text-white transition hover:bg-indigo-700 disabled:cursor-not-allowed disabled:opacity-50"
        >
          {loading ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Diff className="h-3.5 w-3.5" />}
          {loading ? "Comparing..." : "Analyze change"}
        </button>
      </div>

      {!canAnalyze && aoi === null && <p className="text-xs text-amber-700">Draw or select an AOI before analyzing.</p>}
      {!canAnalyze && aoi !== null && (beforeSceneId === "" || afterSceneId === "" || !orderOk) && (
        <p className="text-xs text-amber-700">
          Two distinct scenes with the before scene dated earlier than the after scene are required.
        </p>
      )}

      <div className="flex flex-wrap gap-1.5">
        <SceneBands label="Before" scene={beforeScene} retrievals={retrievalsBefore} />
        <SceneBands label="After" scene={afterScene} retrievals={retrievalsAfter} />
        {(beforeScene || afterScene) && (
          <span className="text-[11px] text-zinc-500">
            Missing bands are reported as unavailable — use the Scene panel to download B03, B04,
            B08 and SCL for both scenes.
          </span>
        )}
      </div>

      {error && <p className="text-xs text-red-600">{error}</p>}

      {result && result.status === "unavailable" && (
        <div className="rounded-lg border border-amber-200 bg-amber-50 p-3">
          <p className="flex items-center gap-1.5 text-xs font-medium text-amber-800">
            <TriangleAlert className="h-4 w-4" /> Change analysis unavailable
          </p>
          <p className="mt-1 text-[11px] text-amber-800">{result.unavailable?.reason}</p>
          {(result.unavailable?.details ?? []).length > 0 && (
            <ul className="mt-1 list-inside list-disc text-[11px] text-amber-700">
              {result.unavailable!.details.map((detail) => (
                <li key={detail}>{detail}</li>
              ))}
            </ul>
          )}
        </div>
      )}

      {(result?.vegetation ?? result?.water) && (
        <div className="flex flex-wrap items-center gap-1.5">
          <span className="text-[11px] font-medium text-zinc-500">Map overlay:</span>
          <button
            type="button"
            onClick={() => onOverlayChange(null)}
            className={clsx(
              "inline-flex items-center gap-1 rounded-full border px-2 py-0.5 text-[11px] font-medium",
              overlay === null ? "border-indigo-200 bg-indigo-50 text-indigo-700" : "border-zinc-200 text-zinc-500 hover:bg-zinc-50",
            )}
          >
            None
          </button>
          {(["vegetation", "water"] as ChangeType[]).map((type) => {
            const block = result?.[type];
            if (!block || block.status !== "completed" || !block.mask) return null;
            const active = overlay?.type === type;
            return (
              <button
                key={type}
                type="button"
                onClick={() => onOverlayChange({ type, mask: block.mask! })}
                className={clsx(
                  "inline-flex items-center gap-1 rounded-full border px-2 py-0.5 text-[11px] font-medium",
                  active
                    ? "border-indigo-200 bg-indigo-50 text-indigo-700"
                    : "border-zinc-200 text-zinc-500 hover:bg-zinc-50",
                )}
              >
                <MapIcon className="h-3 w-3" />
                {TYPE_LABELS[type]}
              </button>
            );
          })}
        </div>
      )}

      {result?.vegetation && <ChangeTypeCard block={result.vegetation} />}
      {result?.water && <ChangeTypeCard block={result.water} />}
      {result?.weather_contexts && result.weather_contexts.length > 0 && (
        <div className="space-y-2">
          <p className="text-[11px] font-semibold text-zinc-600">Weather context (descriptive only)</p>
          {result.weather_contexts.map((context: WeatherContext) => (
          <WeatherContextCard key={context.scene.scene_id} context={context} />
        ))}
        </div>
      )}

      {result?.warnings && result.warnings.length > 0 && (
        <ul className="list-inside list-disc text-[11px] text-amber-700">
          {result.warnings.map((warning) => (
            <li key={warning}>{warning}</li>
          ))}
        </ul>
      )}
    </div>
  );
}

const TYPE_LABELS: Record<ChangeType, string> = {
  vegetation: "Vegetation (NDVI)",
  water: "Water (NDWI)",
};

function SceneSelect({
  label,
  scenes,
  value,
  onChange,
}: {
  label: string;
  scenes: SatelliteScene[];
  value: string;
  onChange: (value: string) => void;
}) {
  return (
    <label className="inline-flex items-center gap-1 text-[11px] text-zinc-500">
      {label}
      <select
        value={value}
        onChange={(event) => onChange(event.target.value)}
        className="rounded-md border border-zinc-300 px-2 py-1 text-xs text-zinc-800"
        aria-label={`${label} satellite scene`}
      >
        <option value="">Select…</option>
        {scenes.map((scene) => (
          <option key={scene.id} value={String(scene.id)}>
            {scene.acquisition_date ?? "?"} · {scene.provider}
            {scene.cloud_cover !== null ? ` · ${scene.cloud_cover.toFixed(0)}% cloud` : ""}
          </option>
        ))}
      </select>
    </label>
  );
}

function SceneBands({
  label,
  scene,
  retrievals,
}: {
  label: string;
  scene: SatelliteScene | null;
  retrievals: RetrievalRecord[];
}) {
  if (!scene) return null;
  return (
    <span className="inline-flex flex-wrap items-center gap-1">
      <span className="text-[11px] font-medium text-zinc-500">
        {label} {scene.acquisition_date ?? "?"}:
      </span>
      {REQUIRED_BAND_KEYS.map((key) => {
        const ready = retrievals.some((record) => record.asset_key === key && record.status === "completed");
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
    </span>
  );
}

function ChangeTypeCard({ block }: { block: ChangeTypeBlock }) {
  if (block.status === "unavailable") {
    return (
      <div className="rounded-lg border border-amber-200 bg-amber-50 p-3">
        <p className="flex items-center gap-1.5 text-xs font-medium text-amber-800">
          <TriangleAlert className="h-4 w-4" />
          {TYPE_LABELS[block.type]} — unavailable
        </p>
        <p className="mt-1 text-[11px] text-amber-800">{block.unavailable?.reason}</p>
        {(block.unavailable?.details ?? []).length > 0 && (
          <ul className="mt-1 list-inside list-disc text-[11px] text-amber-700">
            {block.unavailable!.details.map((detail) => (
              <li key={detail}>{detail}</li>
            ))}
          </ul>
        )}
        {block.mask && (
          <p className="mt-1 text-[11px] text-amber-700">
            A partial invalid mask is available ({formatPct(block.comparison?.masking.comparison_valid_pct)} compared).
          </p>
        )}
      </div>
    );
  }

  if (!block.classification || !block.statistics) return null;
  const isVegetation = block.type === "vegetation";
  return (
    <div className="space-y-3 rounded-lg border border-zinc-200 bg-white p-3">
      <div className="flex flex-wrap items-center gap-2">
        <span className="rounded-full bg-green-100 px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wide text-green-800">
          completed
        </span>
        <span className="text-xs font-medium text-zinc-800">{TYPE_LABELS[block.type]}</span>
        <span className="text-[11px] text-zinc-500">{block.index?.formula}</span>
      </div>

      {block.mask && <ChangeLegend mask={block.mask} />}

      <ChangeStatisticsGrid block={block} />

      <ClassTable classification={block.classification} isVegetation={isVegetation} />

      <p className="text-[11px] leading-relaxed text-zinc-500">{block.classification.limitations_note}</p>

      {(block.warnings ?? []).length > 0 && (
        <ul className="list-inside list-disc text-[11px] text-amber-700">
          {block.warnings.map((warning) => (
            <li key={warning}>{warning}</li>
          ))}
        </ul>
      )}

      <div className="rounded-md bg-zinc-50 p-2 text-[11px] leading-relaxed text-zinc-500">
        <p>
          Alignment: {block.comparison?.alignment.mode}
          {block.comparison?.alignment.resampled_with
            ? ` · resampled after → before with ${block.comparison.alignment.resampled_with}`
            : ""}
          {" · "}
          {block.comparison?.alignment.crs} · {Math.round(block.comparison?.alignment.pixel_size_m[0] ?? 0)} m
        </p>
        <p>
          Compared {formatNumber(block.comparison?.masking.comparison_valid_pixels, 0)} /{" "}
          {formatNumber(block.comparison?.masking.total_pixels, 0)} pixels (
          {formatPct(block.comparison?.masking.comparison_valid_pct)}); invalid pixels never count as
          change.
        </p>
        <p className="text-zinc-400">
          NDVI/NDWI signal only — not a validated land-change model. Results are derived on demand
          and not persisted.
        </p>
      </div>
    </div>
  );
}

function ChangeLegend({ mask }: { mask: ChangeMask }) {
  const entries = Object.entries(mask.classes).sort(
    ([a], [b]) => Number(a) - Number(b),
  );
  return (
    <div className="flex flex-wrap items-center gap-x-3 gap-y-1">
      {entries.map(([code, label]) => (
        <span key={code} className="inline-flex items-center gap-1 text-[11px] text-zinc-600">
          <span className={clsx("h-2.5 w-2.5 rounded-full", CLASS_COLORS[code] ?? "bg-zinc-200")} />
          {label}
        </span>
      ))}
    </div>
  );
}

function ChangeStatisticsGrid({ block }: { block: ChangeTypeBlock }) {
  const statistics = block.statistics!;
  const before = statistics.before;
  const after = statistics.after;
  const delta = statistics.delta;
  return (
    <div className="space-y-2">
      <p className="text-[10px] font-semibold uppercase tracking-wide text-zinc-400">
        Index statistics over compared pixels
      </p>
      <div className="grid grid-cols-2 gap-2 sm:grid-cols-4">
        <StatGroup title="Before" block={before} />
        <StatGroup title="After" block={after} />
        {delta && <StatGroup title="Delta (after − before)" block={delta} />}
        {!delta && <div />}
      </div>
      <p className="text-[11px] text-zinc-500">{statistics.computed_over}</p>
    </div>
  );
}

function StatGroup({
  title,
  block,
}: {
  title: string;
  block: { mean: number | null; median: number | null; stddev: number | null; min: number | null; max: number | null; valid_pixels: number };
}) {
  return (
    <div className="rounded-md bg-zinc-50 px-2 py-1.5">
      <p className="text-[10px] font-semibold uppercase tracking-wide text-zinc-400">{title}</p>
      <p className="text-sm font-semibold text-zinc-800">{formatNumber(block.mean)}</p>
      <p className="text-[10px] text-zinc-500">median {formatNumber(block.median)} · σ {formatNumber(block.stddev)}</p>
      <p className="text-[10px] text-zinc-500">
        min {formatNumber(block.min)} · max {formatNumber(block.max)}
      </p>
    </div>
  );
}

function ClassTable({
  classification,
  isVegetation,
}: {
  classification: ChangeClassification;
  isVegetation: boolean;
}) {
  const entries = Object.entries(classification.classes);
  return (
    <div>
      <p className="mb-1 text-[10px] font-semibold uppercase tracking-wide text-zinc-400">
        Class areas — {classification.boundary}
      </p>
      <table className="w-full text-left text-[11px]">
        <thead>
          <tr className="border-b border-zinc-100 text-[10px] uppercase text-zinc-400">
            <th className="py-1 pr-2">Class</th>
            <th className="py-1 pr-2">Pixels</th>
            <th className="py-1 pr-2">% of compared</th>
            <th className="py-1">Area</th>
          </tr>
        </thead>
        <tbody>
          {entries.map(([name, summary]) => (
            <tr key={name} className="border-t border-zinc-100">
              <td className="py-1 pr-2 capitalize text-zinc-700">{name.replace(/_/g, " ")}</td>
              <td className="py-1 pr-2 text-zinc-600">{summary.pixel_count.toLocaleString()}</td>
              <td className="py-1 pr-2 text-zinc-600">{formatPct(summary.pixel_pct)}</td>
              <td className="py-1 text-zinc-600">{isVegetation ? formatArea(summary.area_m2) : "—"}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}