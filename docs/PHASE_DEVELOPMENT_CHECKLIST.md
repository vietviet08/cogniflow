# Phase Development Checklist

Checklist này dùng để theo dõi tiến độ triển khai theo phase, bám các goal trong `AI_RESEARCH_INFRASTRUCTURE_SPEC.md`.

## Current Snapshot

Status cập nhật ngày `2026-04-29`:

- Theo roadmap của bạn: `Phase 1 complete`, `Phase 2 complete`, `Phase 3 baseline complete`
- Theo phase naming trong docs repo: `Phase 1 complete`, `Phase 2 Insight Layer chưa bắt đầu`
- Đã có happy path MVP: `project -> ingest -> process -> query + citations`
- Processing runtime hiện có `processing_runs`, reprocess không nhân bản dữ liệu, và có API inventory cho `documents/chunks/runs`
- Retrieval embedding đã chuyển sang local `sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2`
- Đã có baseline production foundation cho `auth/RBAC`, `async worker`, và `request/job observability`
- Đã có P0 portfolio readiness baseline: frontend build sạch, Dockerfile backend, static export,
  demo seed/golden path, intelligence radar dashboard, và run replay/compare baseline
- Đã có P1 portfolio readiness baseline: hybrid retrieval/reranking, lineage explorer,
  operations SLO dashboard, secret encryption, deletion audit trail, và evidence snapshots
- Đã có P2 portfolio readiness baseline: history-aware chat, saved searches/scheduled report queue,
  report quality evaluation, report diff viewer, research review workflow, source quality metadata,
  staging smoke script, và CI contract/migration/build guardrails
- Vẫn chưa đóng hoàn toàn theo nghĩa production: chưa có UAT pilot thật, connector mở rộng đầy đủ
  cho Notion/Slack/Confluence/RSS, và go-live incident playbook đầy đủ

## Roadmap Mapping

- Roadmap `Phase 1 - Data Ingestion` tương ứng với ingestion baseline trong repo `Phase 1`
- Roadmap `Phase 2 - Processing + Embedding` tương ứng với processing baseline trong repo `Phase 1`
- Roadmap `Phase 3 - RAG Core` tương ứng với retrieval/query baseline trong repo `Phase 1`
- Roadmap `Phase 4 - Intelligence Layer` tương ứng với repo `Phase 2 - Insight Layer`
- Roadmap `Phase 5 - UI + Deploy + Demo` trải ngang các phase repo, chủ yếu là web/demo/deploy readiness

## User Roadmap Phase 2: Processing + Embedding

### Scope
- [x] Chunking theo token với cấu hình nằm trong vùng `500-1000` token dùng được cho demo
- [x] Local embedding model mặc định là `sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2`
- [x] ChromaDB lưu vector + metadata `project_id/source_id/document_id/chunk_id`
- [x] Processing run lưu `model_id`, `config_hash`, `run_metadata`
- [x] Reprocessing cùng source thay thế document/chunk cũ thay vì nhân bản
- [x] Có API để inspect `documents`, `chunks`, `processing_runs` sau khi xử lý
- [x] Async worker hóa processing flow
- [x] Metrics/observability cho indexing latency

## Goal Coverage

- [x] Goal 1: Transform information into actionable insight
- [x] Goal 2: Maintain durable and queryable knowledge base
- [x] Goal 3: Evidence-first outputs with citation traceability
- [x] Goal 4: Reproducible runs for audit and drift analysis
- [~] Goal 5: Reliable operations at async/high-volume workload

## Phase 1: Knowledge Foundation

### Scope
- [x] Ingestion baseline (file + URL) hoạt động end-to-end
- [x] Processing baseline (extract, chunk, embedding, Chroma indexing)
- [x] Retrieval baseline có semantic query path
- [x] Hybrid retrieval path
- [x] Async worker-based execution cho processing

### API and Data
- [x] `POST /sources/files`, `POST /sources/urls` chạy đúng contract
- [x] `POST /jobs/processing`, `GET /jobs/{job_id}` chạy đúng baseline lifecycle state
- [x] Schema cho `projects/sources/jobs/documents/chunks/processing_runs` đã có trong codebase và contract
- [x] Alembic/schema/runtime model được verify đồng bộ cho Phase 1 flow sau đợt refactor
- [x] `GET /projects/{project_id}/documents|chunks|processing-runs` mở được inventory của dữ liệu đã xử lý

### Readiness Gate
- [x] Query trả lời có citation tối thiểu ở mức baseline
- [x] P95 indexing lag và query latency được đo
- [x] Frontend upload + query flow đã có implementation cho Phase 1
- [x] Smoke test backend/frontend pass trên môi trường cài đủ dependency

## Phase 2: Insight Layer

### Scope
- [x] Insight generation flow từ evidence set
- [x] Multi-document synthesis + theme extraction
- [x] Comparison workflow giữa nhóm nguồn

### Contracts
- [x] `POST /insights/generate` chạy async với `job_id` (synchronous API wrapper available)
- [x] Insight output có citation map tới source/chunk
- [x] Lưu run metadata (model/prompt/config hash/evidence snapshot)

### Readiness Gate
- [x] Replay được run insight với cấu hình cũ
- [x] Insight/report quality baseline có metric theo dõi
- [x] Regression tests cho insight contract pass

## Phase 3: Report Layer

### Scope
- [x] Generate report từ insight + evidence
- [x] Export `markdown/pdf/json` (markdown built)
- [x] Section-level citation và lineage

### Contracts
- [x] `POST /reports/generate`, `GET /reports/{id}` hoạt động
- [x] `GET /reports/{id}/lineage` trả đúng upstream references
- [x] `GET /reports/{id}/quality` trả quality/citation fidelity checks
- [x] Report artifact lưu trữ được trong object storage (database backed)

### Readiness Gate
- [x] Report có thể audit ngược về source
- [x] Formatting/export test pass
- [ ] End-to-end test `source -> report` pass

## Phase 4: Conflict Mesh (Visual Knowledge Graph)

### Scope
- [x] Backend: Pipeline `mesh_pipeline` để trích xuất Concepts (Nodes) và Relationships/Conflicts (Edges) qua LLM structured output.
- [x] Backend: Thiết lập Job gọi AI, nhận JSON lưu vào cột `structured_payload` của `reports` với `report_type="conflict_mesh"`.
- [x] Frontend: Tích hợp thư viện graph 3D (`react-force-graph-3d`/Three.js).
- [x] Frontend: View `/mesh` render đồ thị trực quan và sidebar chi tiết Conflict.

### Readiness Gate
- [ ] Upload 2 tài liệu cố tình mâu thuẫn và render thành công Node mâu thuẫn trên đồ thị.

## Phase 5: Scale and Governance

### Scope
- [~] Crawler/RSS scheduling vận hành ổn định (saved-search scheduled report queue baseline đã có)
- [ ] Queue safety (retry/backoff/dead-letter/idempotency)
- [x] Retention/deletion policy và audit events
- [x] Saved searches cho recurring research workflows
- [x] Source quality metadata và retrieval filters chuẩn hóa

### Operations
- [x] Dashboard SLO (availability, success ratio, latency, lag)
- [x] Alerting cho queue backlog, fail rate, timeout
- [x] Security baseline (authN/authZ/encryption/audit) được enforce

### Readiness Gate
- [~] Job success ratio đạt mục tiêu baseline
- [~] Chính sách governance chạy tự động theo lịch
- [ ] Incident playbook cho lỗi trọng yếu đã có

## Cross-Phase Exit Checklist (Project Complete)

- [ ] All phase readiness gates hoàn tất
- [x] API docs, schema, code implementation đồng bộ cho auth/worker/observability baseline
- [x] CI pipeline ổn định (lint/typecheck/test/integration)
- [x] Reproducibility + lineage verified ở môi trường staging
- [ ] UAT với nhóm user mục tiêu pass
- [ ] Go-live checklist và rollback plan hoàn tất
