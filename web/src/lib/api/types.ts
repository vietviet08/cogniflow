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
}

export interface ProcessingResultData {
  job_id: string;
  run_id: string;
  status: string;
  documents_created: number;
  chunks_created: number;
}

export interface CitationData {
  citation_id: string;
  source_id: string;
  document_id: string;
  chunk_id: string;
  title?: string;
  url?: string;
}

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
  title: string;
  type: string;
  format: string;
  content: string;
  status: string;
  run_id: string | null;
  insight_id: string;
  source_ids: string[];
  citations: CitationData[];
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
  title: string;
  type: string;
  format: string;
  status: string;
  created_at: string;
}

export interface ReportListData {
  items: ReportListItem[];
  total: number;
}
