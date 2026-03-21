# Architecture Diagram

## Logical Architecture

```text
                                +----------------------+
                                |      Web Client      |
                                |   (Next.js Frontend) |
                                +----------+-----------+
                                           |
                                           v
                                +----------------------+
                                |  API Gateway / BFF   |
                                |      (FastAPI)       |
                                +----+-----+-----+-----+
                                     |     |     |
                  +------------------+     |     +------------------+
                  |                        |                        |
                  v                        v                        v
        +------------------+      +------------------+      +------------------+
        | Ingestion Engine |      |  Query Engine    |      | Report Engine    |
        +--------+---------+      +--------+---------+      +--------+---------+
                 |                         |                         |
                 v                         v                         v
        +------------------+      +------------------+      +------------------+
        | Processing Engine|----->| Insight Engine   |----->| Report Artifacts |
        +--------+---------+      +--------+---------+      +------------------+
                 |                         |
                 +------------+------------+
                              |
                              v
                    +-----------------------+
                    | Storage and Retrieval |
                    | PostgreSQL + ChromaDB |
                    | local files for uploads|
                    +-----------+-----------+
                                |
                                v
                    +-----------------------+
                    |  Observability Plane  |
                    | logs/metrics/traces   |
                    +-----------------------+
```

## Cross-Cutting Control Plane

- Job lifecycle service controls async execution state (`queued`, `running`, `completed`, `failed`).
- Worker queues execute ingestion, processing, insight, and report jobs.
- Governance controls apply retention, audit logging, and access boundaries.
- Reproducibility records capture model/prompt/config versions for each run.
- Ingestion adapters target arXiv API, lightweight web scraping, and PDF upload.

## Lineage Path

`source -> document -> chunk -> retrieval evidence -> insight -> report`

Every downstream artifact stores references to upstream artifact IDs.
