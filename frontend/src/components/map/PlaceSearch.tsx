"use client";

import { Loader2, Search } from "lucide-react";
import { useEffect, useRef, useState } from "react";

import { ApiError } from "@/lib/api/client";
import type { Bbox } from "@/lib/api/geo";
import { searchPlaces } from "@/lib/api/geo";
import type { Place } from "@/lib/api/types";

interface PlaceSearchProps {
  onSelect: (place: Place) => void;
  bboxScope?: Bbox | null;
}

const DEBOUNCE_MS = 300;

export function PlaceSearch({ onSelect, bboxScope }: PlaceSearchProps) {
  const [query, setQuery] = useState("");
  const [results, setResults] = useState<Place[]>([]);
  const [open, setOpen] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const timerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const abortRef = useRef<AbortController | null>(null);

  useEffect(() => {
    return () => {
      abortRef.current?.abort();
      if (timerRef.current) clearTimeout(timerRef.current);
    };
  }, []);

  function handleChange(value: string) {
    setQuery(value);
    setError(null);
    if (timerRef.current) clearTimeout(timerRef.current);

    const trimmed = value.trim();
    if (trimmed.length < 2) {
      setResults([]);
      setOpen(false);
      return;
    }
    timerRef.current = setTimeout(() => {
      void runSearch(trimmed);
    }, DEBOUNCE_MS);
  }

  async function runSearch(value: string) {
    abortRef.current?.abort();
    const controller = new AbortController();
    abortRef.current = controller;
    setLoading(true);
    try {
      const found = await searchPlaces(value, { bbox: bboxScope, signal: controller.signal });
      if (controller.signal.aborted) return;
      setResults(found);
      setOpen(true);
    } catch (err) {
      if (err instanceof DOMException && err.name === "AbortError") return;
      setResults([]);
      setError(err instanceof ApiError ? err.message : "Place search failed.");
    } finally {
      if (!controller.signal.aborted) setLoading(false);
    }
  }

  function handleSelect(place: Place) {
    setOpen(false);
    setQuery(place.label);
    onSelect(place);
  }

  return (
    <div className="relative">
      <div className="relative">
        <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-zinc-400" />
        <input
          type="text"
          value={query}
          onChange={(event) => handleChange(event.target.value)}
          onBlur={() => setTimeout(() => setOpen(false), 150)}
          onFocus={() => results.length > 0 && setOpen(true)}
          placeholder="Search for a place (city, street, landmark)…"
          aria-label="Search for a place"
          className="w-full rounded-lg border border-zinc-300 bg-white py-2 pl-9 pr-9 text-sm text-zinc-900 shadow-sm outline-none transition focus:border-brand-500 focus:ring-2 focus:ring-brand-100"
        />
        {loading && <Loader2 className="absolute right-3 top-1/2 h-4 w-4 -translate-y-1/2 animate-spin text-zinc-400" />}
      </div>

      {error && <p className="mt-1.5 text-xs text-red-600">{error}</p>}

      {open && results.length > 0 && (
        <ul className="absolute z-[1100] mt-1 max-h-64 w-full overflow-auto rounded-lg border border-zinc-200 bg-white py-1 shadow-lg">
          {results.map((place) => (
            <li key={place.id}>
              <button
                type="button"
                onMouseDown={() => handleSelect(place)}
                className="block w-full px-3 py-2 text-left text-sm text-zinc-800 transition hover:bg-brand-50"
              >
                <span className="line-clamp-2">{place.label}</span>
                {place.bbox && (
                  <span className="mt-0.5 block text-[10px] uppercase tracking-wide text-zinc-400">
                    {place.bbox[3].toFixed(2)}°N {place.bbox[0].toFixed(2)}°E
                  </span>
                )}
              </button>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}