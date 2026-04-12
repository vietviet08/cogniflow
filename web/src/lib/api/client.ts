import type {
    ApiError,
    ApiSuccess,
    AuthBootstrapData,
    AuthMeData,
    AuthTokenData,
    ChatMessageListData,
    ChatSendResponse,
    ChatSessionData,
    ChatSessionListData,
    HealthData,
    InsightListData,
    InsightResult,
    IntegrationConnectionData,
    IntegrationConnectionListData,
    GoogleDriveBrowseData,
    JobListData,
    JobStatusData,
    ProcessingResultData,
    ProjectListData,
    ProviderModelsData,
    ProviderSettingData,
    ProviderSettingsListData,
    ProjectData,
    QueryResultData,
    ReportLineage,
    ReportListData,
    ReportResult,
    IntegrationProvider,
    ReportType,
    SourceIngestionData,
} from "./types";
import { clearStoredAuthSession, getStoredAuthToken } from "../auth-session";

const DEFAULT_API_BASE_URL = "http://localhost:8000/api/v1";

export function getApiBaseUrl(): string {
    return process.env.NEXT_PUBLIC_API_BASE_URL ?? DEFAULT_API_BASE_URL;
}

export function createApiUrl(path: string): string {
    const base = getApiBaseUrl().replace(/\/$/, "");
    const relativePath = path.startsWith("/") ? path : `/${path}`;
    return `${base}${relativePath}`;
}

export function getSourceArtifactUrl(sourceId: string): string {
    return createApiUrl(`/sources/${sourceId}/artifact`);
}

export function getProjectIntegrationOAuthStartUrl(
    projectId: string,
    provider: IntegrationProvider,
): string {
    return createApiUrl(
        `/projects/${projectId}/integrations/${provider}/oauth/start`,
    );
}

export function startProjectIntegrationOAuth(payload: {
    projectId: string;
    provider: IntegrationProvider;
}): Promise<ApiSuccess<{ redirect_url: string }>> {
    return requestJson<{ redirect_url: string }>(
        `/projects/${payload.projectId}/integrations/${payload.provider}/oauth/start`,
    );
}

export async function requestJson<T>(
    path: string,
    init?: RequestInit,
): Promise<ApiSuccess<T>> {
    const token = getStoredAuthToken();
    const defaultHeaders: HeadersInit = {
        "content-type": "application/json",
    };
    if (token) {
        defaultHeaders.Authorization = `Bearer ${token}`;
    }

    const response = await fetch(createApiUrl(path), {
        ...init,
        headers: {
            ...defaultHeaders,
            ...init?.headers,
        },
    });

    const body = (await response.json()) as ApiSuccess<T> | ApiError;
    if (!response.ok) {
        if (response.status === 401) {
            clearStoredAuthSession();
        }
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

    const token = getStoredAuthToken();
    const response = await fetch(createApiUrl("/sources/files"), {
        method: "POST",
        headers: token
            ? {
                  Authorization: `Bearer ${token}`,
              }
            : undefined,
        body: form,
    });

    const body = (await response.json()) as
        | ApiSuccess<SourceIngestionData>
        | ApiError;
    if (!response.ok) {
        const error = body as ApiError;
        throw new Error(error.error?.message ?? "Request failed");
    }

    return body as ApiSuccess<SourceIngestionData>;
}

export function bootstrapAuth(payload: {
    email: string;
    displayName: string;
    password: string;
}): Promise<ApiSuccess<AuthBootstrapData>> {
    return requestJson<AuthBootstrapData>("/auth/bootstrap", {
        method: "POST",
        body: JSON.stringify({
            email: payload.email,
            display_name: payload.displayName,
            password: payload.password,
        }),
    });
}

export function loginAuth(payload: {
    email: string;
    password: string;
    tokenName?: string;
}): Promise<ApiSuccess<AuthTokenData>> {
    return requestJson<AuthTokenData>("/auth/login", {
        method: "POST",
        body: JSON.stringify({
            email: payload.email,
            password: payload.password,
            token_name: payload.tokenName ?? "web",
        }),
    });
}

export function getCurrentUser(): Promise<ApiSuccess<AuthMeData>> {
    return requestJson<AuthMeData>("/auth/me");
}

export function createPersonalToken(
    tokenName: string,
): Promise<ApiSuccess<AuthTokenData>> {
    return requestJson<AuthTokenData>("/auth/tokens", {
        method: "POST",
        body: JSON.stringify({ token_name: tokenName }),
    });
}

export function getJob(jobId: string): Promise<ApiSuccess<JobStatusData>> {
    return requestJson<JobStatusData>(`/jobs/${jobId}`);
}

export function listProjectJobs(
    projectId: string,
): Promise<ApiSuccess<JobListData>> {
    return requestJson<JobListData>(`/jobs/project/${projectId}`);
}

export function cancelJob(jobId: string): Promise<
    ApiSuccess<{
        job_id: string;
        status: string;
        cancel_requested_at: string | null;
    }>
> {
    return requestJson<{
        job_id: string;
        status: string;
        cancel_requested_at: string | null;
    }>(`/jobs/${jobId}/cancel`, {
        method: "POST",
    });
}

export function retryJob(
    jobId: string,
): Promise<ApiSuccess<{ job_id: string; status: string }>> {
    return requestJson<{ job_id: string; status: string }>(
        `/jobs/${jobId}/retry`,
        {
            method: "POST",
        },
    );
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
    return requestJson<ProviderSettingsListData>(
        `/projects/${projectId}/providers`,
    );
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

export function listProjectIntegrations(
    projectId: string,
): Promise<ApiSuccess<IntegrationConnectionListData>> {
    return requestJson<IntegrationConnectionListData>(
        `/projects/${projectId}/integrations`,
    );
}

export function saveProjectIntegrationConnection(payload: {
    projectId: string;
    provider: IntegrationProvider;
    accessToken?: string;
    accountLabel?: string;
    baseUrl?: string;
}): Promise<ApiSuccess<IntegrationConnectionData>> {
    return requestJson<IntegrationConnectionData>(
        `/projects/${payload.projectId}/integrations/${payload.provider}`,
        {
            method: "PUT",
            body: JSON.stringify({
                access_token: payload.accessToken,
                account_label: payload.accountLabel,
                base_url: payload.baseUrl,
            }),
        },
    );
}

export function deleteProjectIntegrationConnection(payload: {
    projectId: string;
    provider: IntegrationProvider;
}): Promise<ApiSuccess<IntegrationConnectionData>> {
    return requestJson<IntegrationConnectionData>(
        `/projects/${payload.projectId}/integrations/${payload.provider}`,
        {
            method: "DELETE",
        },
    );
}

export function importProjectIntegrationSource(payload: {
    projectId: string;
    provider: IntegrationProvider;
    itemReference: string;
}): Promise<ApiSuccess<SourceIngestionData>> {
    return requestJson<SourceIngestionData>(
        `/projects/${payload.projectId}/integrations/${payload.provider}/import`,
        {
            method: "POST",
            body: JSON.stringify({
                item_reference: payload.itemReference,
            }),
        },
    );
}

export function browseGoogleDriveItems(payload: {
    projectId: string;
    folderId?: string;
    query?: string;
    pageToken?: string;
    pageSize?: number;
}): Promise<ApiSuccess<GoogleDriveBrowseData>> {
    const params = new URLSearchParams();
    if (payload.folderId) {
        params.set("folder_id", payload.folderId);
    }
    if (payload.query) {
        params.set("q", payload.query);
    }
    if (payload.pageToken) {
        params.set("page_token", payload.pageToken);
    }
    if (payload.pageSize) {
        params.set("page_size", String(payload.pageSize));
    }

    const queryString = params.toString();
    const endpoint = `/projects/${payload.projectId}/integrations/google_drive/browse`;
    return requestJson<GoogleDriveBrowseData>(
        queryString ? `${endpoint}?${queryString}` : endpoint,
    );
}

// ---- Phase 2: Insight Layer ----

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

export function getInsight(
    insightId: string,
): Promise<ApiSuccess<InsightResult>> {
    return requestJson<InsightResult>(`/insights/${insightId}`);
}

export function listInsights(
    projectId: string,
): Promise<ApiSuccess<InsightListData>> {
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

export function updateActionItemStatus(payload: {
    reportId: string;
    itemId: string;
    status: "open" | "needs_review" | "done";
}): Promise<ApiSuccess<ReportResult>> {
    return requestJson<ReportResult>(
        `/reports/${payload.reportId}/action-items/${payload.itemId}`,
        {
            method: "PUT",
            body: JSON.stringify({ status: payload.status }),
        },
    );
}

export function getReportLineage(
    reportId: string,
): Promise<ApiSuccess<ReportLineage>> {
    return requestJson<ReportLineage>(`/reports/${reportId}/lineage`);
}

export function listReports(
    projectId: string,
): Promise<ApiSuccess<ReportListData>> {
    return requestJson<ReportListData>(`/projects/${projectId}/reports`);
}

// ---- Phase 4: UX Polish (Projects & Chat) ----

export function listProjects(): Promise<ApiSuccess<ProjectListData>> {
    return requestJson<ProjectListData>("/projects");
}

export function updateProject(
    projectId: string,
    payload: { name: string; description?: string },
): Promise<ApiSuccess<ProjectData>> {
    return requestJson<ProjectData>(`/projects/${projectId}`, {
        method: "PUT",
        body: JSON.stringify(payload),
    });
}

export function deleteProject(
    projectId: string,
): Promise<ApiSuccess<{ success: boolean }>> {
    return requestJson<{ success: boolean }>(`/projects/${projectId}`, {
        method: "DELETE",
    });
}

export function listSources(
    projectId: string,
): Promise<ApiSuccess<import("./types").SourceListData>> {
    return requestJson<import("./types").SourceListData>(
        `/sources/project/${projectId}`,
    );
}

export function deleteSources(
    sourceIds: string[],
): Promise<ApiSuccess<{ success: boolean; deleted_count: number }>> {
    return requestJson<{ success: boolean; deleted_count: number }>(
        "/sources/bulk",
        {
            method: "DELETE",
            body: JSON.stringify({ source_ids: sourceIds }),
        },
    );
}

export function createChatSession(payload: {
    projectId: string;
    title?: string;
}): Promise<ApiSuccess<ChatSessionData>> {
    return requestJson<ChatSessionData>(
        `/projects/${payload.projectId}/chat/sessions`,
        {
            method: "POST",
            body: JSON.stringify({ title: payload.title }),
        },
    );
}

export function listChatSessions(
    projectId: string,
): Promise<ApiSuccess<ChatSessionListData>> {
    return requestJson<ChatSessionListData>(
        `/projects/${projectId}/chat/sessions`,
    );
}

export function listChatMessages(
    sessionId: string,
): Promise<ApiSuccess<ChatMessageListData>> {
    return requestJson<ChatMessageListData>(
        `/chat/sessions/${sessionId}/messages`,
    );
}

export function sendChatMessage(payload: {
    sessionId: string;
    content: string;
    provider?: string;
    topK?: number;
}): Promise<ApiSuccess<ChatSendResponse>> {
    return requestJson<ChatSendResponse>(
        `/chat/sessions/${payload.sessionId}/messages`,
        {
            method: "POST",
            body: JSON.stringify({
                content: payload.content,
                provider: payload.provider ?? "openai",
                top_k: payload.topK ?? 5,
            }),
        },
    );
}

export function updateChatMessage(payload: {
    messageId: string;
    isBookmarked?: boolean;
    rating?: number;
}): Promise<ApiSuccess<{ success: boolean }>> {
    return requestJson<{ success: boolean }>(
        `/chat/messages/${payload.messageId}`,
        {
            method: "PUT",
            body: JSON.stringify({
                is_bookmarked: payload.isBookmarked,
                rating: payload.rating,
            }),
        },
    );
}
