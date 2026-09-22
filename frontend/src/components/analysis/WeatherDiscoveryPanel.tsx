"use client";

import { useCallback, useState } from "react";
import clsx from "clsx";
import { Loader2, PackageOpen, RefreshCw, TriangleAlert } from "lucide-react";

import type {
  GeoJsonGeometry,
  WeatherDataTypes,
  WeatherObservationPoint,
  WeatherProviderStatus,
  WeatherUnits,
} from "@/lib/api/types";
import { listSessionObservations, searchWeather } from "@/lib/api/weather";
import { ApiError } from "@/lib/api/client";

export const WEATHER_VARIABLES: Array<{ key: string; label: string }> = [
  { key: "temperature_2m", label: "Temp (2m)" },
  { key: "temperature_2m_max", label: "Temp max" },
  { key: "temperature_2m_min", label: "Temp min" },
  { key: "apparent_temperature", label: "Feels like" },
  { key: "relative_humidity_2m", label: "Humidity" },
  { key: "dewpoint_2m", label: "Dew point" },
  { key: "precipitation", label: "Precipitation" },
  { key: "pressure_msl", label: "Pressure (MSL)" },
  { key: "surface_pressure", label: "Surface pressure" },
  { key: "wind_speed_10m", label: "Wind speed" },
  { key: "wind_direction_10m", label: "Wind direction" },
  { key: "cloud_cover", label: "Cloud cover" },
];

const DATA_TYPES: Array<{ value: WeatherDataTypes; label: string; needsDates: boolean }> = [
  { value: "current", label: "Current conditions", needsDates: false },
  { value: "forecast", label: "Forecast", needsDates: false },
  { value: "history", label: "History", needsDates: true },
  { value: "archive", label: "Archive", needsDates: true },
  { value: "reanalysis", label: "Reanalysis", needsDates: true },
  { value: "historical_forecast", label: "Historical forecast", needsDates: true },
];

const DEFAULT_VARIABLES = ["temperature_2m", "relative_humidity_2m"];

function formatTimestamp(observedAt: string, timezone: string): string {
  const when = new Date(observedAt);
  if (Number.isNaN(when.getTime())) return observedAt;
  return (
    when.toLocaleString([], { dateStyle: "short", timeStyle: "short" }) +
    ` (${timezone})`
  );
}

function formatValue(value: number | null): string {
  if (value === null) return "—";
  return String(Math.round(value * 10) / 10);
}

interface WeatherDiscoveryPanelProps {
  sessionId: number;
  aoi: GeoJsonGeometry | null;
  startDate: string;
  endDate: string;
}

export function WeatherDiscoveryPanel({
  sessionId,
  aoi,
  startDate,
  endDate,
}: WeatherDiscoveryPanelProps) {
  const [observations, setObservations] = useState<WeatherObservationPoint[] | null>(null);
  const [providers, setProviders] = useState<WeatherProviderStatus[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [truncated, setTruncated] = useState(false);
  const [dataType, setDataType] = useState<WeatherDataTypes>("current");
  const [units, setUnits] = useState<WeatherUnits>("metric");
  const [selectedVariables, setSelectedVariables] = useState<Set<string>>(
    () => new Set(DEFAULT_VARIABLES),
  );

  const activeType = DATA_TYPES.find((item) => item.value === dataType) ?? DATA_TYPES[0];
  const canSearch =
    aoi !== null && (!activeType.needsDates || (startDate !== "" && endDate !== ""));

  function toggleVariable(key: string) {
    setSelectedVariables((current) => {
      const next = new Set(current);
      if (next.has(key)) next.delete(key);
      else next.add(key);
      return next;
    });
  }

  const handleSearch = useCallback(async () => {
    if (!canSearch || selectedVariables.size === 0) return;
    setLoading(true);
    setError(null);
    try {
      const result = await searchWeather(sessionId, {
        aoi,
        start_date: startDate === "" ? null : startDate,
        end_date: endDate === "" ? null : endDate,
        data_type: dataType,
        units,
        variables: [...selectedVariables],
      });
      setObservations(result.observations);
      setProviders(result.providers);
      setTruncated(result.truncated);
    } catch (err) {
      setObservations(null);
      setProviders([]);
      setError(
        err instanceof ApiError ? err.message : "The weather data could not be retrieved.",
      );
    } finally {
      setLoading(false);
    }
  }, [canSearch, sessionId, aoi, startDate, endDate, dataType, units, selectedVariables]);

  async function handleLoadSaved() {
    setLoading(true);
    setError(null);
    try {
      const saved = await listSessionObservations(sessionId);
      setObservations(saved);
      setProviders([]);
      setTruncated(false);
    } catch (err) {
      setObservations(null);
      setProviders([]);
      setError(
        err instanceof ApiError ? err.message : "The saved observations could not be loaded.",
      );
    } finally {
      setLoading(false);
    }
  }

  const groups = new Map<string, WeatherObservationPoint[]>();
  for (const obs of observations ?? []) {
    const list = groups.get(obs.variable) ?? [];
    list.push(obs);
    groups.set(obs.variable, list);
  }

  return (
    <div className="space-y-3">
      <div className="flex flex-wrap items-center gap-2">
        <select
          value={dataType}
          onChange={(event) => setDataType(event.target.value as WeatherDataTypes)}
          className="rounded-md border border-zinc-300 px-2 py-1 text-xs text-zinc-800"
        >
          {DATA_TYPES.map((item) => (
            <option key={item.value} value={item.value}>
              {item.label}
            </option>
          ))}
        </select>
        <select
          value={units}
          onChange={(event) => setUnits(event.target.value as WeatherUnits)}
          className="rounded-md border border-zinc-300 px-2 py-1 text-xs text-zinc-800"
        >
          <option value="metric">Metric</option>
          <option value="imperial">Imperial</option>
        </select>
        <button
          type="button"
          onClick={() => void handleSearch()}
          disabled={!canSearch || loading || selectedVariables.size === 0}
          className="inline-flex items-center gap-1.5 rounded-lg bg-indigo-600 px-3 py-1.5 text-xs font-medium text-white transition hover:bg-indigo-700 disabled:cursor-not-allowed disabled:opacity-50"
        >
          {loading ? (
            <Loader2 className="h-3.5 w-3.5 animate-spin" />
          ) : (
            <PackageOpen className="h-3.5 w-3.5" />
          )}
          {loading ? "Fetching..." : "Fetch weather"}
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

      <div className="flex flex-wrap gap-1.5">
        {WEATHER_VARIABLES.map((item) => {
          const active = selectedVariables.has(item.key);
          return (
            <button
              key={item.key}
              type="button"
              onClick={() => toggleVariable(item.key)}
              className={clsx(
                "rounded-full border px-2 py-0.5 text-[11px] font-medium transition",
                active
                  ? "border-indigo-200 bg-indigo-50 text-indigo-700"
                  : "border-zinc-200 text-zinc-500 hover:border-zinc-300",
              )}
            >
              {item.label}
            </button>
          );
        })}
      </div>

      {activeType.needsDates && (
        <p className="text-xs text-zinc-500">
          {dataType} requires a start and end date on the analysis session.
        </p>
      )}
      {!canSearch && aoi === null && (
        <p className="text-xs text-amber-700">Draw or select an AOI before fetching weather.</p>
      )}
      {canSearch && selectedVariables.size === 0 && (
        <p className="text-xs text-amber-700">Select at least one variable.</p>
      )}
      {error && <p className="text-xs text-red-600">{error}</p>}
      {truncated && (
        <p className="text-xs text-amber-700">Observations were truncated to the maximum.</p>
      )}
      {observations && observations.length === 0 && !loading && (
        <p className="text-xs text-zinc-500">
          No weather observations are stored for this session yet.
        </p>
      )}

      {providers.length > 0 && (
        <div className="flex flex-wrap gap-1.5">
          {providers.map((status) => (
            <span
              key={status.provider}
              className={clsx(
                "inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wide",
                status.error
                  ? "bg-red-50 text-red-700"
                  : status.observations > 0
                    ? "bg-emerald-50 text-emerald-700"
                    : "bg-zinc-100 text-zinc-500",
              )}
            >
              {status.provider}
              {status.error ? (
                <span className="inline-flex cursor-default" title={status.error}>
                  <TriangleAlert className="h-3 w-3" />
                  {status.error}
                </span>
              ) : (
                <span>· {status.observations} obs</span>
              )}
            </span>
          ))}
        </div>
      )}

      {observations && observations.length > 0 && (
        <div className="space-y-3">
          {[...groups.entries()].map(([variable, points]) => {
            const sorted = [...points].sort((a, b) =>
              a.observed_at.localeCompare(b.observed_at),
            );
            const sample = sorted[0];
            return (
              <div key={variable} className="rounded-lg border border-zinc-200 bg-white p-3">
                <div className="flex flex-wrap items-center gap-2">
                  <span className="rounded-full bg-indigo-50 px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wide text-indigo-700">
                    {variable}
                  </span>
                  <span className="text-[11px] text-zinc-500">
                    {sample.provider} · {sample.data_type}
                    {sample.model ? ` · ${sample.model}` : ""} · {sorted.length} point(s)
                  </span>
                </div>
                <table className="mt-2 w-full text-left text-[11px]">
                  <thead>
                    <tr className="border-b border-zinc-100 text-[10px] uppercase text-zinc-400">
                      <th className="py-1 pr-2 font-medium">Time</th>
                      <th className="py-1 pr-2 font-medium">Value</th>
                      <th className="py-1 font-medium">Source</th>
                    </tr>
                  </thead>
                  <tbody>
                    {sorted.map((obs) => (
                      <tr key={obs.id} className="border-t border-zinc-100">
                        <td className="py-1 pr-2 text-zinc-600">
                          {formatTimestamp(obs.observed_at, obs.timezone)}
                        </td>
                        <td className="py-1 pr-2">
                          <span className="font-medium text-zinc-900">
                            {formatValue(obs.value)}
                          </span>
                          <span className={clsx("ml-1", clsx(obs.units && "text-zinc-500"))}>
                            {obs.units ?? ""}
                          </span>
                        </td>
                        <td className="py-1 text-zinc-500">
                          {obs.latitude.toFixed(3)}, {obs.longitude.toFixed(3)}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
                {sample.attribution && (
                  <p className="mt-2 text-[10px] text-zinc-400">{sample.attribution}</p>
                )}
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}