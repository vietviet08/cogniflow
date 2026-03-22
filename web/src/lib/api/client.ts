import type {
  ApiError,
  ApiSuccess,
  HealthData,
  ProcessingResultData,
  ProviderModelsData,
  ProviderSettingData,
  ProviderSettingsListData,
  ProjectData,
  QueryResultData,
  ReportType,
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
  provider?: string;
  topK?: number;
}): Promise<ApiSuccess<QueryResultData>> {
  return requestJson<QueryResultData>("/query/search", {
    method: "POST",
    body: JSON.stringify({
      project_id: payload.projectId,
      query: payload.query,
      provider: payload.provider ?? "openai",
      top_k: payload.topK ?? 5,
    }),
  });
}

export function listProjectProviderSettings(
  projectId: string,
): Promise<ApiSuccess<ProviderSettingsListData>> {
  return requestJson<ProviderSettingsListData>(`/projects/${projectId}/providers`);
}

export function saveProjectProviderKey(payload: {
  projectId: string;
  provider: string;
  apiKey: string;
  baseUrl?: string;
  chatModel: string;
  embeddingModel?: string;
}): Promise<ApiSuccess<ProviderSettingData>> {
  return requestJson<ProviderSettingData>(
    `/projects/${payload.projectId}/providers/${payload.provider}`,
    {
      method: "PUT",
      body: JSON.stringify({
        api_key: payload.apiKey,
        base_url: payload.baseUrl,
        chat_model: payload.chatModel,
        embedding_model: payload.embeddingModel,
      }),
    },
  );
}

export function deleteProjectProviderKey(payload: {
  projectId: string;
  provider: string;
}): Promise<ApiSuccess<ProviderSettingData>> {
  return requestJson<ProviderSettingData>(
    `/projects/${payload.projectId}/providers/${payload.provider}`,
    {
      method: "DELETE",
    },
  );
}

export function discoverProjectProviderModels(payload: {
  projectId: string;
  provider: string;
  apiKey?: string;
  baseUrl?: string;
}): Promise<ApiSuccess<ProviderModelsData>> {
  return requestJson<ProviderModelsData>(
    `/projects/${payload.projectId}/providers/${payload.provider}/models/discover`,
    {
      method: "POST",
      body: JSON.stringify({
        api_key: payload.apiKey,
        base_url: payload.baseUrl,
      }),
    },
  );
}

// ---- Phase 2: Insight Layer ----
import type {
  InsightResult,
  InsightListData,
  ReportResult,
  ReportListData,
  ReportLineage,
} from "./types";

export function generateInsight(payload: {
  projectId: string;
  query: string;
  provider?: string;
  maxSources?: number;
}): Promise<ApiSuccess<InsightResult>> {
  return requestJson<InsightResult>("/insights/generate", {
    method: "POST",
    body: JSON.stringify({
      project_id: payload.projectId,
      query: payload.query,
      provider: payload.provider ?? "openai",
      evidence_scope: { max_sources: payload.maxSources ?? 20 },
    }),
  });
}

export function getInsight(insightId: string): Promise<ApiSuccess<InsightResult>> {
  return requestJson<InsightResult>(`/insights/${insightId}`);
}

export function listInsights(projectId: string): Promise<ApiSuccess<InsightListData>> {
  return requestJson<InsightListData>(`/projects/${projectId}/insights`);
}

// ---- Phase 3: Report Layer ----

export function generateReport(payload: {
  projectId: string;
  query: string;
  type?: ReportType;
  format?: string;
  provider?: string;
}): Promise<ApiSuccess<ReportResult>> {
  return requestJson<ReportResult>("/reports/generate", {
    method: "POST",
    body: JSON.stringify({
      project_id: payload.projectId,
      query: payload.query,
      type: payload.type ?? "research_brief",
      format: payload.format ?? "markdown",
      provider: payload.provider ?? "openai",
    }),
  });
}

export function getReport(reportId: string): Promise<ApiSuccess<ReportResult>> {
  return requestJson<ReportResult>(`/reports/${reportId}`);
}

export function getReportLineage(reportId: string): Promise<ApiSuccess<ReportLineage>> {
  return requestJson<ReportLineage>(`/reports/${reportId}/lineage`);
}

export function listReports(projectId: string): Promise<ApiSuccess<ReportListData>> {
  return requestJson<ReportListData>(`/projects/${projectId}/reports`);
}

// ---- Phase 4: UX Polish (Projects & Chat) ----
import type {
  ProjectListData,
  ChatSessionData,
  ChatSessionListData,
  ChatMessageListData,
  ChatSendResponse,
} from "./types";

export function listProjects(): Promise<ApiSuccess<ProjectListData>> {
  return requestJson<ProjectListData>("/projects");
}

export function updateProject(
  projectId: string,
  payload: { name: string; description?: string }
): Promise<ApiSuccess<ProjectData>> {
  return requestJson<ProjectData>(`/projects/${projectId}`, {
    method: "PUT",
    body: JSON.stringify(payload),
  });
}

export function deleteProject(projectId: string): Promise<ApiSuccess<{ success: boolean }>> {
  return requestJson<{ success: boolean }>(`/projects/${projectId}`, {
    method: "DELETE",
  });
}

export function listSources(projectId: string): Promise<ApiSuccess<import("./types").SourceListData>> {
  return requestJson<import("./types").SourceListData>(`/sources/project/${projectId}`);
}

export function deleteSources(sourceIds: string[]): Promise<ApiSuccess<{ success: boolean; deleted_count: number }>> {
  return requestJson<{ success: boolean; deleted_count: number }>("/sources/bulk", {
    method: "DELETE",
    body: JSON.stringify({ source_ids: sourceIds }),
  });
}

export function createChatSession(payload: {
  projectId: string;
  title?: string;
}): Promise<ApiSuccess<ChatSessionData>> {
  return requestJson<ChatSessionData>(`/projects/${payload.projectId}/chat/sessions`, {
    method: "POST",
    body: JSON.stringify({ title: payload.title }),
  });
}

export function listChatSessions(projectId: string): Promise<ApiSuccess<ChatSessionListData>> {
  return requestJson<ChatSessionListData>(`/projects/${projectId}/chat/sessions`);
}

export function listChatMessages(sessionId: string): Promise<ApiSuccess<ChatMessageListData>> {
  return requestJson<ChatMessageListData>(`/chat/sessions/${sessionId}/messages`);
}

export function sendChatMessage(payload: {
  sessionId: string;
  content: string;
  provider?: string;
  topK?: number;
}): Promise<ApiSuccess<ChatSendResponse>> {
  return requestJson<ChatSendResponse>(`/chat/sessions/${payload.sessionId}/messages`, {
    method: "POST",
    body: JSON.stringify({
      content: payload.content,
      provider: payload.provider ?? "openai",
      top_k: payload.topK ?? 5,
    }),
  });
}

export function updateChatMessage(payload: {
  messageId: string;
  isBookmarked?: boolean;
  rating?: number;
}): Promise<ApiSuccess<{ success: boolean }>> {
  return requestJson<{ success: boolean }>(`/chat/messages/${payload.messageId}`, {
    method: "PUT",
    body: JSON.stringify({
      is_bookmarked: payload.isBookmarked,
      rating: payload.rating,
    }),
  });
}
