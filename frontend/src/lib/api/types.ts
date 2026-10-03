export interface UserSummary {
  id: number;
  email: string;
  username: string;
  full_name: string | null;
}

export interface AuthUserResponse extends UserSummary {
  created_at: string;
  updated_at: string;
}

export type OrganizationRole = "owner" | "admin" | "member";

export interface OrganizationSummary {
  id: number;
  name: string;
  slug: string;
}

export interface Organization extends OrganizationSummary {
  description: string | null;
  created_at: string;
  updated_at: string;
}

export interface OrganizationMember {
  id: number;
  role: OrganizationRole;
  user: UserSummary;
  created_at: string;
  updated_at: string;
}

export interface Workspace {
  id: number;
  organization_id: number;
  name: string;
  description: string | null;
  created_at: string;
  updated_at: string;
}

export type SavedLocationType = "point" | "polygon" | "line" | "custom";

export interface Centroid {
  lon: number;
  lat: number;
}

export type BboxTuple = [number, number, number, number];

export interface SavedLocation {
  id: number;
  user_id: number;
  workspace_id: number | null;
  name: string;
  description: string | null;
  location_type: SavedLocationType;
  center_lat: number | null;
  center_lon: number | null;
  bbox: BboxTuple | null;
  geometry: string | null; // EWKT text
  geometry_type: string | null;
  geometry_geojson: GeoJsonGeometry | null;
  centroid: Centroid | null;
  area_m2_approx: number;
  created_at: string;
  updated_at: string;
}

export type GeoJsonGeometryType =
  | "Point"
  | "LineString"
  | "Polygon"
  | "MultiPoint"
  | "MultiLineString"
  | "MultiPolygon"
  | "GeometryCollection";

export interface GeoJsonGeometry {
  type: GeoJsonGeometryType;
  coordinates: unknown;
  geometries?: GeoJsonGeometry[];
}

export interface GeometryInfo {
  geometry_type: string;
  is_valid: boolean;
  point_count: number;
  bbox: BboxTuple | null;
  centroid: Centroid | null;
  area_m2_approx: number;
  srid: number;
  warnings: string[];
}

export interface Place {
  id: string;
  provider: string;
  label: string;
  display_name: string;
  bbox: BboxTuple | null;
  center: Centroid;
}

export type AgentCode = "agri" | "aqua" | "weather" | "change";
export type SatelliteProviderCode = "planetary-computer" | "cdse";

export interface SceneAsset {
  key: string;
  href: string;
  media_type: string | null;
  size_bytes: number | null;
  acquisition_datetime?: string | null;
}

export interface SatelliteScene {
  id: number;
  provider: SatelliteProviderCode;
  scene_id: string;
  platform: string | null;
  acquisition_date: string | null;
  cloud_cover: number | null;
  resolution_m: number | null;
  geometry: GeoJsonGeometry | null;
  bbox: BboxTuple | null;
  metadata: Record<string, unknown>;
  assets: SceneAsset[];
  created_at: string;
}

export interface ProviderStatus {
  provider: string;
  scenes: number;
  error?: string | null;
}

export interface SceneSearchRequest {
  analysis_session_id?: number | null;
  aoi?: GeoJsonGeometry | null;
  start_date?: string | null;
  end_date?: string | null;
  providers?: SatelliteProviderCode[] | null;
  limit?: number;
  max_cloud_cover?: number;
}

export interface SceneSearchResponse {
  scenes: SatelliteScene[];
  providers: ProviderStatus[];
  truncated: boolean;
}

export type RetrievalStatus = "completed" | "failed";

export interface RetrievalRecord {
  id: number;
  scene_id: number;
  asset_key: string;
  status: RetrievalStatus;
  size_bytes: number | null;
  requested_at: string;
  completed_at: string | null;
}

export interface SceneAssetRetrievalRequest {
  asset_keys: string[];
  analysis_session_id?: number | null;
}
export type WeatherDataTypes =
  | "current"
  | "forecast"
  | "history"
  | "archive"
  | "reanalysis"
  | "historical_forecast";

export type WeatherUnits = "metric" | "imperial";

export interface WeatherProvenance {
  provider: string;
  source_url?: string | null;
  model?: string | null;
  grid_cell?: Record<string, unknown>;
  aggregation?: string | null;
  attribution?: string | null;
}

export interface WeatherObservationPoint {
  id: number;
  provider: string;
  model: string | null;
  data_type: WeatherDataTypes;
  variable: string;
  observed_at: string;
  timezone: string;
  value: number | null;
  units: string | null;
  units_doc: string | null;
  latitude: number;
  longitude: number;
  provenance: WeatherProvenance;
  attribution: string;
}

export interface WeatherProviderStatus {
  provider: string;
  observations: number;
  error?: string | null;
}

export interface WeatherSearchRequest {
  analysis_session_id?: number | null;
  aoi?: GeoJsonGeometry | null;
  start_date?: string | null;
  end_date?: string | null;
  variables?: string[] | null;
  model?: string | null;
  timezone?: string;
  units?: WeatherUnits;
  data_type?: WeatherDataTypes;
  providers?: string[] | null;
}

export interface WeatherSearchResponse {
  observations: WeatherObservationPoint[];
  providers: WeatherProviderStatus[];
  truncated: boolean;
}

export interface WeatherContextVariable {
  name: string;
  aggregator: "mean" | "sum" | "min" | "max" | "none";
  value: number | null;
  units: string | null;
  units_doc: string | null;
  observation_count: number;
  sample_count: number;
  expected_count: number;
  coverage_pct: number;
  available: boolean;
  note: string | null;
}

export interface WeatherContextPeriod {
  start: string;
  end: string;
  days_before: number;
  days_after: number;
}

export interface WeatherContextSceneRef {
  id: number;
  scene_id: string;
  provider: SatelliteProviderCode;
  acquisition_date: string;
}

export interface WeatherContextUnavailable {
  code: string;
  reason: string;
  details: string[];
}

export interface WeatherContext {
  status: "available" | "unavailable";
  scene: WeatherContextSceneRef;
  satellite_observation: string;
  period: WeatherContextPeriod | null;
  variables_requested: string[];
  variables: WeatherContextVariable[];
  observation_count: number;
  completeness_pct: number;
  partial: boolean;
  providers: string[];
  models: string[];
  data_types: string[];
  attribution: string | null;
  warnings: string[];
  unavailable: WeatherContextUnavailable | null;
  note: string | null;
}

export interface WeatherContextRequest {
  analysis_session_id: number;
  scene_id: number;
  days_before?: number | null;
  days_after?: number | null;
  variables?: string[] | null;
  providers?: string[] | null;
}

export interface WeatherContextResponse {
  context: WeatherContext;
}

export type AgriIndexName = "ndvi";

export interface AgriIndexInfo {
  name: AgriIndexName;
  label: string;
  formula: string;
  band_roles: Record<string, string>;
  units: string;
  range: [number, number];
  description: string;
}

export interface AgriBandOutput {
  role: string;
  asset_key: string;
  retrieval_id: number;
}

export interface AgriCloudInfo {
  mask_clouds: boolean;
  cloud_mask_available: boolean;
  masked_classes: number[];
}

export interface AgriStatistics {
  min: number;
  max: number;
  mean: number;
  median: number;
  stddev: number;
  valid_pixel_count: number;
  aoi_pixel_count: number;
  valid_pixel_pct: number;
  excluded_pixel_pct: number;
  sampled_area_m2: number;
  units: string;
  range: [number, number];
}

export interface AgriTier {
  tier: string;
  label: string;
  low: number | null;
  high: number | null;
  description: string;
  pixel_pct: number;
}

export interface AgriClassification {
  overall: { tier: string; label: string | null; basis: string };
  dominant_tier: { tier: string; label: string | null; pixel_pct: number };
  tiers: AgriTier[];
  threshold_source: string;
}

export interface AgriSceneReference {
  id: number;
  provider: SatelliteProviderCode;
  scene_id: string;
  platform: string | null;
  acquisition_date: string | null;
  cloud_cover: number | null;
}

export interface AgriUnavailableInfo {
  code: string;
  reason: string;
  details: string[];
}

export interface AgriAnalysisResult {
  id: number | null;
  status: "completed" | "unavailable";
  scene: AgriSceneReference;
  index: AgriIndexInfo | null;
  acquisition_date: string | null;
  cloud: AgriCloudInfo | null;
  statistics: AgriStatistics | null;
  classification: AgriClassification | null;
  bands: AgriBandOutput[] | null;
  processing: Record<string, unknown> | null;
  warnings: string[];
  unavailable: AgriUnavailableInfo | null;
  created_at: string | null;
  weather_context: WeatherContext | null;
}

export interface AgriAnalyzeRequest {
  analysis_session_id: number;
  scene_id: number;
  aoi?: GeoJsonGeometry | null;
  indices: AgriIndexName[];
  mask_clouds: boolean;
}

export interface AgriAnalyzeResponse {
  results: AgriAnalysisResult[];
}

export interface AgriAnalysisSummary {
  id: number;
  status: string;
  index_name: AgriIndexName;
  acquisition_date: string | null;
  scene_id: number;
  provider: SatelliteProviderCode | null;
  platform: string | null;
  cloud_cover: number | null;
  overall_tier: string | null;
  dominant_tier: string | null;
  mean_value: number | null;
  valid_pixel_pct: number | null;
  created_at: string;
}

export type SessionStatus = "draft" | "queued" | "running" | "completed" | "failed";

export type AquaIndexName = "ndwi";

export interface AquaIndexInfo {
  name: AquaIndexName;
  label: string;
  formula: string;
  band_roles: Record<string, string>;
  units: string;
  range: [number, number];
  description: string;
}

export interface AquaBandOutput {
  role: string;
  asset_key: string;
  retrieval_id: number;
}

export interface AquaCloudInfo {
  mask_clouds: boolean;
  cloud_mask_available: boolean;
  masked_classes: number[];
}

export interface AquaStatistics {
  min: number;
  max: number;
  mean: number;
  median: number;
  stddev: number;
  valid_pixel_count: number;
  aoi_pixel_count: number;
  valid_pixel_pct: number;
  excluded_pixel_pct: number;
  sampled_area_m2: number;
  units: string;
  range: [number, number];
}

export interface AquaWaterSummary {
  pixel_count: number;
  area_m2: number;
  pixel_pct: number;
  pct_of_aoi_area: number;
}

export interface AquaNonWaterSummary {
  pixel_count: number;
  pixel_pct: number;
}

export interface AquaClassification {
  label: string;
  threshold: number;
  threshold_source: string;
  boundary: string;
  water: AquaWaterSummary;
  non_water: AquaNonWaterSummary;
  invalid_pixel_count: number;
}

export interface AquaSceneReference {
  id: number;
  provider: SatelliteProviderCode;
  scene_id: string;
  platform: string | null;
  acquisition_date: string | null;
  cloud_cover: number | null;
}

export interface AquaUnavailableInfo {
  code: string;
  reason: string;
  details: string[];
}

export interface AquaAnalysisResult {
  status: "completed" | "unavailable";
  scene: AquaSceneReference;
  index: AquaIndexInfo | null;
  acquisition_date: string | null;
  cloud: AquaCloudInfo | null;
  statistics: AquaStatistics | null;
  classification: AquaClassification | null;
  bands: AquaBandOutput[] | null;
  processing: Record<string, unknown> | null;
  warnings: string[];
  unavailable: AquaUnavailableInfo | null;
  weather_context: WeatherContext | null;
}

export interface AquaAnalyzeRequest {
  analysis_session_id: number;
  scene_id: number;
  aoi?: GeoJsonGeometry | null;
  indices: AquaIndexName[];
  mask_clouds: boolean;
  threshold?: number;
}

export interface AquaAnalyzeResponse {
  results: AquaAnalysisResult[];
}

export interface AnalysisSession {
  id: number;
  user_id: number;
  workspace_id: number | null;
  title: string;
  status: SessionStatus;
  aoi: GeoJsonGeometry | null;
  start_date: string | null;
  end_date: string | null;
  agents: AgentCode[] | null;
  bbox: BboxTuple | null;
  centroid: Centroid | null;
  area_m2_approx: number;
  created_at: string;
  updated_at: string;
}

export interface ApiErrorPayload {
  error: {
    code: string;
    message: string;
    details?: unknown[];
  };
}