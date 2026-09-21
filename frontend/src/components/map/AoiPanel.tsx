"use client";

import { Download, Eraser, FileUp, PencilRuler, ClipboardPaste, X } from "lucide-react";
import { ChangeEvent, useRef, useState } from "react";

import type { DrawMode } from "@/components/map/LocationMap";
import type { GeometryInfo } from "@/lib/api/types";
import { downloadGeometryFeature } from "@/lib/map/geojson";
import clsx from "clsx";

interface AoiPanelProps {
  hasAoi: boolean;
  aoiGeometry: unknown;
  drawMode: DrawMode | null;
  info: GeometryInfo | null;
  error: string | null;
  onStartDraw: (mode: DrawMode) => void;
  onCancelDraw: () => void;
  onImportText: (text: string) => void;
  onClear: () => void;
  documentTitle: string;
}

export function formatArea(m2: number): string {
  if (m2 >= 1_000_000) return `${(m2 / 1_000_000).toFixed(2)} km²`;
  if (m2 >= 1) return `${Math.round(m2).toLocaleString()} m²`;
  return `${m2.toFixed(2)} m²`;
}

export function AoiPanel({
  hasAoi,
  aoiGeometry,
  drawMode,
  info,
  error,
  onStartDraw,
  onCancelDraw,
  onImportText,
  onClear,
  documentTitle,
}: AoiPanelProps) {
  const fileRef = useRef<HTMLInputElement>(null);
  const [pasting, setPasting] = useState(false);
  const [pasteText, setPasteText] = useState("");

  async function handleFile(event: ChangeEvent<HTMLInputElement>) {
    const file = event.target.files?.[0];
    event.target.value = "";
    if (!file) return;
    const text = await file.text();
    onImportText(text);
  }

  function handlePasteSubmit() {
    onImportText(pasteText);
    setPasteText("");
    setPasting(false);
  }

  return (
    <div className="space-y-3">
      <div className="flex flex-wrap gap-2">
        <button
          type="button"
          onClick={() => onStartDraw("polygon")}
          disabled={drawMode === "polygon"}
          className={clsx(
            "inline-flex items-center gap-1.5 rounded-lg border px-3 py-1.5 text-xs font-medium transition",
            drawMode === "polygon"
              ? "border-brand-600 bg-brand-600 text-white"
              : "border-zinc-300 bg-white text-zinc-700 hover:border-brand-400 hover:text-brand-600",
          )}
        >
          <PencilRuler className="h-3.5 w-3.5" />
          Draw polygon
        </button>
        <button
          type="button"
          onClick={() => onStartDraw("rectangle")}
          disabled={drawMode === "rectangle"}
          className={clsx(
            "inline-flex items-center gap-1.5 rounded-lg border px-3 py-1.5 text-xs font-medium transition",
            drawMode === "rectangle"
              ? "border-brand-600 bg-brand-600 text-white"
              : "border-zinc-300 bg-white text-zinc-700 hover:border-brand-400 hover:text-brand-600",
          )}
        >
          <PencilRuler className="h-3.5 w-3.5" />
          Draw rectangle
        </button>
        {drawMode && (
          <button
            type="button"
            onClick={onCancelDraw}
            className="inline-flex items-center gap-1.5 rounded-lg border border-zinc-300 bg-white px-3 py-1.5 text-xs font-medium text-zinc-700 hover:bg-zinc-50"
          >
            <X className="h-3.5 w-3.5" />
            Cancel drawing
          </button>
        )}
        <button
          type="button"
          onClick={() => fileRef.current?.click()}
          className="inline-flex items-center gap-1.5 rounded-lg border border-zinc-300 bg-white px-3 py-1.5 text-xs font-medium text-zinc-700 hover:border-brand-400 hover:text-brand-600"
        >
          <FileUp className="h-3.5 w-3.5" />
          Import GeoJSON
        </button>
        <input ref={fileRef} type="file" accept=".geojson,.json,application/geo+json,application/json" className="hidden" onChange={handleFile} />
        <button
          type="button"
          onClick={() => setPasting((value) => !value)}
          className={clsx(
            "inline-flex items-center gap-1.5 rounded-lg border px-3 py-1.5 text-xs font-medium transition",
            pasting
              ? "border-brand-600 bg-brand-600 text-white"
              : "border-zinc-300 bg-white text-zinc-700 hover:border-brand-400 hover:text-brand-600",
          )}
        >
          <ClipboardPaste className="h-3.5 w-3.5" />
          Paste
        </button>
        <button
          type="button"
          onClick={() => downloadGeometryFeature(aoiGeometry, documentTitle)}
          disabled={!hasAoi}
          className="inline-flex items-center gap-1.5 rounded-lg border border-zinc-300 bg-white px-3 py-1.5 text-xs font-medium text-zinc-700 transition enabled:hover:border-brand-400 enabled:hover:text-brand-600 disabled:opacity-40"
        >
          <Download className="h-3.5 w-3.5" />
          Export
        </button>
        <button
          type="button"
          onClick={onClear}
          disabled={!hasAoi}
          className="inline-flex items-center gap-1.5 rounded-lg border border-zinc-300 bg-white px-3 py-1.5 text-xs font-medium text-zinc-700 transition enabled:hover:border-red-400 enabled:hover:text-red-600 disabled:opacity-40"
        >
          <Eraser className="h-3.5 w-3.5" />
          Clear
        </button>
      </div>

      {pasting && (
        <div className="space-y-2">
          <textarea
            value={pasteText}
            onChange={(event) => setPasteText(event.target.value)}
            rows={4}
            placeholder='{"type":"Polygon","coordinates":[[[...]]]}'
            className="w-full rounded-lg border border-zinc-300 bg-white p-2 font-mono text-xs text-zinc-800 outline-none focus:border-brand-500"
          />
          <div className="flex gap-2">
            <button
              type="button"
              onClick={handlePasteSubmit}
              disabled={!pasteText.trim()}
              className="rounded-lg bg-brand-600 px-3 py-1.5 text-xs font-medium text-white transition enabled:hover:bg-brand-700 disabled:opacity-40"
            >
              Validate &amp; apply
            </button>
          </div>
        </div>
      )}

      {error && (
        <p className="rounded-lg bg-red-50 px-3 py-2 text-xs text-red-700" role="alert">
          {error}
        </p>
      )}

      {info && !error && (
        <dl className="grid grid-cols-2 gap-x-4 gap-y-2 rounded-lg border border-emerald-100 bg-emerald-50/60 px-3 py-2.5 text-xs">
          <div>
            <dt className="text-zinc-500">Type</dt>
            <dd className="font-medium text-zinc-900">{info.geometry_type}</dd>
          </div>
          <div>
            <dt className="text-zinc-500">Approximate area</dt>
            <dd className="font-medium text-zinc-900">{formatArea(info.area_m2_approx)}</dd>
          </div>
          <div>
            <dt className="text-zinc-500">Vertices</dt>
            <dd className="font-medium text-zinc-900">{info.point_count.toLocaleString()}</dd>
          </div>
          <div>
            <dt className="text-zinc-500">Status</dt>
            <dd className="font-medium text-emerald-700">Valid ({info.srid})</dd>
          </div>
        </dl>
      )}
    </div>
  );
}