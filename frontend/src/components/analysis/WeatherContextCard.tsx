"use client";

import clsx from "clsx";
import { CloudSun, TriangleAlert } from "lucide-react";

import type { WeatherContext, WeatherContextVariable } from "@/lib/api/types";

const VARIABLE_LABELS: Record<string, string> = {
  temperature_2m: "Mean temperature",
  apparent_temperature: "Mean apparent temperature",
  temperature_2m_max: "Max temperature",
  temperature_2m_min: "Min temperature",
  relative_humidity_2m: "Mean humidity",
  dewpoint_2m: "Mean dew point",
  precipitation: "Precipitation during period",
  rain: "Rain during period",
  showers: "Showers during period",
  snowfall: "Snowfall during period",
  weather_code: "Weather code",
  cloud_cover: "Mean cloud cover",
  pressure_msl: "Mean sea-level pressure",
  surface_pressure: "Mean surface pressure",
  wind_speed_10m: "Mean wind speed",
  wind_direction_10m: "Wind direction",
  wind_gusts_10m: "Max wind gust",
  soil_temperature_0cm: "Mean soil temp (0 cm)",
  soil_moisture_0to10cm: "Mean soil moisture (0–10 cm)",
  et0_fao_evapotranspiration: "Evapotranspiration (period)",
};

function formatValue(value: number | null | undefined): string {
  if (value === null || value === undefined || Number.isNaN(value)) return "Unavailable";
  const rounded = Math.round(value * 10) / 10;
  return Number.isInteger(rounded) ? String(rounded) : rounded.toFixed(1);
}

interface WeatherContextCardProps {
  context: WeatherContext | null | undefined;
  className?: string;
}

export function WeatherContextCard({ context, className }: WeatherContextCardProps) {
  if (!context) return null;

  return (
    <div
      className={clsx(
        "rounded-lg border border-sky-200 bg-sky-50/50 p-3",
        className,
      )}
    >
      <div className="flex items-center gap-1.5">
        <CloudSun className="h-4 w-4 text-sky-600" />
        <p className="text-xs font-medium text-zinc-800">Weather context</p>
        {context.attribution && (
          <span className="ml-auto text-[10px] text-zinc-400">{context.attribution}</span>
        )}
      </div>

      {context.period && (
        <p className="mt-1 text-[11px] text-zinc-500">
          Observed conditions {context.status === "available" ? "corresponding to" : "around"} the
          satellite observation of {context.satellite_observation} · window {context.period.start} to{" "}
          {context.period.end}
          {context.period.days_before === 0 && context.period.days_after === 0 ? " (same-day)" : ""}
        </p>
      )}

      {context.status === "unavailable" && context.unavailable && (
        <div className="mt-2 rounded-md border border-amber-200 bg-amber-50 p-2">
          <p className="flex items-center gap-1.5 text-[11px] font-medium text-amber-800">
            <TriangleAlert className="h-3.5 w-3.5" /> No weather observations available for this period.
          </p>
          {context.unavailable.details.length > 0 && (
            <ul className="mt-1 list-inside list-disc text-[11px] text-amber-700">
              {context.unavailable.details.map((detail) => (
                <li key={detail}>{detail}</li>
              ))}
            </ul>
          )}
        </div>
      )}

      {context.status === "available" && context.variables.length > 0 && (
        <div className="mt-2 grid grid-cols-2 gap-x-4 gap-y-1.5 sm:grid-cols-3">
          {context.variables.map((variable) => (
            <ContextVariable key={variable.name} variable={variable} />
          ))}
        </div>
      )}

      {context.status === "available" && context.partial && (
        <p className="mt-2 text-[11px] text-amber-700">
          Weather coverage is incomplete for the selected period.
        </p>
      )}

      {(context.warnings ?? []).length > 0 && (
        <ul className="mt-2 list-inside list-disc text-[11px] text-amber-700">
          {context.warnings.map((warning) => (
            <li key={warning}>{warning}</li>
          ))}
        </ul>
      )}

      {context.status === "available" && (
        <p className="mt-2 text-[10px] leading-relaxed text-zinc-400">
          {context.observation_count} stored observation
          {context.observation_count === 1 ? "" : "s"} ·{" "}
          {context.providers.join(", ")} · completeness {context.completeness_pct}%
          <br />
          {context.note}
        </p>
      )}
    </div>
  );
}

function ContextVariable({ variable }: { variable: WeatherContextVariable }) {
  const label = VARIABLE_LABELS[variable.name] ?? variable.name.replace(/_/g, " ");
  const missing = variable.value === null || variable.value === undefined || !variable.available;
  return (
    <div className="min-w-0">
      <p className="truncate text-[10px] font-semibold uppercase tracking-wide text-zinc-400" title={label}>
        {label}
      </p>
      <p
        className={clsx(
          "text-sm font-semibold",
          missing ? "text-zinc-400" : "text-zinc-800",
        )}
      >
        {missing ? "Unavailable" : formatValue(variable.value)}
        {!missing && variable.units ? (
          <span className="ml-1 text-[10px] font-normal text-zinc-400">{variable.units}</span>
        ) : null}
      </p>
      {!missing && variable.coverage_pct < 100 && (
        <p className="text-[10px] text-zinc-400">
          {variable.sample_count} of {variable.expected_count} samples
        </p>
      )}
    </div>
  );
}