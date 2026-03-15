import type { ApiError, ApiSuccess, HealthData } from "./types";

const DEFAULT_API_BASE_URL = "http://localhost:8000/api/v1";

export function getApiBaseUrl(): string {
  return process.env.NEXT_PUBLIC_API_BASE_URL ?? DEFAULT_API_BASE_URL;
}

export function createApiUrl(path: string): string {
  const base = getApiBaseUrl().replace(/\/$/, "");
  const relativePath = path.startsWith("/") ? path : `/${path}`;
  return `${base}${relativePath}`;
}

export async function requestJson<T>(path: string, init?: RequestInit): Promise<ApiSuccess<T>> {
  const response = await fetch(createApiUrl(path), {
    ...init,
    headers: {
      "content-type": "application/json",
      ...(init?.headers ?? {}),
    },
  });

  const body = (await response.json()) as ApiSuccess<T> | ApiError;
  if (!response.ok) {
    const error = body as ApiError;
    throw new Error(error.error?.message ?? "Request failed");
  }

  return body as ApiSuccess<T>;
}

export function getHealth(): Promise<ApiSuccess<HealthData>> {
  return requestJson<HealthData>("/health");
}
