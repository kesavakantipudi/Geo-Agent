"use client";

import dynamic from "next/dynamic";
import { useCallback, useEffect, useState } from "react";

import {
  AnalysisConfigPanel,
  type AnalysisConfig,
} from "@/components/analysis/AnalysisConfigPanel";
import { SessionsList } from "@/components/analysis/SessionsList";
import { WeatherDiscoveryPanel } from "@/components/analysis/WeatherDiscoveryPanel";
import { AoiPanel } from "@/components/map/AoiPanel";
import { PlaceSearch } from "@/components/map/PlaceSearch";
import type { DrawMode } from "@/components/map/LocationMap";
import { ApiError } from "@/lib/api/client";
import {
  createAnalysisSession,
  listAnalysisSessions,
  listSavedLocations,
  listWorkspaces,
  updateAnalysisSession,
  validateGeometry,
  type AnalysisSessionInput,
} from "@/lib/api/geo";
import type {
  AgentCode,
  AnalysisSession,
  Centroid,
  GeoJsonGeometry,
  GeometryInfo,
  Place,
  SavedLocation,
  Workspace,
} from "@/lib/api/types";
import { extractGeometry } from "@/lib/map/geojson";

const LocationMap = dynamic(
  () => import("@/components/map/LocationMap").then((mod) => mod.LocationMap),
  {
    ssr: false,
    loading: () => (
      <div className="flex h-full w-full items-center justify-center bg-zinc-100 text-sm text-zinc-400">
        Loading mapâ€¦
      </div>
    ),
  },
);

const EMPTY_CONFIG: AnalysisConfig = {
  title: "",
  workspaceId: "",
  startDate: "",
  endDate: "",
  agents: [],
};

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <section className="rounded-xl border border-zinc-200 bg-white p-4 shadow-sm">
      <h2 className="mb-3 text-sm font-semibold text-zinc-900">{title}</h2>
      {children}
    </section>
  );
}

export function AnalysisWorkspace() {
  const [aoi, setAoi] = useState<GeoJsonGeometry | null>(null);
  const [geometryInfo, setGeometryInfo] = useState<GeometryInfo | null>(null);
  const [geomError, setGeomError] = useState<string | null>(null);
  const [validating, setValidating] = useState(false);
  const [drawMode, setDrawMode] = useState<DrawMode | null>(null);
  const [placeCenter, setPlaceCenter] = useState<Centroid | null>(null);

  const [workspaces, setWorkspaces] = useState<Workspace[]>([]);
  const [savedLocations, setSavedLocations] = useState<SavedLocation[]>([]);
  const [sessions, setSessions] = useState<AnalysisSession[]>([]);
  const [sessionsLoading, setSessionsLoading] = useState(true);

  const [config, setConfig] = useState<AnalysisConfig>(EMPTY_CONFIG);
  const [activeSession, setActiveSession] = useState<AnalysisSession | null>(null);
  const [saveState, setSaveState] = useState<"idle" | "saved" | "error">("idle");
  const [saving, setSaving] = useState(false);
  const [saveError, setSaveError] = useState<string | null>(null);

  const validateAoi = useCallback(async (geometry: unknown) => {
    setValidating(true);
    setGeomError(null);
    setGeometryInfo(null);
    try {
      const info = await validateGeometry(geometry, true);
      setGeometryInfo(info);
    } catch (err) {
      setGeomError(
        err instanceof ApiError ? err.message : "The geometry could not be validated.",
      );
    } finally {
      setValidating(false);
    }
  }, []);

  useEffect(() => {
    let cancelled = false;
    async function refreshSessions() {
      setSessionsLoading(true);
      try {
        const next = await listAnalysisSessions();
        if (!cancelled) {
          setSessions(next);
          setSessionsLoading(false);
        }
      } catch {
        if (!cancelled) setSessionsLoading(false);
      }
    }
    async function load() {
      try {
        const [workspaceList, locationList] = await Promise.all([
          listWorkspaces(),
          listSavedLocations(),
        ]);
        if (!cancelled) {
          setWorkspaces(workspaceList);
          setSavedLocations(locationList);
        }
      } catch {
        // Individual panels render empty states; user can retry by saving.
      }
      void refreshSessions();
    }
    void load();
    return () => {
      cancelled = true;
    };
  }, []);

  function handleDrawCreated(geometry: GeoJsonGeometry) {
    setDrawMode(null);
    setAoi(geometry);
    setPlaceCenter(null);
    void validateAoi(geometry);
  }

  function handleImportText(text: string) {
    let parsed: unknown;
    try {
      parsed = JSON.parse(text);
    } catch {
      setGeomError("The pasted content is not valid JSON.");
      return;
    }
    const geometry = extractGeometry(parsed);
    if (!geometry || typeof geometry !== "object") {
      setGeomError(
        "No usable single geometry found. Expected a geometry, one Feature, or a single-feature FeatureCollection.",
      );
      return;
    }
    setAoi(geometry as GeoJsonGeometry);
    setPlaceCenter(null);
    void validateAoi(geometry);
  }

  function handleClear() {
    setAoi(null);
    setGeometryInfo(null);
    setGeomError(null);
    setPlaceCenter(null);
  }

  function handlePlaceSelect(place: Place) {
    setPlaceCenter(place.center);
    setAoi(null);
    setGeometryInfo(null);
    setGeomError(null);
  }

  function handleUseSavedLocation(location: SavedLocation | null) {
    if (!location) return;
    if (location.geometry_geojson) {
      setAoi(location.geometry_geojson);
      setGeomError(null);
      void validateAoi(location.geometry_geojson);
    } else {
      setGeomError("This saved location has no usable geometry.");
    }
  }

  function handleConfigChange(partial: Partial<AnalysisConfig>) {
    setConfig((current) => ({ ...current, ...partial }));
    setSaveState("idle");
    setSaveError(null);
  }

  const dateError =
    config.startDate && config.endDate && config.endDate < config.startDate
      ? "End date must be on or after start date."
      : null;

  const canSave = aoi !== null && !validating && !geomError && !dateError;

  async function handleSave() {
    if (!aoi) {
      setSaveError("Draw or import an area of interest first.");
      setSaveState("error");
      return;
    }
    setSaving(true);
    setSaveError(null);
    const input: AnalysisSessionInput = {
      title: config.title.trim() || undefined,
      workspace_id: config.workspaceId ? Number(config.workspaceId) : null,
      aoi,
      start_date: config.startDate || null,
      end_date: config.endDate || null,
      agents: config.agents.length > 0 ? (config.agents as AgentCode[]) : null,
    };
    try {
      const saved = activeSession
        ? await updateAnalysisSession(activeSession.id, input)
        : await createAnalysisSession(input);
      setActiveSession(saved);
      setSaveState("saved");
      setSessions(await listAnalysisSessions());
    } catch (err) {
      setSaveState("error");
      setSaveError(
        err instanceof ApiError
          ? err.message
          : "Could not save the analysis. Please try again.",
      );
    } finally {
      setSaving(false);
    }
  }

  function handleReopen(session: AnalysisSession) {
    setActiveSession(session);
    setConfig({
      title: session.title,
      workspaceId: session.workspace_id ? String(session.workspace_id) : "",
      startDate: session.start_date ?? "",
      endDate: session.end_date ?? "",
      agents: session.agents ?? [],
    });
    setSaveState("idle");
    setSaveError(null);
    setGeomError(null);
    if (session.aoi) {
      setAoi(session.aoi);
      void validateAoi(session.aoi);
    } else {
      setAoi(null);
      setGeometryInfo(null);
    }
  }

  function handleNew() {
    setActiveSession(null);
    setConfig(EMPTY_CONFIG);
    setAoi(null);
    setGeometryInfo(null);
    setGeomError(null);
    setPlaceCenter(null);
    setSaveState("idle");
    setSaveError(null);
  }

  const hasState =
    config.title !== "" ||
    aoi !== null ||
    config.startDate !== "" ||
    config.agents.length > 0 ||
    activeSession !== null;

  return (
    <div className="space-y-6">
      <div className="grid gap-6 lg:grid-cols-[minmax(0,1fr)_380px]">
        <div className="min-w-0">
          <div className="mb-3">
            <PlaceSearch onSelect={handlePlaceSelect} bboxScope={null} />
          </div>
          <div className="h-[420px] overflow-hidden rounded-xl border border-zinc-200 lg:h-[560px]">
            <LocationMap
              aoi={aoi}
              drawMode={drawMode}
              onDrawCreated={handleDrawCreated}
              placeCenter={placeCenter}
            />
          </div>
        </div>

        <div className="space-y-6">
          <Section title="Area of interest">
            <AoiPanel
              hasAoi={aoi !== null}
              aoiGeometry={aoi}
              drawMode={drawMode}
              info={geometryInfo}
              error={geomError}
              onStartDraw={setDrawMode}
              onCancelDraw={() => setDrawMode(null)}
              onImportText={handleImportText}
              onClear={handleClear}
              documentTitle={config.title}
            />
          </Section>

          <Section title="Analysis settings">
            <AnalysisConfigPanel
              config={config}
              onChange={handleConfigChange}
              onSave={() => void handleSave()}
              onNew={handleNew}
              onUseSavedLocation={handleUseSavedLocation}
              workspaces={workspaces}
              savedLocations={savedLocations}
              canSave={canSave}
              saving={saving}
              saveState={saveState}
              saveError={dateError ?? saveError}
              canCancelSave={hasState}
            />
          </Section>
        </div>
      </div>

      <Section title="Your analysis sessions">
        <SessionsList
          sessions={sessions}
          activeSessionId={activeSession?.id ?? null}
          loading={sessionsLoading}
          onReopen={handleReopen}
        />
      </Section>

      <Section title="Weather observations">
        {activeSession ? (
          <WeatherDiscoveryPanel
            sessionId={activeSession.id}
            aoi={aoi}
            startDate={config.startDate}
            endDate={config.endDate}
          />
        ) : (
          <p className="text-xs text-zinc-500">
            Save or reopen an analysis session to fetch weather observations for its AOI and
            date range.
          </p>
        )}
      </Section>
    </div>
  );
}
