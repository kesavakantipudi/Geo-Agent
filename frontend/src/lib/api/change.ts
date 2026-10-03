import type {
  ChangeDetectionRequest,
  ChangeDetectionResponse,
} from "./types";
import { api } from "./client";

export function analyzeChange(
  sessionId: number,
  beforeSceneId: number,
  afterSceneId: number,
  payload?: Partial<
    Omit<
      ChangeDetectionRequest,
      "analysis_session_id" | "before_scene_id" | "after_scene_id"
    >
  >,
): Promise<ChangeDetectionResponse> {
  return api.post<ChangeDetectionResponse>("/change-detection/analyze", {
    analysis_session_id: sessionId,
    before_scene_id: beforeSceneId,
    after_scene_id: afterSceneId,
    types: ["vegetation", "water"],
    mask_clouds: true,
    include_weather: true,
    ...payload,
  });
}