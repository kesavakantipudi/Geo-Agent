import type {
  RetrievalRecord,
  RetrievalStatus,
  SatelliteScene,
  SceneAsset,
  SceneAssetRetrievalRequest,
  SceneSearchRequest,
  SceneSearchResponse,
} from "./types";
import { api } from "./client";

export function searchScenes(
  sessionId: number,
  payload?: Partial<SceneSearchRequest>,
): Promise<SceneSearchResponse> {
  return api.post<SceneSearchResponse>("/satellite/scenes/search", { sessionId, ...payload });
}

export function listSessionScenes(sessionId: number): Promise<SatelliteScene[]> {
  return api.get<SatelliteScene[]>(`/satellite/sessions/${sessionId}/scenes`);
}

export function getScene(sceneId: number): Promise<SatelliteScene> {
  return api.get<SatelliteScene>(`/satellite/scenes/${sceneId}`);
}

export function listSceneAssets(sceneId: number): Promise<SceneAsset[]> {
  return api.get<SceneAsset[]>(`/satellite/scenes/${sceneId}/assets`);
}

export function requestRetrieval(
  sceneId: number,
  assetKeys: string[],
  sessionId: number,
): Promise<RetrievalRecord[]> {
  const request: SceneAssetRetrievalRequest = { asset_keys: assetKeys };
  return api.post<RetrievalRecord[]>(`/satellite/scenes/${sceneId}/retrievals`, request);
}

export function listRetrievals(sceneId: number): Promise<RetrievalRecord[]> {
  return api.get<RetrievalRecord[]>(`/satellite/scenes/${sceneId}/retrievals`);
}

export function deleteRetrieval(retrievalId: number): Promise<void> {
  return api.delete(`/satellite/retrievals/${retrievalId}`);
}
