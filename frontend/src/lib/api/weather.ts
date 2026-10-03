import type {
  WeatherContext,
  WeatherContextRequest,
  WeatherContextResponse,
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

export function getWeatherContext(
  sessionId: number,
  sceneId: number,
  payload?: Partial<Omit<WeatherContextRequest, "analysis_session_id" | "scene_id">>,
): Promise<WeatherContext> {
  return api
    .post<WeatherContextResponse>("/weather/context", {
      analysis_session_id: sessionId,
      scene_id: sceneId,
      ...payload,
    })
    .then((response) => response.context);
}

export function listSessionObservations(
  sessionId: number,
): Promise<WeatherObservationPoint[]> {
  return api.get<WeatherObservationPoint[]>(`/weather/sessions/${sessionId}/observations`);
}

export function getObservation(observationId: number): Promise<WeatherObservationPoint> {
  return api.get<WeatherObservationPoint>(`/weather/observations/${observationId}`);
}