import type {
  HistoricalRequest,
  HistoricalResponse,
} from "./types";
import { api } from "./client";

export function analyzeHistorical(
  sessionId: number,
  payload?: Partial<Omit<HistoricalRequest, "analysis_session_id">>,
): Promise<HistoricalResponse> {
  return api.post<HistoricalResponse>("/historical/analyze", {
    analysis_session_id: sessionId,
    types: ["vegetation", "water"],
    mask_clouds: true,
    include_weather: true,
    ...payload,
  });
}