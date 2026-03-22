# API Specification

## Base

- Base path: `/api/v1`
- Content type: `application/json`
- Authentication: bearer token (required for non-public endpoints)

## Common Response Envelope

Successful response:

```json
{
  "data": {},
  "meta": {
    "request_id": "req_123",
    "timestamp": "2026-03-15T10:00:00Z"
  }
}
```

Error response:

```json
{
  "error": {
    "code": "JOB_NOT_FOUND",
    "message": "Job does not exist",
    "details": {}
  },
  "meta": {
    "request_id": "req_123",
    "timestamp": "2026-03-15T10:00:00Z"
  }
}
```

## Domain Models

### JobStatus

Allowed values:
- `queued`
- `running`
- `completed`
- `failed`

## Projects

### Create Project

`POST /projects`

Request:

```json
{
  "name": "AI agents landscape",
  "description": "Research project for market mapping"
}
```

## Ingestion

### Upload Source File

`POST /sources/files`

Request: `multipart/form-data`
- `project_id`
- `file` (pdf, docx, txt)

Response data:

```json
{
  "source_id": "src_001",
  "job_id": "job_ingest_001",
  "status": "completed",
  "source_type": "file",
  "filename": "paper.pdf"
}
```

### Ingest Source URL

`POST /sources/urls`

Request:

```json
{
  "project_id": "prj_001",
  "url": "https://example.com/article"
}
```

Response data:

```json
{
  "source_id": "src_002",
  "job_id": "job_ingest_002",
  "status": "completed",
  "source_type": "arxiv"
}
```

## Processing

### Start Processing Job

`POST /jobs/processing`

Request:

```json
{
  "project_id": "prj_001",
  "source_ids": ["src_001", "src_002"],
  "options": {
    "chunk_size": 800,
    "chunk_overlap": 120
  }
}
```

Response data:

```json
{
  "job_id": "job_process_001",
  "run_id": "run_process_001",
  "status": "completed",
  "documents_created": 2,
  "chunks_created": 14
}
```

### List Processed Documents

`GET /projects/{project_id}/documents`

Response data:

```json
{
  "items": [
    {
      "document_id": "doc_001",
      "source_id": "src_001",
      "title": "Paper A",
      "source_type": "file",
      "original_uri": "paper.pdf",
      "token_count": 1420,
      "chunk_count": 4,
      "created_at": "2026-03-22T10:00:00Z"
    }
  ],
  "total": 1
}
```

### List Indexed Chunks

`GET /projects/{project_id}/chunks`

Query params:
- `source_id` (optional)
- `document_id` (optional)
- `limit` (optional, default `50`)

Response data:

```json
{
  "items": [
    {
      "chunk_id": "chk_001",
      "document_id": "doc_001",
      "source_id": "src_001",
      "chunk_index": 0,
      "embedding_model": "text-embedding-3-small",
      "metadata": {
        "project_id": "prj_001",
        "source_id": "src_001",
        "document_id": "doc_001",
        "chunk_id": "chk_001"
      },
      "preview": "Transformer agents rely on retrieval...",
      "title": "Paper A"
    }
  ],
  "total": 1,
  "limit": 50
}
```

### List Processing Runs

`GET /projects/{project_id}/processing-runs`

Response data:

```json
{
  "items": [
    {
      "run_id": "run_process_001",
      "job_id": "job_process_001",
      "run_type": "processing",
      "model_id": "text-embedding-3-small",
      "config_hash": "cfg_abc123",
      "run_metadata": {
        "source_count": 2,
        "documents_created": 2,
        "chunks_created": 14
      },
      "created_at": "2026-03-22T10:00:00Z"
    }
  ],
  "total": 1
}
```

## Jobs

### Get Job Status

`GET /jobs/{job_id}`

Response data:

```json
{
  "job_id": "job_process_001",
  "type": "processing",
  "status": "running",
  "progress": 62,
  "error": null
}
```

### Cancel Job

`POST /jobs/{job_id}/cancel`

### Retry Job

`POST /jobs/{job_id}/retry`

## Query

### Search Knowledge

`POST /query/search`

Request:

```json
{
  "project_id": "prj_001",
  "query": "What are major trends in AI agent infrastructure?",
  "filters": {
    "source_types": ["url", "pdf"]
  },
  "top_k": 8
}
```

Response data:

```json
{
  "answer": "...",
  "citations": [
    {
      "citation_id": "chk_045",
      "source_id": "src_001",
      "document_id": "doc_001",
      "chunk_id": "chk_045",
      "title": "Paper A",
      "url": "https://arxiv.org/abs/1234.5678"
    }
  ],
  "run_id": "run_query_001"
}
```

## Insights

### Generate Insights

`POST /insights/generate`

Request:

```json
{
  "project_id": "prj_001",
  "query": "Compare open-source vs managed agent platforms",
  "evidence_scope": {
    "max_sources": 20
  }
}
```

Response data:

```json
{
  "job_id": "job_insight_001",
  "status": "queued"
}
```

## Reports

### Generate Report

`POST /reports/generate`

Request:

```json
{
  "project_id": "prj_001",
  "type": "research_brief",
  "query": "AI research infrastructure 2026",
  "format": "markdown"
}
```

Response data:

```json
{
  "job_id": "job_report_001",
  "status": "queued"
}
```

### Get Report

`GET /reports/{report_id}`

### Get Report Lineage

`GET /reports/{report_id}/lineage`

Response data:

```json
{
  "report_id": "rep_001",
  "insight_ids": ["ins_001", "ins_002"],
  "source_ids": ["src_001", "src_005"],
  "run_id": "run_report_001"
}
```

## Reproducibility

### Replay a Previous Run

`POST /runs/{run_id}/replay`

Response data:

```json
{
  "job_id": "job_replay_001",
  "status": "queued"
}
```

## API Design Rules

- All long-running operations MUST return a `job_id`.
- All generated outputs MUST include or resolve to citations.
- All generation runs MUST persist reproducibility metadata.
- Breaking changes MUST use explicit API version bump.
