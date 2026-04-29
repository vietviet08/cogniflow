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
    InsightLineage,
    InsightResult,
    IntelligenceActionData,
    IntelligenceActionListData,
    IntelligenceActionStatus,
    IntelligenceApprovalData,
    IntelligenceApprovalListData,
    IntelligenceDigestData,
    IntelligenceDispatchResultData,
    IntelligenceEventData,
    IntelligenceEventListData,
    IntelligenceIntegrationListData,
    IntelligenceOutputData,
    IntelligenceOutputListData,
    IntelligenceRoiData,
    IntelligenceScanResultData,
    IntelligenceSourceData,
    IntelligenceSourceListData,
    IntelligenceSeverity,
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
    ReportQualityData,
    ReportResult,
    IntegrationProvider,
    ResearchReviewData,
    ResearchReviewListData,
    RunCompareData,
    SavedSearchData,
    SavedSearchListData,
    SavedSearchRunData,
    ReportType,
    ShareLinkData,
    ShareLinkListData,
    SourceIngestionData,
    OrganizationData,
    OrganizationListData,
    OpsSloData,
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

export function getOpsSlo(): Promise<ApiSuccess<OpsSloData>> {
    return requestJson<OpsSloData>("/ops/slo");
}

export function listOrganizations(): Promise<ApiSuccess<OrganizationListData>> {
    return requestJson<OrganizationListData>("/organizations");
}

export function createOrganization(payload: {
    name: string;
}): Promise<ApiSuccess<OrganizationData>> {
    return requestJson<OrganizationData>("/organizations", {
        method: "POST",
        body: JSON.stringify({ name: payload.name }),
    });
}

export function listOrganizationMembers(organizationId: string): Promise<
    ApiSuccess<{
        items: Array<{
            membership_id: string;
            user_id: string;
            email: string;
            display_name: string;
            role: string;
            joined_at: string | null;
        }>;
    }>
> {
    return requestJson<{
        items: Array<{
            membership_id: string;
            user_id: string;
            email: string;
            display_name: string;
            role: string;
            joined_at: string | null;
        }>;
    }>(`/organizations/${organizationId}/members`);
}

export function listProjectMembers(projectId: string): Promise<
    ApiSuccess<{
        items: Array<{
            membership_id: string;
            user_id: string;
            email: string;
            display_name: string;
            role: string;
            joined_at: string | null;
        }>;
        total: number;
    }>
> {
    return requestJson<{
        items: Array<{
            membership_id: string;
            user_id: string;
            email: string;
            display_name: string;
            role: string;
            joined_at: string | null;
        }>;
        total: number;
    }>(`/projects/${projectId}/members`);
}

export function addOrganizationMember(
    organizationId: string,
    email: string,
    role: string = "member",
): Promise<ApiSuccess<any>> {
    return requestJson(`/organizations/${organizationId}/members`, {
        method: "POST",
        body: JSON.stringify({ email, role }),
    });
}

export function updateOrganizationMember(
    organizationId: string,
    userId: string,
    role: string,
): Promise<ApiSuccess<any>> {
    return requestJson(`/organizations/${organizationId}/members/${userId}`, {
        method: "PATCH",
        body: JSON.stringify({ role }),
    });
}

export function removeOrganizationMember(
    organizationId: string,
    userId: string,
): Promise<ApiSuccess<any>> {
    return requestJson(`/organizations/${organizationId}/members/${userId}`, {
        method: "DELETE",
    });
}

export function createProject(payload: {
    name: string;
    description?: string;
    organizationId?: string;
}): Promise<ApiSuccess<ProjectData>> {
    return requestJson<ProjectData>("/projects", {
        method: "POST",
        body: JSON.stringify({
            name: payload.name,
            description: payload.description,
            organization_id: payload.organizationId,
        }),
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

export function getInsightLineage(
    insightId: string,
): Promise<ApiSuccess<InsightLineage>> {
    return requestJson<InsightLineage>(`/insights/${insightId}/lineage`);
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

export function getReportQuality(
    reportId: string,
): Promise<ApiSuccess<ReportQualityData>> {
    return requestJson<ReportQualityData>(`/reports/${reportId}/quality`);
}

export function listReports(
    projectId: string,
): Promise<ApiSuccess<ReportListData>> {
    return requestJson<ReportListData>(`/projects/${projectId}/reports`);
}

export function compareRuns(payload: {
    leftRunId: string;
    rightRunId: string;
}): Promise<ApiSuccess<RunCompareData>> {
    return requestJson<RunCompareData>(
        `/runs/${payload.leftRunId}/compare/${payload.rightRunId}`,
    );
}

export function requestResearchReview(payload: {
    projectId: string;
    targetType: "insight" | "report";
    targetId: string;
}): Promise<ApiSuccess<ResearchReviewData>> {
    return requestJson<ResearchReviewData>(`/projects/${payload.projectId}/reviews`, {
        method: "POST",
        body: JSON.stringify({
            target_type: payload.targetType,
            target_id: payload.targetId,
        }),
    });
}

export function listResearchReviews(payload: {
    projectId: string;
    status?: "pending" | "approved" | "rejected";
    targetType?: "insight" | "report";
}): Promise<ApiSuccess<ResearchReviewListData>> {
    const params = new URLSearchParams();
    if (payload.status) params.set("status", payload.status);
    if (payload.targetType) params.set("target_type", payload.targetType);
    const suffix = params.toString() ? `?${params.toString()}` : "";
    return requestJson<ResearchReviewListData>(
        `/projects/${payload.projectId}/reviews${suffix}`,
    );
}

export function decideResearchReview(payload: {
    projectId: string;
    reviewId: string;
    status: "approved" | "rejected";
    reviewNotes?: string;
}): Promise<ApiSuccess<ResearchReviewData>> {
    return requestJson<ResearchReviewData>(
        `/projects/${payload.projectId}/reviews/${payload.reviewId}/decision`,
        {
            method: "POST",
            body: JSON.stringify({
                status: payload.status,
                review_notes: payload.reviewNotes,
            }),
        },
    );
}

export function createSavedSearch(payload: {
    projectId: string;
    name: string;
    query: string;
    filters?: Record<string, unknown>;
    reportType?: ReportType;
    provider?: string;
    scheduleIntervalMinutes?: number | null;
    isActive?: boolean;
}): Promise<ApiSuccess<SavedSearchData>> {
    return requestJson<SavedSearchData>(
        `/projects/${payload.projectId}/saved-searches`,
        {
            method: "POST",
            body: JSON.stringify({
                name: payload.name,
                query: payload.query,
                filters: payload.filters,
                report_type: payload.reportType ?? "research_brief",
                provider: payload.provider ?? "openai",
                schedule_interval_minutes: payload.scheduleIntervalMinutes,
                is_active: payload.isActive ?? true,
            }),
        },
    );
}

export function listSavedSearches(
    projectId: string,
): Promise<ApiSuccess<SavedSearchListData>> {
    return requestJson<SavedSearchListData>(
        `/projects/${projectId}/saved-searches`,
    );
}

export function runSavedSearch(payload: {
    projectId: string;
    savedSearchId: string;
}): Promise<ApiSuccess<SavedSearchRunData>> {
    return requestJson<SavedSearchRunData>(
        `/projects/${payload.projectId}/saved-searches/${payload.savedSearchId}/run`,
        { method: "POST" },
    );
}

export function listIntelligenceSources(
    projectId: string,
): Promise<ApiSuccess<IntelligenceSourceListData>> {
    return requestJson<IntelligenceSourceListData>(
        `/projects/${projectId}/intelligence/sources`,
    );
}

export function createIntelligenceSource(payload: {
    projectId: string;
    name: string;
    sourceUrl: string;
    category?: string;
    defaultOwner?: string;
    pollIntervalMinutes?: number;
    isActive?: boolean;
}): Promise<ApiSuccess<IntelligenceSourceData>> {
    return requestJson<IntelligenceSourceData>(
        `/projects/${payload.projectId}/intelligence/sources`,
        {
            method: "POST",
            body: JSON.stringify({
                name: payload.name,
                source_url: payload.sourceUrl,
                category: payload.category ?? "general",
                default_owner: payload.defaultOwner,
                poll_interval_minutes: payload.pollIntervalMinutes ?? 1440,
                is_active: payload.isActive ?? true,
            }),
        },
    );
}

export function updateIntelligenceSource(payload: {
    projectId: string;
    sourceId: string;
    name?: string;
    sourceUrl?: string;
    category?: string;
    defaultOwner?: string;
    pollIntervalMinutes?: number;
    isActive?: boolean;
}): Promise<ApiSuccess<IntelligenceSourceData>> {
    return requestJson<IntelligenceSourceData>(
        `/projects/${payload.projectId}/intelligence/sources/${payload.sourceId}`,
        {
            method: "PUT",
            body: JSON.stringify({
                name: payload.name,
                source_url: payload.sourceUrl,
                category: payload.category,
                default_owner: payload.defaultOwner,
                poll_interval_minutes: payload.pollIntervalMinutes,
                is_active: payload.isActive,
            }),
        },
    );
}

export function triggerIntelligenceScan(payload: {
    projectId: string;
    mode?: "sync" | "async";
    sourceIds?: string[];
    alertThreshold?: IntelligenceSeverity;
}): Promise<
    ApiSuccess<
        | IntelligenceScanResultData
        | { job_id: string; status: string; mode: "async" }
    >
> {
    return requestJson<
        | IntelligenceScanResultData
        | { job_id: string; status: string; mode: "async" }
    >(`/projects/${payload.projectId}/intelligence/scan`, {
        method: "POST",
        body: JSON.stringify({
            mode: payload.mode ?? "sync",
            source_ids: payload.sourceIds,
            alert_threshold: payload.alertThreshold ?? "medium",
        }),
    });
}

export function listIntelligenceEvents(payload: {
    projectId: string;
    sinceHours?: number;
    minimumSeverity?: IntelligenceSeverity;
}): Promise<ApiSuccess<IntelligenceEventListData>> {
    const params = new URLSearchParams();
    if (payload.sinceHours)
        params.set("since_hours", String(payload.sinceHours));
    if (payload.minimumSeverity)
        params.set("minimum_severity", payload.minimumSeverity);
    const suffix = params.size ? `?${params.toString()}` : "";
    return requestJson<IntelligenceEventListData>(
        `/projects/${payload.projectId}/intelligence/events${suffix}`,
    );
}

export function acknowledgeIntelligenceEvent(payload: {
    projectId: string;
    eventId: string;
}): Promise<ApiSuccess<IntelligenceEventData>> {
    return requestJson<IntelligenceEventData>(
        `/projects/${payload.projectId}/intelligence/events/${payload.eventId}/ack`,
        { method: "POST" },
    );
}

export function getIntelligenceTodayDigest(
    projectId: string,
): Promise<ApiSuccess<IntelligenceDigestData>> {
    return requestJson<IntelligenceDigestData>(
        `/projects/${projectId}/intelligence/digest/today`,
    );
}

export function createIntelligenceAction(payload: {
    projectId: string;
    title: string;
    description: string;
    eventId?: string;
    parentActionId?: string;
    assignedUserId?: string;
    owner?: string;
    dueDateSuggested?: string;
    priority?: IntelligenceSeverity;
}): Promise<ApiSuccess<IntelligenceActionData>> {
    return requestJson<IntelligenceActionData>(
        `/projects/${payload.projectId}/intelligence/actions`,
        {
            method: "POST",
            body: JSON.stringify({
                title: payload.title,
                description: payload.description,
                event_id: payload.eventId,
                parent_action_id: payload.parentActionId,
                assigned_user_id: payload.assignedUserId,
                owner: payload.owner,
                due_date_suggested: payload.dueDateSuggested,
                priority: payload.priority ?? "medium",
            }),
        },
    );
}

export function listIntelligenceActions(payload: {
    projectId: string;
    status?: IntelligenceActionStatus;
    parentActionId?: string;
}): Promise<ApiSuccess<IntelligenceActionListData>> {
    const params = new URLSearchParams();
    if (payload.status) params.set("status", payload.status);
    if (payload.parentActionId)
        params.set("parent_action_id", payload.parentActionId);
    const suffix = params.size ? `?${params.toString()}` : "";
    return requestJson<IntelligenceActionListData>(
        `/projects/${payload.projectId}/intelligence/actions${suffix}`,
    );
}

export function updateIntelligenceAction(payload: {
    projectId: string;
    actionId: string;
    title?: string;
    description?: string;
    parentActionId?: string;
    assignedUserId?: string;
    owner?: string;
    dueDateSuggested?: string;
    priority?: IntelligenceSeverity;
    status?: IntelligenceActionStatus;
}): Promise<ApiSuccess<IntelligenceActionData>> {
    return requestJson<IntelligenceActionData>(
        `/projects/${payload.projectId}/intelligence/actions/${payload.actionId}`,
        {
            method: "PATCH",
            body: JSON.stringify({
                title: payload.title,
                description: payload.description,
                parent_action_id: payload.parentActionId,
                assigned_user_id: payload.assignedUserId,
                owner: payload.owner,
                due_date_suggested: payload.dueDateSuggested,
                priority: payload.priority,
                status: payload.status,
            }),
        },
    );
}

export function breakDownIntelligenceEvent(payload: {
    projectId: string;
    eventId: string;
}): Promise<
    ApiSuccess<{
        event_id: string;
        root_action: IntelligenceActionData;
        subtasks: IntelligenceActionData[];
        generated_count: number;
    }>
> {
    return requestJson(
        `/projects/${payload.projectId}/intelligence/events/${payload.eventId}/breakdown`,
        { method: "POST" },
    );
}

export function exportIntelligenceActions(payload: {
    projectId: string;
    format?: "csv" | "json";
    status?: IntelligenceActionStatus;
}): Promise<ApiSuccess<IntelligenceActionListData>> {
    const params = new URLSearchParams();
    params.set("format", payload.format ?? "json");
    if (payload.status) params.set("status", payload.status);
    return requestJson<IntelligenceActionListData>(
        `/projects/${payload.projectId}/intelligence/actions/export?${params.toString()}`,
    );
}

export function exportProjectInsights(payload: {
    projectId: string;
    format?: "csv" | "json";
}): Promise<
    ApiSuccess<{ items: Array<Record<string, unknown>>; total: number }>
> {
    const params = new URLSearchParams();
    params.set("format", payload.format ?? "json");
    return requestJson<{
        items: Array<Record<string, unknown>>;
        total: number;
    }>(`/insights/project/${payload.projectId}/export?${params.toString()}`);
}

export function createShareLink(payload: {
    projectId: string;
    targetType: "report" | "actions";
    targetId?: string;
    password?: string;
    expiresInHours?: number;
}): Promise<ApiSuccess<ShareLinkData>> {
    return requestJson<ShareLinkData>(
        `/projects/${payload.projectId}/share-links`,
        {
            method: "POST",
            body: JSON.stringify({
                target_type: payload.targetType,
                target_id: payload.targetId,
                password: payload.password,
                expires_in_hours: payload.expiresInHours,
            }),
        },
    );
}

export function listShareLinks(
    projectId: string,
): Promise<ApiSuccess<ShareLinkListData>> {
    return requestJson<ShareLinkListData>(`/projects/${projectId}/share-links`);
}

export function revokeShareLink(payload: {
    projectId: string;
    linkId: string;
}): Promise<ApiSuccess<{ success: boolean }>> {
    return requestJson<{ success: boolean }>(
        `/projects/${payload.projectId}/share-links/${payload.linkId}`,
        { method: "DELETE" },
    );
}

export function dispatchIntelligenceAction(payload: {
    projectId: string;
    actionId: string;
    provider: string;
    destination?: string;
}): Promise<ApiSuccess<IntelligenceDispatchResultData>> {
    return requestJson<IntelligenceDispatchResultData>(
        `/projects/${payload.projectId}/intelligence/actions/${payload.actionId}/dispatch`,
        {
            method: "POST",
            body: JSON.stringify({
                provider: payload.provider,
                destination: payload.destination,
            }),
        },
    );
}

export function listIntelligenceIntegrations(
    projectId: string,
): Promise<ApiSuccess<IntelligenceIntegrationListData>> {
    return requestJson<IntelligenceIntegrationListData>(
        `/projects/${projectId}/intelligence/integrations`,
    );
}

export function saveIntelligenceIntegrationConnection(payload: {
    projectId: string;
    provider: "jira" | "slack" | "email" | "crm";
    accessToken?: string;
    accountLabel?: string;
    baseUrl?: string;
    connectionMetadata?: Record<string, unknown>;
}): Promise<ApiSuccess<import("./types").IntelligenceIntegrationStatusData>> {
    return requestJson<import("./types").IntelligenceIntegrationStatusData>(
        `/projects/${payload.projectId}/intelligence/integrations/${payload.provider}`,
        {
            method: "PUT",
            body: JSON.stringify({
                access_token: payload.accessToken,
                account_label: payload.accountLabel,
                base_url: payload.baseUrl,
                connection_metadata: payload.connectionMetadata,
            }),
        },
    );
}

export function deleteIntelligenceIntegrationConnection(payload: {
    projectId: string;
    provider: "jira" | "slack" | "email" | "crm";
}): Promise<ApiSuccess<import("./types").IntelligenceIntegrationStatusData>> {
    return requestJson<import("./types").IntelligenceIntegrationStatusData>(
        `/projects/${payload.projectId}/intelligence/integrations/${payload.provider}`,
        {
            method: "DELETE",
        },
    );
}

export function createIntelligenceOutput(payload: {
    projectId: string;
    outputType:
        | "battlecard"
        | "talking_points"
        | "response_plan"
        | "outreach_draft";
    eventId?: string;
    context?: string;
}): Promise<ApiSuccess<IntelligenceOutputData>> {
    return requestJson<IntelligenceOutputData>(
        `/projects/${payload.projectId}/intelligence/outputs`,
        {
            method: "POST",
            body: JSON.stringify({
                output_type: payload.outputType,
                event_id: payload.eventId,
                context: payload.context,
            }),
        },
    );
}

export function listIntelligenceOutputs(
    projectId: string,
): Promise<ApiSuccess<IntelligenceOutputListData>> {
    return requestJson<IntelligenceOutputListData>(
        `/projects/${projectId}/intelligence/outputs`,
    );
}

export function requestIntelligenceApproval(payload: {
    projectId: string;
    targetType: string;
    targetId: string;
}): Promise<ApiSuccess<IntelligenceApprovalData>> {
    return requestJson<IntelligenceApprovalData>(
        `/projects/${payload.projectId}/intelligence/approvals`,
        {
            method: "POST",
            body: JSON.stringify({
                target_type: payload.targetType,
                target_id: payload.targetId,
            }),
        },
    );
}

export function reviewIntelligenceApproval(payload: {
    projectId: string;
    approvalId: string;
    status: "approved" | "rejected";
    reviewNotes?: string;
}): Promise<ApiSuccess<IntelligenceApprovalData>> {
    return requestJson<IntelligenceApprovalData>(
        `/projects/${payload.projectId}/intelligence/approvals/${payload.approvalId}/review`,
        {
            method: "POST",
            body: JSON.stringify({
                status: payload.status,
                review_notes: payload.reviewNotes,
            }),
        },
    );
}

export function listIntelligenceApprovals(payload: {
    projectId: string;
    status?: "pending" | "approved" | "rejected";
}): Promise<ApiSuccess<IntelligenceApprovalListData>> {
    const suffix = payload.status ? `?status=${payload.status}` : "";
    return requestJson<IntelligenceApprovalListData>(
        `/projects/${payload.projectId}/intelligence/approvals${suffix}`,
    );
}

export function getIntelligenceRoiDashboard(payload: {
    projectId: string;
    windowDays?: number;
}): Promise<ApiSuccess<IntelligenceRoiData>> {
    const suffix = payload.windowDays
        ? `?window_days=${payload.windowDays}`
        : "";
    return requestJson<IntelligenceRoiData>(
        `/projects/${payload.projectId}/intelligence/roi${suffix}`,
    );
}

// ---- Phase 4: UX Polish (Projects & Chat) ----

export function listProjects(payload?: {
    organizationId?: string;
}): Promise<ApiSuccess<ProjectListData>> {
    const params = new URLSearchParams();
    if (payload?.organizationId) {
        params.set("organization_id", payload.organizationId);
    }
    const suffix = params.size ? `?${params.toString()}` : "";
    return requestJson<ProjectListData>(`/projects${suffix}`);
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
