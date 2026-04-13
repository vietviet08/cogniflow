# Production Foundation Backlog

Date: 2026-04-12
Scope: NoteMesh production hardening backlog derived from the current repository state.

## Status Legend

- `[x]` Implemented
- `[~]` Partial / baseline only
- `[ ]` Not implemented

## Critical (Implement First)

### Product Differentiation and GTM

- [x] Live intelligence radar with continuous monitoring of competitor websites, pricing pages, policy updates, industry news, and customer review sources
- [x] Daily "What Changed Today" digest summarizing meaningful changes with business impact level
- [x] Threshold-based alerting for key events (price change, new competitor feature, legal or compliance risk signal)
- [x] Action center to convert alerts into tracked tasks with owner, due date, status, and escalation
- [x] One-click go-to-market outputs (battlecards, talking points, response plan, outreach drafts)
- [x] Integrations for execution workflows (Jira, Slack, email, CRM)
- [x] Approval workflow for high-impact insights and reports before team-wide broadcast
- [x] Outcome and ROI dashboard (response time reduction, opportunities created, risk mitigated, action closure rate)

### Readiness Gate

- [ ] Pilot team can run daily workflow end-to-end: monitor -> detect change -> assign action -> publish output
- [ ] At least one real customer-facing use case shows measurable weekly value (time saved, faster response, better conversion support)
- [ ] Core business alerts are delivered reliably with actionable context and owner assignment

### Execution Order (Next 8 Weeks)

- [x] Weeks 1-2: Live intelligence radar, "What Changed Today", baseline alerts
- [x] Weeks 3-4: Action center and Jira/Slack integration
- [x] Weeks 5-6: One-click outputs and approval workflow
- [x] Weeks 7-8: Outcome and ROI dashboard with pilot metrics

### Implemented in Current Iteration

- [x] Backend APIs for intelligence sources, scans, change events, acknowledgements, and daily digest
- [x] Async worker job type `intelligence_monitoring` wired into job runtime
- [x] Backend APIs for action center, dispatch workflow status, and ROI summary metrics
- [x] Backend APIs for one-click GTM outputs and approval request/review flow
- [x] Contract tests for intelligence end-to-end baseline

## Must

### Backend

- [x] Auth and project-level RBAC with user identity, bearer token validation, and project membership checks
- [x] Async worker runtime for ingestion, processing, insight, and report jobs
- [x] Job lifecycle controls for retry, cancellation, attempt tracking, and dead-letter states
- [x] Structured observability with correlation IDs, metrics, and traces across request and job flows
- [x] Contract sync guardrail for ORM models, SQL docs, migrations, and API envelopes
- [ ] Hybrid retrieval and reranking baseline
- [ ] Replay and compare runs for query, insight, and report flows

### Frontend

- [x] Auth flow and permission-aware UI states
- [x] Job operations screen with progress, retry, cancel, and failure detail
- [ ] Lineage explorer from report and insight to source, document, and chunk

### Infra

- [x] Dedicated worker process in deployment topology
- [ ] Monitoring and alerting for backlog, latency, and upstream provider failures
- [ ] Secret management hardening for provider and integration credentials

### Data

- [x] Source versioning and deduplication policy
- [ ] Artifact retention and deletion audit trail
- [ ] Evidence snapshot support for reproducible report generation

## Should

### Backend

- [ ] Conversational research engine with history-aware retrieval
- [ ] Saved search, monitoring, and scheduled reports
- [ ] Human review workflow for insights and reports
- [ ] Evaluation pipeline for retrieval quality and citation fidelity
- [ ] Expanded source connectors (Notion, Slack, Confluence, RSS scheduler)

### Frontend

- [ ] Research workspace for saved findings, notes, and pinned evidence
- [ ] Diff view between runs and reports
- [ ] Citation annotation and review feedback tools

### Infra

- [ ] Staging environment with smoke tests and seeded data
- [~] CI checks for migrations, contracts, and integration flows

### Data

- [ ] Source quality metadata (OCR confidence, parser warnings, freshness score, trust score)
- [ ] Retrieval filter metadata standardization (author, published_at, language, tags)

## Nice-to-have

### Backend

- [ ] Cost governance by project, run, provider, and model
- [ ] Publish and export adapters (Notion, Google Docs, Slack, webhook)
- [ ] Advanced report templates for recurring research workflows

### Frontend

- [ ] Collaboration comments, mentions, and shareable report snapshots
- [ ] Admin console for tenant, provider, queue, and audit health

### Infra

- [ ] Worker autoscaling by queue depth and priority
- [ ] Disaster recovery runbook and chaos drills

### Data

- [ ] Cross-project source graph and entity normalization
