import type {
  ApiError,
  ApiSuccess,
  HealthData,
  ProcessingResultData,
  ProjectData,
  QueryResultData,
  SourceIngestionData,
} from "./types";

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

export function createProject(payload: {
  name: string;
  description?: string;
}): Promise<ApiSuccess<ProjectData>> {
  return requestJson<ProjectData>("/projects", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export async function uploadSourceFile(payload: {
  projectId: string;
  file: File;
}): Promise<ApiSuccess<SourceIngestionData>> {
  const form = new FormData();
  form.append("project_id", payload.projectId);
  form.append("file", payload.file);

  const response = await fetch(createApiUrl("/sources/files"), {
    method: "POST",
    body: form,
  });

  const body = (await response.json()) as ApiSuccess<SourceIngestionData> | ApiError;
  if (!response.ok) {
    const error = body as ApiError;
    throw new Error(error.error?.message ?? "Request failed");
  }

  return body as ApiSuccess<SourceIngestionData>;
}

export function ingestSourceUrl(payload: {
  projectId: string;
  url: string;
}): Promise<ApiSuccess<SourceIngestionData>> {
  return requestJson<SourceIngestionData>("/sources/urls", {
    method: "POST",
    body: JSON.stringify({
      project_id: payload.projectId,
      url: payload.url,
    }),
  });
}

export function processSources(payload: {
  projectId: string;
  sourceIds: string[];
  chunkSize?: number;
  chunkOverlap?: number;
}): Promise<ApiSuccess<ProcessingResultData>> {
  return requestJson<ProcessingResultData>("/jobs/processing", {
    method: "POST",
    body: JSON.stringify({
      project_id: payload.projectId,
      source_ids: payload.sourceIds,
      options: {
        chunk_size: payload.chunkSize ?? 800,
        chunk_overlap: payload.chunkOverlap ?? 120,
      },
    }),
  });
}

export function queryKnowledge(payload: {
  projectId: string;
  query: string;
  topK?: number;
}): Promise<ApiSuccess<QueryResultData>> {
  return requestJson<QueryResultData>("/query/search", {
    method: "POST",
    body: JSON.stringify({
      project_id: payload.projectId,
      query: payload.query,
      top_k: payload.topK ?? 5,
    }),
  });
}
