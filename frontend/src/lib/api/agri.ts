import type {
  AgriAnalysisResult,
  AgriAnalysisSummary,
  AgriAnalyzeRequest,
  AgriAnalyzeResponse,
} from "./types";
import { api } from "./client";

export function analyzeAgri(
  sessionId: number,
  sceneId: number,
  payload?: Partial<Omit<AgriAnalyzeRequest, "analysis_session_id" | "scene_id">>,
): Promise<AgriAnalyzeResponse> {
  return api.post<AgriAnalyzeResponse>("/agri/analyze", {
    analysis_session_id: sessionId,
    scene_id: sceneId,
    indices: ["ndvi"],
    mask_clouds: true,
    ...payload,
  });
}

export function getAgriAnalysis(analysisId: number): Promise<AgriAnalysisResult> {
  return api.get<AgriAnalysisResult>(`/agri/analyses/${analysisId}`);
}

export function listSessionAgriAnalyses(sessionId: number): Promise<AgriAnalysisSummary[]> {
  return api.get<AgriAnalysisSummary[]>(`/agri/sessions/${sessionId}/analyses`);
}