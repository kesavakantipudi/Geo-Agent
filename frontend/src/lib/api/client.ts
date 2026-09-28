import type { ApiErrorPayload } from "@/lib/api/types";

const API_BASE = (process.env.NEXT_PUBLIC_API_BASE_URL ?? "/api/v1").replace(/\/$/, "");

export class ApiError extends Error {
  readonly status: number;
  readonly code: string;
  readonly details?: unknown[];

  constructor(message: string, status: number, code: string, details?: unknown[]) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.code = code;
    this.details = details;
  }
}

async function readErrorBody(res: Response): Promise<Partial<ApiErrorPayload>> {
  try {
    return (await res.json()) as Partial<ApiErrorPayload>;
  } catch {
    return {};
  }
}

/** Rotate the refresh cookie. Called once when an access token has expired. */
export async function rotateRefreshToken(): Promise<void> {
  await fetch(`${API_BASE}/auth/refresh`, {
    method: "POST",
    credentials: "include",
  }).catch(() => undefined);
}

async function request<T>(
  path: string,
  options: { method?: string; body?: unknown; signal?: AbortSignal } = {},
  allowRetry = true,
): Promise<T> {
  const { method = "GET", body, signal } = options;
  const headers: Record<string, string> = {};
  if (body !== undefined) {
    headers["Content-Type"] = "application/json";
  }

  const res = await fetch(`${API_BASE}${path}`, {
    method,
    headers,
    body: body !== undefined ? JSON.stringify(body) : undefined,
    credentials: "include",
    signal,
  });

  if (res.status === 401 && allowRetry) {
    await rotateRefreshToken();
    return request<T>(path, options, false);
  }

  if (!res.ok) {
    const payload = await readErrorBody(res);
    const error = payload?.error;
    throw new ApiError(
      error?.message ?? `Request failed with status ${res.status}`,
      res.status,
      error?.code ?? "request_failed",
      error?.details,
    );
  }

  if (res.status === 204) {
    return undefined as T;
  }
  return (await res.json()) as T;
}

export const api = {
  get: <T>(path: string, signal?: AbortSignal) => request<T>(path, { signal }),
  post: <T>(path: string, body?: unknown) => request<T>(path, { method: "POST", body }),
  patch: <T>(path: string, body?: unknown) => request<T>(path, { method: "PATCH", body }),
  delete: <T>(path: string) => request<T>(path, { method: "DELETE" }),
};