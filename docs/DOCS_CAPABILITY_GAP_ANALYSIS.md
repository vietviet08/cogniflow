# Documentation Capability Mapping and Gap Analysis

## Scope

This document maps the documentation set to the four capabilities from change `improve-ai-research-infra-docs` and records resolved gaps.

Capabilities:
- research-workflow-contracts
- evidence-and-reproducibility
- operations-and-governance
- documentation-baseline

## File-to-Capability Coverage

| File | research-workflow-contracts | evidence-and-reproducibility | operations-and-governance | documentation-baseline |
|---|---|---|---|---|
| AI_RESEARCH_INFRASTRUCTURE_SPEC.md | Yes | Yes | Yes | Yes |
| API_SPEC.md | Yes | Yes | Partial | Yes |
| DATABASE_SCHEMA.sql | Yes | Yes | Yes | Yes |
| ARCHITECTURE_DIAGRAM.md | Yes | Partial | Yes | Yes |
| PROJECT_STRUCTURE.md | Partial | No | Partial | Yes |

## Gaps Identified and Resolution

### AI_RESEARCH_INFRASTRUCTURE_SPEC.md
- Gap (previous): conceptual narrative without explicit engine handoff contracts.
- Resolution: added core domain model, engine input/output contracts, lifecycle states, SLO baseline, and phase readiness criteria.

### API_SPEC.md
- Gap (previous): endpoint list without a unified async contract.
- Resolution: added common response envelope, shared job lifecycle endpoints, lineage endpoint, and replay endpoint.

### DATABASE_SCHEMA.sql
- Gap (previous): missing entities for jobs, runs, citations, and audit.
- Resolution: added `jobs`, `processing_runs`, `query_runs`, `citations`, `report_sections`, and `audit_events` with indexes and lineage relationships.

### ARCHITECTURE_DIAGRAM.md
- Gap (previous): lacked explicit control/observability planes and lineage path.
- Resolution: added logical architecture with API, engines, storage, observability, and cross-cutting control plane.

### PROJECT_STRUCTURE.md
- Gap (previous): directory layout did not define ownership boundaries.
- Resolution: added backend responsibility boundaries, documentation workflow, and recommended test layout.

## Canonical Terminology

- source: ingestion unit from file/url/rss/crawl.
- document: normalized text extracted from source.
- chunk: retrieval unit derived from document.
- job: asynchronous execution record.
- run: reproducible processing/generation context.
- insight: structured synthesis artifact.
- report: formatted output artifact.

## Canonical State Machine

Allowed states for asynchronous workflows:
- queued
- running
- completed
- failed

Usage rule:
- all long-running API operations return a `job_id` and are tracked through the same state model.

## Consistency Review Checklist (Task 5.3)

Checks performed:
- entity names are consistent across system spec, API spec, schema, and architecture docs.
- workflow states are consistent (`queued`, `running`, `completed`, `failed`).
- API endpoints and schema entities align for jobs, runs, citations, and reports.
- phase readiness criteria are present and measurable.

Result:
- no unresolved naming or lifecycle mismatches remain for this change scope.
