# Phase Development Checklist

Checklist này dùng để theo dõi tiến độ triển khai theo phase, bám các goal trong `AI_RESEARCH_INFRASTRUCTURE_SPEC.md`.

## Goal Coverage

- [ ] Goal 1: Transform information into actionable insight
- [ ] Goal 2: Maintain durable and queryable knowledge base
- [ ] Goal 3: Evidence-first outputs with citation traceability
- [ ] Goal 4: Reproducible runs for audit and drift analysis
- [ ] Goal 5: Reliable operations at async/high-volume workload

## Phase 1: Knowledge Foundation

### Scope
- [ ] Ingestion baseline (file + URL) hoạt động async
- [ ] Processing baseline (extract, chunk, embedding pipeline scaffold)
- [ ] Retrieval baseline có semantic/hybrid query path

### API and Data
- [ ] `POST /sources/files`, `POST /sources/urls` chạy đúng contract
- [ ] `POST /jobs/processing`, `GET /jobs/{job_id}` chạy đúng lifecycle state
- [ ] Schema cho `projects/sources/jobs/documents/chunks` đã migrate

### Readiness Gate
- [ ] Query trả lời có citation tối thiểu ở mức baseline
- [ ] P95 indexing lag và query latency được đo
- [ ] Smoke test backend/frontend pass

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
