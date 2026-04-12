export interface Meta {
    request_id: string;
    timestamp: string;
}

export interface ApiSuccess<T> {
    data: T;
    meta: Meta;
}

export interface ApiError {
    error: {
        code: string;
        message: string;
        details: Record<string, unknown>;
    };
    meta: Meta;
}

export interface HealthData {
    status: string;
    service: string;
}

export type ProjectRole = "viewer" | "editor" | "owner";

export interface AuthUserData {
    id: string;
    email: string;
    display_name: string;
    role?: string;
    is_active: boolean;
    created_at: string;
}

export interface AuthBootstrapData {
    user: AuthUserData;
    token: string;
    token_last_four: string;
}

export interface AuthMeData {
    user: AuthUserData;
}

export interface AuthTokenData {
    user: AuthUserData;
    token: string;
    token_last_four: string;
}

export interface ProjectData {
    id: string;
    name: string;
    description: string | null;
    created_at: string | null;
}

export interface SourceIngestionData {
    source_id: string;
    job_id: string;
    status: string;
    source_type: string;
    filename?: string | null;
    source_version?: number;
    duplicate_of_source_id?: string | null;
}

export interface ProcessingResultData {
    job_id: string;
    status: string;
    run_id?: string;
    documents_created?: number;
    chunks_created?: number;
}

export interface JobStatusData {
    job_id: string;
    type: string;
    status:
        | "queued"
        | "running"
        | "completed"
        | "failed"
        | "cancelled"
        | "dead_letter";
    progress: number;
    attempt_count: number;
    max_retries: number;
    queue_name: string | null;
    started_at: string | null;
    finished_at: string | null;
    error: {
        code: string | null;
        message: string | null;
    } | null;
    result: Record<string, unknown> | null;
}

export interface JobListData {
    items: JobStatusData[];
    total: number;
}

export interface SourceListItemData {
    id: string;
    file_name: string;
    type: string;
    provider?: string | null;
    status: string;
    created_at: string | null;
}

export interface SourceListData {
    items: SourceListItemData[];
    total: number;
}

export interface CitationData {
    citation_id: string;
    source_id: string;
    source_type?: string;
    document_id: string;
    chunk_id: string;
    title?: string;
    url?: string;
    page_number?: number | null;
    quote?: string;
}

export type ReportType =
    | "research_brief"
    | "summary"
    | "comparison"
    | "action_items"
    | "risk_analysis"
    | "executive_brief"
    | "conflict_mesh";

export interface ActionItemData {
    id: string;
    title: string;
    description: string;
    priority: "high" | "medium" | "low";
    owner_suggested: string | null;
    due_date_suggested: string | null;
    status: "open" | "needs_review" | "done";
    citations: CitationData[];
}

export interface RiskItemData {
    id: string;
    title: string;
    severity: "high" | "medium" | "low";
    why_it_matters: string;
    recommended_action: string;
    status: "open" | "needs_review" | "accepted";
    citations: CitationData[];
}

export interface ExecutiveBriefData {
    summary: string;
    key_points: string[];
    decisions_needed: string[];
    next_steps: string[];
    citations: CitationData[];
}

export interface MeshNodeData {
    id: string;
    label: string;
    type: string;
}

export interface MeshEdgeData {
    id: string;
    source: string;
    target: string;
    type: "agrees_with" | "contradicts" | "relates_to" | string;
    description: string;
    citation_indexes?: number[];
    citations?: CitationData[];
}

export interface ActionItemsPayload {
    overview: string;
    items: ActionItemData[];
}

export interface RiskAnalysisPayload {
    overview: string;
    items: RiskItemData[];
}

export interface ExecutiveBriefPayload {
    summary: string;
    key_points: string[];
    decisions_needed: string[];
    next_steps: string[];
    citations: CitationData[];
}

export interface ConflictMeshPayload {
    overview: string;
    nodes: MeshNodeData[];
    edges: MeshEdgeData[];
}

export type StructuredReportPayload =
    | ActionItemsPayload
    | RiskAnalysisPayload
    | ExecutiveBriefPayload
    | ConflictMeshPayload
    | Record<string, unknown>;

export interface QueryResultData {
    answer: string;
    citations: CitationData[];
    run_id: string;
    provider: string;
    model: string;
}

export interface ProviderSettingData {
    provider: string;
    display_name: string;
    supports: string[];
    supports_base_url: boolean;
    configured: boolean;
    configured_source: "project" | "missing";
    masked_api_key: string | null;
    base_url: string | null;
    chat_model: string | null;
    embedding_model: string | null;
    available_chat_models: string[];
    available_embedding_models: string[];
    model_discovery_error: string | null;
    updated_at: string | null;
    removed?: boolean;
}

export interface ProviderSettingsListData {
    items: ProviderSettingData[];
}

export interface ProviderModelsData {
    provider: string;
    display_name: string;
    supports_base_url: boolean;
    base_url: string | null;
    available_chat_models: string[];
    available_embedding_models: string[];
    source: "payload" | "project";
}

export type IntegrationProvider = "google_drive";

export interface IntegrationConnectionData {
    provider: IntegrationProvider;
    display_name: string;
    supports_base_url: boolean;
    supports_oauth: boolean;
    reference_label: string;
    description: string;
    configured: boolean;
    status: string;
    account_label: string | null;
    base_url: string | null;
    masked_access_token: string | null;
    updated_at: string | null;
}

export interface IntegrationConnectionListData {
    items: IntegrationConnectionData[];
}

export interface GoogleDriveBrowseItemData {
    id: string;
    name: string;
    mime_type: string;
    web_view_link: string;
    modified_time: string | null;
    size: string | null;
    icon_link: string | null;
    is_folder: boolean;
    is_supported_import: boolean;
}

export interface GoogleDriveBrowseData {
    folder_id: string;
    items: GoogleDriveBrowseItemData[];
    next_page_token: string | null;
}

// ---- Phase 2: Insight Layer ----

export interface InsightFinding {
    theme: string;
    points: string[];
}

export interface InsightResult {
    insight_id: string;
    project_id: string;
    query: string;
    summary: string;
    findings: InsightFinding[];
    citations: CitationData[];
    run_id: string | null;
    provider: string;
    model: string;
    status: string;
    created_at: string;
}

export interface InsightListItem {
    insight_id: string;
    query: string;
    summary: string | null;
    provider: string | null;
    model: string | null;
    status: string;
    created_at: string;
}

export interface InsightListData {
    items: InsightListItem[];
    total: number;
}

// ---- Phase 3: Report Layer ----

export interface ReportResult {
    report_id: string;
    query: string;
    title: string;
    type: ReportType;
    format: string;
    content: string;
    structured_payload?: StructuredReportPayload | null;
    status: string;
    run_id: string | null;
    insight_id?: string;
    source_ids?: string[];
    citations?: CitationData[];
    created_at?: string;
}

export interface ReportLineage {
    report_id: string;
    insight_ids: string[];
    source_ids: string[];
    run_id: string | null;
}

export interface ReportListItem {
    report_id: string;
    query: string;
    title: string;
    type: ReportType;
    format: string;
    structured_payload?: StructuredReportPayload | null;
    status: string;
    created_at: string;
}

export interface ReportListData {
    items: ReportListItem[];
    total: number;
}

export type IntelligenceSeverity = "low" | "medium" | "high";

export interface IntelligenceSourceData {
    source_id: string;
    project_id: string;
    name: string;
    source_url: string;
    category: string;
    is_active: boolean;
    poll_interval_minutes: number;
    last_checked_at: string | null;
    last_content_hash: string | null;
    created_at: string | null;
    updated_at: string | null;
}

export interface IntelligenceSourceListData {
    items: IntelligenceSourceData[];
    total: number;
}

export interface IntelligenceEventData {
    event_id: string;
    project_id: string;
    source_id: string | null;
    event_type: string;
    severity: IntelligenceSeverity;
    title: string;
    summary: string;
    metadata: Record<string, unknown>;
    detected_at: string | null;
    acknowledged_at: string | null;
}

export interface IntelligenceEventListData {
    items: IntelligenceEventData[];
    total: number;
}

export interface IntelligenceScanResultData {
    checked_sources: number;
    events_created: number;
    alerts_triggered: number;
    threshold: IntelligenceSeverity;
    items: IntelligenceEventData[];
}

export interface IntelligenceDigestData {
    date: string;
    summary: {
        events_total: number;
        high: number;
        medium: number;
        low: number;
        acknowledged: number;
        open_actions: number;
    };
    items: IntelligenceEventData[];
}

export interface IntelligenceActionData {
    action_id: string;
    project_id: string;
    event_id: string | null;
    title: string;
    description: string;
    owner: string | null;
    due_date_suggested: string | null;
    priority: IntelligenceSeverity;
    status: "open" | "in_progress" | "done" | "escalated";
    channel_targets: Record<string, unknown>;
    created_at: string | null;
    updated_at: string | null;
    completed_at: string | null;
}

export interface IntelligenceActionListData {
    items: IntelligenceActionData[];
    total: number;
}

export interface IntelligenceDispatchResultData {
    action: IntelligenceActionData;
    dispatch: {
        provider: string;
        destination: string | null;
        status: string;
    };
}

export interface IntelligenceOutputData {
    output_id: string;
    project_id: string;
    event_id: string | null;
    output_type: string;
    title: string;
    content: string;
    status: string;
    created_at: string | null;
    updated_at: string | null;
}

export interface IntelligenceOutputListData {
    items: IntelligenceOutputData[];
    total: number;
}

export interface IntelligenceApprovalData {
    approval_id: string;
    project_id: string;
    target_type: string;
    target_id: string;
    status: "pending" | "approved" | "rejected";
    requested_by_user_id: string | null;
    reviewed_by_user_id: string | null;
    review_notes: string | null;
    created_at: string | null;
    reviewed_at: string | null;
}

export interface IntelligenceApprovalListData {
    items: IntelligenceApprovalData[];
    total: number;
}

export interface IntelligenceIntegrationStatusData {
    provider: string;
    connected: boolean;
    status: string;
    account_label: string | null;
    updated_at: string | null;
}

export interface IntelligenceIntegrationListData {
    items: IntelligenceIntegrationStatusData[];
}

export interface IntelligenceRoiData {
    window_days: number;
    events_total: number;
    high_events: number;
    acknowledged_rate: number;
    actions_total: number;
    actions_completed: number;
    action_completion_rate: number;
    avg_action_completion_hours: number | null;
    outputs_generated: number;
}

// ---- Phase 4: UX Polish (Projects & Chat) ----

export interface ProjectListItemData extends ProjectData {
    role: ProjectRole;
    source_count?: number;
    report_count?: number;
}

export interface ProjectListData {
    items: ProjectListItemData[];
    total: number;
}

export interface ChatSessionData {
    id: string;
    project_id: string;
    title: string | null;
    created_at: string;
}

export interface ChatSessionListData {
    items: ChatSessionData[];
    total: number;
}

export interface ChatMessageData {
    id: string;
    session_id: string;
    role: "user" | "assistant";
    content: string;
    citations: CitationData[] | null;
    is_bookmarked: boolean;
    rating: number | null;
    created_at: string;
}

export interface ChatMessageListData {
    items: ChatMessageData[];
    total: number;
}

export interface ChatSendResponse {
    user_message: {
        id: string;
        role: string;
        content: string;
    };
    assistant_message: {
        id: string;
        role: string;
        content: string;
        citations: CitationData[] | null;
    };
}
