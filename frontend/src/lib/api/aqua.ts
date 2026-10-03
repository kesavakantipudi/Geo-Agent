import type {
  AquaAnalyzeRequest,
  AquaAnalyzeResponse,
} from "./types";
import { api } from "./client";

export function analyzeAqua(
  sessionId: number,
  sceneId: number,
  payload?: Partial<Omit<AquaAnalyzeRequest, "analysis_session_id" | "scene_id">>,
): Promise<AquaAnalyzeResponse> {
  return api.post<AquaAnalyzeResponse>("/aqua/analyze", {
    analysis_session_id: sessionId,
    scene_id: sceneId,
    indices: ["ndwi"],
    mask_clouds: true,
    ...payload,
  });
}