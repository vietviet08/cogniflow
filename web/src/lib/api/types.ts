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
}
