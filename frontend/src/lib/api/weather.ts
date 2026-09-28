import type {
  WeatherObservationPoint,
  WeatherSearchRequest,
  WeatherSearchResponse,
} from "./types";
import { api } from "./client";

export function searchWeather(
  sessionId: number,
  payload?: Partial<WeatherSearchRequest>,
): Promise<WeatherSearchResponse> {
  return api.post<WeatherSearchResponse>("/weather/search", {
    analysis_session_id: sessionId,
    ...payload,
  });
}

export function listSessionObservations(
  sessionId: number,
): Promise<WeatherObservationPoint[]> {
  return api.get<WeatherObservationPoint[]>(`/weather/sessions/${sessionId}/observations`);
}

export function getObservation(observationId: number): Promise<WeatherObservationPoint> {
  return api.get<WeatherObservationPoint>(`/weather/observations/${observationId}`);
}