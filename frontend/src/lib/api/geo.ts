import type {
  AgentCode,
  AnalysisSession,
  GeoJsonGeometry,
  GeometryInfo,
  Place,
  SavedLocation,
  Workspace,
} from "@/lib/api/types";
import { api } from "./client";

export interface Bbox {
  minLon: number;
  minLat: number;
  maxLon: number;
  maxLat: number;
}

export function bboxFromTuple(value: [number, number, number, number] | null): Bbox | null {
  if (!value) return null;
  return { minLon: value[0], minLat: value[1], maxLon: value[2], maxLat: value[3] };
}

/** Geocode a free-text query; pass an AbortSignal to cancel in-flight requests. */
export function searchPlaces(
  query: string,
  options: { bbox?: Bbox | null; signal?: AbortSignal } = {},
): Promise<Place[]> {
  const params = new URLSearchParams({ q: query });
  if (options.bbox) params.set("bbox", bboxToQuery(options.bbox));
  return api.get<Place[]>(`/places/search?${params.toString()}`, options.signal);
}

function bboxToQuery(bbox: Bbox): string {
  return `${bbox.minLon},${bbox.minLat},${bbox.maxLon},${bbox.maxLat}`;
}

export function validateGeometry(
  geometry: unknown,
  requireArea = false,
): Promise<GeometryInfo> {
  return api.post<GeometryInfo>("/geometries/validate", {
    geometry,
    require_area: requireArea,
  });
}

export function listAnalysisSessions(workspaceId?: number | null): Promise<AnalysisSession[]> {
  const query = workspaceId ? `?workspace_id=${workspaceId}` : "";
  return api.get<AnalysisSession[]>(`/analysis-sessions${query}`);
}

export interface AnalysisSessionInput {
  title?: string | null;
  workspace_id?: number | null;
  aoi?: GeoJsonGeometry | null;
  saved_location_id?: number | null;
  start_date?: string | null;
  end_date?: string | null;
  agents?: AgentCode[] | null;
}

export function createAnalysisSession(input: AnalysisSessionInput): Promise<AnalysisSession> {
  return api.post<AnalysisSession>("/analysis-sessions", input);
}

export function updateAnalysisSession(
  id: number,
  input: AnalysisSessionInput,
): Promise<AnalysisSession> {
  return api.patch<AnalysisSession>(`/analysis-sessions/${id}`, input);
}

export function listSavedLocations(workspaceId?: number | null): Promise<SavedLocation[]> {
  const query = workspaceId ? `?workspace_id=${workspaceId}` : "";
  return api.get<SavedLocation[]>(`/saved-locations${query}`);
}

export function listWorkspaces(): Promise<Workspace[]> {
  return api.get<Workspace[]>("/workspaces");
}