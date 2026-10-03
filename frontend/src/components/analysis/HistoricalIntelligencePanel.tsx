"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import clsx from "clsx";
import {
  CalendarClock,
  History,
  Loader2,
  Map as MapIcon,
  TriangleAlert,
} from "lucide-react";

import { analyzeHistorical } from "@/lib/api/historical";
import { ApiError } from "@/lib/api/client";
import { listSessionScenes } from "@/lib/api/satellite";
import type {
  ChangeType,
  HistoricalEvent,
  HistoricalObservation,
  HistoricalResponse,
  HistoricalTrend,
  WeatherContext,
} from "@/lib/api/types";
import type { ChangeOverlay } from "./ChangeDetectionPanel";
import { WeatherContextCard } from "./WeatherContextCard";

const TYPE_LABELS: Record<ChangeType, string> = {
  vegetation: "Vegetation (NDVI)",
  water: "Water (NDWI)",
};

const EVENT_STYLES: Record<string, string> = {
  vegetation_increase: "border-emerald-200 bg-emerald-50 text-emerald-800",
  vegetation_decrease: "border-rose-200 bg-rose-50 text-rose-800",
  vegetation_stable: "border-zinc-200 bg-zinc-50 text-zinc-700",
  water_expansion: "border-blue-200 bg-blue-50 text-blue-800",
  water_reduction: "border-amber-200 bg-amber-50 text-amber-800",
  water_stable: "border-zinc-200 bg-zinc-50 text-zinc-700",
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

interface HistoricalIntelligencePanelProps {
  sessionId: number;
  aoiPresent: boolean;
  overlay: ChangeOverlay | null;
  onOverlayChange: (overlay: ChangeOverlay | null) => void;
}

export function HistoricalIntelligencePanel({
  sessionId,
  aoiPresent,
  overlay,
  onOverlayChange,
}: HistoricalIntelligencePanelProps) {
  const [sceneCount, setSceneCount] = useState<number | null>(null);
  const [types, setTypes] = useState<ChangeType[]>(["vegetation", "water"]);
  const [maskClouds, setMaskClouds] = useState(true);
  const [includeWeather, setIncludeWeather] = useState(true);
  const [vegetationThreshold, setVegetationThreshold] = useState("0.10");
  const [waterThreshold, setWaterThreshold] = useState("0");
  const [startDate, setStartDate] = useState("");
  const [endDate, setEndDate] = useState("");
  const [result, setResult] = useState<HistoricalResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const vegThreshold = Number.parseFloat(vegetationThreshold);
  const waterThresholdValue = Number.parseFloat(waterThreshold);
  const validVegThreshold = Number.isFinite(vegThreshold) && vegThreshold > 0 && vegThreshold <= 2;
  const validWaterThreshold =
    Number.isFinite(waterThresholdValue) &&
    waterThresholdValue >= -1 &&
    waterThresholdValue <= 1;
  const rangeProvided = startDate !== "" || endDate !== "";
  const validRange =
    (!rangeProvided || (startDate !== "" && endDate !== "")) &&
    (startDate === "" || endDate === "" || startDate <= endDate);

  useEffect(() => {
    let cancelled = false;
    async function load() {
      try {
        const scenes = await listSessionScenes(sessionId);
        if (!cancelled) setSceneCount(scenes.length);
      } catch {
        if (!cancelled) setSceneCount(null);
      }
    }
    void load();
    return () => {
      cancelled = true;
    };
  }, [sessionId]);

  function toggleType(type: ChangeType) {
    setTypes((current) =>
      current.includes(type) ? current.filter((item) => item !== type) : [...current, type],
    );
  }

  const canAnalyze =
    aoiPresent &&
    types.length > 0 &&
    validRange &&
    !loading;

  const handleAnalyze = useCallback(async () => {
    if (!canAnalyze) return;
    setLoading(true);
    setError(null);
    try {
      const response = await analyzeHistorical(sessionId, {
        types,
        mask_clouds: maskClouds,
        include_weather: includeWeather,
        vegetation_threshold: validVegThreshold ? vegThreshold : null,
        water_threshold: validWaterThreshold ? waterThresholdValue : null,
        start_date: rangeProvided ? startDate : null,
        end_date: rangeProvided ? endDate : null,
      });
      setResult(response);
      const first = response.events.find(
        (event) => event.status === "completed" && event.mask !== null,
      );
      onOverlayChange(first ? { type: first.type, mask: first.mask! } : null);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "The historical timeline could not be built.");
    } finally {
      setLoading(false);
    }
  }, [
    canAnalyze,
    sessionId,
    types,
    maskClouds,
    includeWeather,
    validVegThreshold,
    vegThreshold,
    validWaterThreshold,
    waterThresholdValue,
    rangeProvided,
    startDate,
    endDate,
    onOverlayChange,
  ]);

  const hasTimeline = (result?.observations.length ?? 0) > 0;
  const hasEvents = (result?.events.length ?? 0) > 0;

  return (
    <div className="space-y-3">
      <div className="flex flex-wrap items-center gap-3">
        <div className="flex items-center gap-2 text-[11px] text-zinc-600">
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

      <div className="flex flex-wrap items-center gap-3">
        <span className="inline-flex items-center gap-1 text-[11px] font-medium text-zinc-500">
          <CalendarClock className="h-3.5 w-3.5" /> Date range (optional, within the session)
        </span>
        <label className="text-[11px] text-zinc-600">
          from&nbsp;
          <input
            type="date"
            value={startDate}
            onChange={(event) => setStartDate(event.target.value)}
            className="rounded-md border border-zinc-300 px-1.5 py-0.5 text-xs"
          />
        </label>
        <label className="text-[11px] text-zinc-600">
          to&nbsp;
          <input
            type="date"
            value={endDate}
            onChange={(event) => setEndDate(event.target.value)}
            className="rounded-md border border-zinc-300 px-1.5 py-0.5 text-xs"
          />
        </label>
        {(startDate !== "" || endDate !== "") && (
          <button
            type="button"
            onClick={() => {
              setStartDate("");
              setEndDate("");
            }}
            className="rounded-full border border-zinc-200 px-2 py-0.5 text-[11px] font-medium text-zinc-500 hover:bg-zinc-50"
          >
            Use session range
          </button>
        )}
      </div>
      {!validRange && (
        <p className="text-xs text-amber-700">
          Provide both a start and an end date, with the start on or before the end.
        </p>
      )}

      <div className="flex flex-wrap items-center gap-2">
        <button
          type="button"
          onClick={() => void handleAnalyze()}
          disabled={!canAnalyze}
          className="inline-flex items-center gap-1.5 rounded-lg bg-indigo-600 px-3 py-1.5 text-xs font-medium text-white transition hover:bg-indigo-700 disabled:cursor-not-allowed disabled:opacity-50"
        >
          {loading ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <History className="h-3.5 w-3.5" />}
          {loading ? "Building timeline..." : "Build timeline"}
        </button>
        {sceneCount !== null && (
          <span className="text-[11px] text-zinc-500">
            {sceneCount} discovered scene{sceneCount === 1 ? "" : "s"} in this session.
          </span>
        )}
      </div>

      {!aoiPresent && (
        <p className="text-xs text-amber-700">Draw or select an AOI before building a timeline.</p>
      )}
      {aoiPresent && sceneCount === 0 && (
        <p className="text-xs text-amber-700">
          This session has no discovered satellite scenes yet — use the Scene panel to search and
          download bands.
        </p>
      )}

      {error && <p className="text-xs text-red-600">{error}</p>}

      {result && result.status === "unavailable" && (
        <div className="rounded-lg border border-amber-200 bg-amber-50 p-3">
          <p className="flex items-center gap-1.5 text-xs font-medium text-amber-800">
            <TriangleAlert className="h-4 w-4" /> Historical timeline unavailable
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

      {result && (
        <>
          <CoverageCard result={result} />

          <p className="text-[11px] leading-relaxed text-zinc-600">{result.summary}</p>

          {hasTimeline && (
            <div className="space-y-3">
              <SeriesChart
                title="Mean NDVI per observation (vegetation)"
                unit="NDVI"
                points={result.observations.map((observation) => ({
                  label: observation.date,
                  value:
                    observation.vegetation?.status === "completed"
                      ? observation.vegetation.statistics?.mean ?? null
                      : null,
                }))}
              />
              <SeriesChart
                title="Water extent per observation (NDWI)"
                unit="area"
                points={result.observations.map((observation) => ({
                  label: observation.date,
                  value:
                    observation.water?.status === "completed"
                      ? observation.water.water?.area_m2 ?? null
                      : null,
                }))}
                format={(value) => formatArea(value)}
              />
            </div>
          )}

          {hasTimeline && <ObservationTable observations={result.observations} />}

          {hasEvents && (
            <div className="space-y-2">
              <p className="text-[11px] font-semibold text-zinc-600">
                Observed change between consecutive observations
              </p>
              <div className="flex flex-wrap items-center gap-1.5">
                <span className="text-[11px] font-medium text-zinc-500">Map overlay:</span>
                <button
                  type="button"
                  onClick={() => onOverlayChange(null)}
                  className={clsx(
                    "inline-flex items-center gap-1 rounded-full border px-2 py-0.5 text-[11px] font-medium",
                    overlay === null
                      ? "border-indigo-200 bg-indigo-50 text-indigo-700"
                      : "border-zinc-200 text-zinc-500 hover:bg-zinc-50",
                  )}
                >
                  None
                </button>
                {result.events
                  .filter((event) => event.status === "completed" && event.mask !== null)
                  .map((event) => {
                    const active =
                      overlay !== null && overlay.type === event.type &&
                      overlay.mask.data_uri === event.mask!.data_uri;
                    return (
                      <button
                        key={`${event.type}-${event.start_date}-${event.end_date}`}
                        type="button"
                        onClick={() => onOverlayChange({ type: event.type, mask: event.mask! })}
                        className={clsx(
                          "inline-flex items-center gap-1 rounded-full border px-2 py-0.5 text-[11px] font-medium",
                          active
                            ? "border-indigo-200 bg-indigo-50 text-indigo-700"
                            : "border-zinc-200 text-zinc-500 hover:bg-zinc-50",
                        )}
                      >
                        <MapIcon className="h-3 w-3" />
                        {TYPE_LABELS[event.type]} {event.start_date} → {event.end_date}
                      </button>
                    );
                  })}
              </div>
              {result.events.map((event) => (
                <EventCard key={`${event.type}-${event.start_date}-${event.end_date}`} event={event} />
              ))}
            </div>
          )}

          {result.types_requested.map((type) => {
            const trend = result.trends[type];
            return trend ? <TrendCard key={type} trend={trend} /> : null;
          })}

          {result.weather_contexts && result.weather_contexts.length > 0 && (
            <div className="space-y-2">
              <p className="text-[11px] font-semibold text-zinc-600">
                Weather context per observation (descriptive only)
              </p>
              {result.weather_contexts.map((context: WeatherContext) => (
                <WeatherContextCard key={context.scene.scene_id} context={context} />
              ))}
            </div>
          )}

          {result.warnings.length > 0 && (
            <ul className="list-inside list-disc text-[11px] text-amber-700">
              {result.warnings.map((warning) => (
                <li key={warning}>{warning}</li>
              ))}
            </ul>
          )}

          <div className="rounded-md bg-zinc-50 p-2 text-[11px] leading-relaxed text-zinc-500">
            <p>
              {result.coverage.observation_count} observation(s); ordered by{" "}
              {result.coverage.ordered_by}; {result.coverage.compared_pairs} compared pair(s)
              {result.coverage.same_day_pairs_skipped > 0
                ? `; ${result.coverage.same_day_pairs_skipped} same-day pair(s) not compared`
                : ""}
              .
            </p>
            <p className="text-zinc-400">
              Descriptive and analytical only — no forecasting and no causal attribution.
              Observations are derived on demand from the bands downloaded for this session and are
              not persisted.
            </p>
          </div>
        </>
      )}
    </div>
  );
}

function CoverageCard({ result }: { result: HistoricalResponse }) {
  const coverage = result.coverage;
  return (
    <div className="space-y-2 rounded-lg border border-zinc-200 bg-white p-3">
      <div className="flex flex-wrap items-center gap-2">
        <span
          className={clsx(
            "rounded-full px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wide",
            result.status === "completed"
              ? "bg-green-100 text-green-800"
              : "bg-amber-100 text-amber-800",
          )}
        >
          {result.status}
        </span>
        <span className="text-xs font-medium text-zinc-800">Timeline coverage</span>
        {coverage.limited && (
          <span className="rounded-full bg-amber-100 px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wide text-amber-800">
            limited evidence
          </span>
        )}
      </div>
      <div className="grid grid-cols-2 gap-2 sm:grid-cols-4">
        <Metric label="Observations" value={String(coverage.observation_count)} />
        <Metric
          label="Span"
          value={
            coverage.temporal_span_days === null
              ? "—"
              : `${coverage.temporal_span_days} day(s)`
          }
        />
        <Metric label="Compared pairs" value={String(coverage.compared_pairs)} />
        <Metric label="Same-day skipped" value={String(coverage.same_day_pairs_skipped)} />
      </div>
      <p className="text-[11px] text-zinc-500">
        {coverage.start_date ?? "—"} → {coverage.end_date ?? "—"} · ordered by{" "}
        {coverage.ordered_by}
      </p>
      {coverage.gaps.length > 0 && (
        <ul className="list-inside list-disc text-[11px] text-amber-700">
          {coverage.gaps.map((gap) => (
            <li key={`${gap.from_date}-${gap.to_date}`}>
              Temporal gap of {gap.gap_days} day(s) between {gap.from_date} and {gap.to_date} —
              reported, never interpolated.
            </li>
          ))}
        </ul>
      )}
      <ul className="list-inside list-disc text-[11px] text-zinc-500">
        {coverage.notes.map((note) => (
          <li key={note}>{note}</li>
        ))}
      </ul>
    </div>
  );
}

function Metric({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-md bg-zinc-50 px-2 py-1.5">
      <p className="text-[10px] font-semibold uppercase tracking-wide text-zinc-400">{label}</p>
      <p className="text-sm font-semibold text-zinc-800">{value}</p>
    </div>
  );
}

interface ChartPoint {
  label: string;
  value: number | null;
}

/**
 * Observed-points-only chart. Observations are placed on an even (categorical)
 * axis so irregular sampling is never drawn as a regular cadence, and a
 * connecting segment is drawn only between two adjacent *measured* points —
 * nothing is extrapolated and unmeasured observations are never filled in.
 */
function SeriesChart({
  title,
  unit,
  points,
  format,
}: {
  title: string;
  unit: string;
  points: ChartPoint[];
  format?: (value: number) => string;
}) {
  const width = 340;
  const height = 120;
  const padLeft = 44;
  const padRight = 10;
  const padTop = 10;
  const padBottom = 22;

  const measuredCount = points.filter((point) => point.value !== null).length;
  const geometry = useMemo(() => {
    const measured = points.filter((point) => point.value !== null);
    if (measured.length === 0) return null;
    const values = measured.map((point) => point.value as number);
    let min = Math.min(...values);
    let max = Math.max(...values);
    if (min === max) {
      const pad = Math.abs(min) > 0 ? Math.abs(min) * 0.1 : 0.5;
      min -= pad;
      max += pad;
    }
    const innerWidth = width - padLeft - padRight;
    const innerHeight = height - padTop - padBottom;
    const x = (index: number) =>
      points.length > 1
        ? padLeft + (index * innerWidth) / (points.length - 1)
        : padLeft + innerWidth / 2;
    const y = (value: number) =>
      padTop + innerHeight - ((value - min) / (max - min)) * innerHeight;
    const segments: string[] = [];
    for (let index = 1; index < points.length; index += 1) {
      const previous = points[index - 1];
      const current = points[index];
      if (previous.value !== null && current.value !== null) {
        segments.push(`${x(index - 1)},${y(previous.value)} ${x(index)},${y(current.value)}`);
      }
    }
    return { min, max, x, y, segments };
  }, [points]);

  return (
    <div className="rounded-lg border border-zinc-200 bg-white p-3">
      <p className="text-[10px] font-semibold uppercase tracking-wide text-zinc-400">{title}</p>
      {!geometry ? (
        <p className="mt-1 text-[11px] text-zinc-500">
          Not measured — no completed observations of this type ({unit}).
        </p>
      ) : (
        <>
          <svg viewBox={`0 0 ${width} ${height}`} className="mt-1 w-full max-w-lg" role="img" aria-label={title}>
            <line
              x1={padLeft}
              y1={height - padBottom}
              x2={width - padRight}
              y2={height - padBottom}
              stroke="#e4e4e7"
              strokeWidth="1"
            />
            {geometry.segments.map((segment) => (
              <polyline
                key={segment}
                points={segment}
                fill="none"
                stroke="#a1a1aa"
                strokeWidth="1.5"
              />
            ))}
            {points.map((point, index) =>
              point.value === null ? null : (
                <g key={point.label}>
                  <circle
                    cx={geometry.x(index)}
                    cy={geometry.y(point.value)}
                    r="3"
                    fill="#4f46e5"
                  />
                  <text
                    x={geometry.x(index)}
                    y={height - padBottom + 12}
                    textAnchor="middle"
                    fontSize="9"
                    fill="#71717a"
                  >
                    {point.label}
                  </text>
                </g>
              ),
            )}
            <text x={2} y={padTop + 6} fontSize="9" fill="#a1a1aa">
              {(format ?? ((value: number) => formatNumber(value)))(geometry.max)}
            </text>
            <text x={2} y={height - padBottom} fontSize="9" fill="#a1a1aa">
              {(format ?? ((value: number) => formatNumber(value)))(geometry.min)}
            </text>
          </svg>
          <p className="mt-1 text-[11px] text-zinc-500">
            Observed points only ({measuredCount} of {points.length}); gaps are never interpolated.
          </p>
        </>
      )}
    </div>
  );
}

function ObservationTable({ observations }: { observations: HistoricalObservation[] }) {
  return (
    <div className="rounded-lg border border-zinc-200 bg-white p-3">
      <p className="mb-1 text-[10px] font-semibold uppercase tracking-wide text-zinc-400">
        Observations — oldest → newest
      </p>
      <table className="w-full text-left text-[11px]">
        <thead>
          <tr className="border-b border-zinc-100 text-[10px] uppercase text-zinc-400">
            <th className="py-1 pr-2">Date</th>
            <th className="py-1 pr-2">Mean NDVI</th>
            <th className="py-1 pr-2">Valid px</th>
            <th className="py-1 pr-2">Water px</th>
            <th className="py-1 pr-2">Water area</th>
            <th className="py-1">Weather</th>
          </tr>
        </thead>
        <tbody>
          {observations.map((observation) => {
            const vegetation = observation.vegetation;
            const water = observation.water;
            return (
              <tr key={`${observation.date}-${observation.scene.id}`} className="border-t border-zinc-100">
                <td className="py-1 pr-2 text-zinc-700">
                  {observation.date}
                  {observation.scene.cloud_cover !== null
                    ? ` · ${observation.scene.cloud_cover.toFixed(0)}% cloud`
                    : ""}
                </td>
                <td className="py-1 pr-2 text-zinc-600">
                  {vegetation?.status === "completed"
                    ? formatNumber(vegetation.statistics?.mean)
                    : unavailableLabel(vegetation?.unavailable?.code)}
                </td>
                <td className="py-1 pr-2 text-zinc-600">
                  {vegetation?.status === "completed"
                    ? formatPct(vegetation.statistics?.valid_pixel_pct)
                    : "—"}
                </td>
                <td className="py-1 pr-2 text-zinc-600">
                  {water?.status === "completed"
                    ? (water.water?.pixel_count ?? 0).toLocaleString()
                    : unavailableLabel(water?.unavailable?.code)}
                </td>
                <td className="py-1 pr-2 text-zinc-600">
                  {water?.status === "completed" ? formatArea(water.water?.area_m2) : "—"}
                </td>
                <td className="py-1 text-zinc-600">{weatherLabel(observation.weather_context)}</td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}

function EventCard({ event }: { event: HistoricalEvent }) {
  if (event.status === "unavailable" || !event.classification) {
    return (
      <div className="space-y-1 rounded-lg border border-amber-200 bg-amber-50 p-3">
        <p className="flex items-center gap-1.5 text-xs font-medium text-amber-800">
          <TriangleAlert className="h-4 w-4" />
          {TYPE_LABELS[event.type]} — {event.start_date} → {event.end_date}: unavailable
        </p>
        <p className="text-[11px] text-amber-800">{event.unavailable?.reason}</p>
        {(event.unavailable?.details ?? []).length > 0 && (
          <ul className="list-inside list-disc text-[11px] text-amber-700">
            {event.unavailable!.details.map((detail) => (
              <li key={detail}>{detail}</li>
            ))}
          </ul>
        )}
      </div>
    );
  }

  const classification = event.classification;
  const style = EVENT_STYLES[classification.event] ?? "border-zinc-200 bg-zinc-50 text-zinc-700";
  return (
    <div className="space-y-1.5 rounded-lg border border-zinc-200 bg-white p-3">
      <div className="flex flex-wrap items-center gap-2">
        <span className={clsx("rounded-full border px-2 py-0.5 text-[10px] font-semibold", style)}>
          {classification.event.replace(/_/g, " ")}
        </span>
        <span className="text-xs font-medium text-zinc-800">
          {TYPE_LABELS[event.type]} · {event.start_date} → {event.end_date}
        </span>
        <span className="text-[11px] text-zinc-500">{event.gap_days} day(s) apart</span>
      </div>
      <p className="text-[11px] text-zinc-700">{classification.label}</p>
      <p className="text-[11px] text-zinc-500">{classification.basis}</p>
      {event.type === "vegetation" && classification.region && (
        <p className="text-[11px] text-zinc-600">
          Increased {formatArea(classification.region.increased?.area_m2)} · decreased{" "}
          {formatArea(classification.region.decreased?.area_m2)} · changed total{" "}
          {formatArea(classification.region.changed_total?.area_m2)}
        </p>
      )}
      {event.type === "water" && classification.water_extent && (
        <p className="text-[11px] text-zinc-600">
          Water pixels {classification.water_extent.before_pixels.toLocaleString()} →{" "}
          {classification.water_extent.after_pixels.toLocaleString()} (delta{" "}
          {classification.water_extent.delta_pixels.toLocaleString()}); added{" "}
          {formatArea(classification.water_extent.added?.area_m2)} · lost{" "}
          {formatArea(classification.water_extent.lost?.area_m2)}
        </p>
      )}
      <p className="text-[11px] text-zinc-500">
        Threshold {formatNumber(classification.threshold)} · {classification.boundary} ·{" "}
        {classification.comparison_pixels.toLocaleString()} compared pixels (
        {formatPct(classification.comparison_valid_pct)}).
      </p>
      <p className="text-[11px] leading-relaxed text-zinc-500">
        {classification.limitations_note}
      </p>
      {event.warnings.length > 0 && (
        <ul className="list-inside list-disc text-[11px] text-amber-700">
          {event.warnings.map((warning) => (
            <li key={warning}>{warning}</li>
          ))}
        </ul>
      )}
    </div>
  );
}

function TrendCard({ trend }: { trend: HistoricalTrend }) {
  return (
    <div className="rounded-lg border border-zinc-200 bg-white p-3">
      <p className="text-[10px] font-semibold uppercase tracking-wide text-zinc-400">
        Trend — {TYPE_LABELS[trend.type] ?? trend.type} (descriptive)
      </p>
      {trend.observations === 0 ? (
        <p className="mt-1 text-[11px] text-zinc-500">{trend.basis}</p>
      ) : (
        <>
          <div className="mt-1 grid grid-cols-2 gap-2 sm:grid-cols-4">
            <Metric
              label="First"
              value={`${formatNumber(trend.first?.value ?? null)} (${trend.first?.date ?? "—"})`}
            />
            <Metric
              label="Latest"
              value={`${formatNumber(trend.latest?.value ?? null)} (${trend.latest?.date ?? "—"})`}
            />
            <Metric label="Min" value={`${formatNumber(trend.minimum?.value ?? null)}`} />
            <Metric label="Max" value={`${formatNumber(trend.maximum?.value ?? null)}`} />
          </div>
          <p className="mt-1 text-[11px] text-zinc-600">
            Change {formatNumber(trend.absolute_change, 4)}
            {trend.relative_change_pct === null
              ? ""
              : ` (${formatNumber(trend.relative_change_pct, 2)}%)`}{" "}
            over {trend.observations} observation(s).
          </p>
          <p className="text-[11px] text-zinc-500">{trend.basis}</p>
          <p className="mt-1 text-[11px] leading-relaxed text-zinc-400">{trend.note}</p>
        </>
      )}
    </div>
  );
}

function unavailableLabel(code: string | undefined): string {
  if (!code) return "—";
  return `unavailable (${code.replace(/_/g, " ")})`;
}

function weatherLabel(context: WeatherContext | null | undefined): string {
  if (!context) return "—";
  return context.status === "available" ? context.status : `unavailable`;
}