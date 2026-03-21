# Phase Development Checklist

Checklist này dùng để theo dõi tiến độ triển khai theo phase, bám các goal trong `AI_RESEARCH_INFRASTRUCTURE_SPEC.md`.

## Current Snapshot

Status cập nhật ngày `2026-03-22`:

- Phase hiện tại: `Phase 1 MVP complete`
- Đã có happy path MVP: `project -> ingest -> process -> query + citations`
- Chưa đóng hoàn toàn theo nghĩa production: chưa có worker async thật, chưa có latency metrics, chưa có hybrid retrieval

## Goal Coverage

- [ ] Goal 1: Transform information into actionable insight
- [x] Goal 2: Maintain durable and queryable knowledge base
- [x] Goal 3: Evidence-first outputs with citation traceability
- [ ] Goal 4: Reproducible runs for audit and drift analysis
- [ ] Goal 5: Reliable operations at async/high-volume workload

## Phase 1: Knowledge Foundation

### Scope
- [x] Ingestion baseline (file + URL) hoạt động end-to-end
- [x] Processing baseline (extract, chunk, embedding, Chroma indexing)
- [x] Retrieval baseline có semantic query path
- [ ] Hybrid retrieval path
- [ ] Async worker-based execution cho ingestion/processing

### API and Data
- [x] `POST /sources/files`, `POST /sources/urls` chạy đúng contract
- [x] `POST /jobs/processing`, `GET /jobs/{job_id}` chạy đúng baseline lifecycle state
- [x] Schema cho `projects/sources/jobs/documents/chunks` đã có trong codebase và contract
- [x] Alembic/schema/runtime model được verify đồng bộ cho Phase 1 flow sau đợt refactor

### Readiness Gate
- [x] Query trả lời có citation tối thiểu ở mức baseline
- [ ] P95 indexing lag và query latency được đo
- [x] Frontend upload + query flow đã có implementation cho Phase 1
- [ ] Smoke test backend/frontend pass trên môi trường cài đủ dependency

## Phase 2: Insight Layer

### Scope
- [ ] Insight generation flow từ evidence set
- [ ] Multi-document synthesis + theme extraction
- [ ] Comparison workflow giữa nhóm nguồn

### Contracts
- [ ] `POST /insights/generate` chạy async với `job_id`
- [ ] Insight output có citation map tới source/chunk
- [ ] Lưu run metadata (model/prompt/config hash)

### Readiness Gate
- [ ] Replay được run insight với cấu hình cũ
- [ ] Insight quality baseline có metric theo dõi
- [ ] Regression tests cho insight contract pass

## Phase 3: Report Layer

### Scope
- [ ] Generate report từ insight + evidence
- [ ] Export `markdown/pdf/json`
- [ ] Section-level citation và lineage

### Contracts
- [ ] `POST /reports/generate`, `GET /reports/{id}` hoạt động
- [ ] `GET /reports/{id}/lineage` trả đúng upstream references
- [ ] Report artifact lưu trữ được trong object storage

### Readiness Gate
- [ ] Report có thể audit ngược về source
- [ ] Formatting/export test pass
- [ ] End-to-end test `source -> report` pass

## Phase 4: Scale and Governance

### Scope
- [ ] Crawler/RSS scheduling vận hành ổn định
- [ ] Queue safety (retry/backoff/dead-letter/idempotency)
- [ ] Retention/deletion policy và audit events

### Operations
- [ ] Dashboard SLO (availability, success ratio, latency, lag)
- [ ] Alerting cho queue backlog, fail rate, timeout
- [ ] Security baseline (authN/authZ/encryption/audit) được enforce

### Readiness Gate
- [ ] Job success ratio đạt mục tiêu baseline
- [ ] Chính sách governance chạy tự động theo lịch
- [ ] Incident playbook cho lỗi trọng yếu đã có

## Cross-Phase Exit Checklist (Project Complete)

- [ ] All phase readiness gates hoàn tất
- [ ] API docs, schema, code implementation đồng bộ
- [ ] CI pipeline ổn định (lint/typecheck/test/integration)
- [ ] Reproducibility + lineage verified ở môi trường staging
- [ ] UAT với nhóm user mục tiêu pass
- [ ] Go-live checklist và rollback plan hoàn tất
