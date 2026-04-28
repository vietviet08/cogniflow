# NoteMesh Demo Golden Path

Use this flow when demoing NoteMesh as a portfolio project.

## Seed Data

```bash
cd api
alembic upgrade head
python -m scripts.seed_demo
```

Default demo account:

- Email: `demo@notemesh.local`
- Password: `notemesh-demo`

## Demo Flow

1. Sign in and open `NoteMesh Portfolio Demo`.
2. Go to `/sources` and show the seeded evidence sources and processed inventory.
3. Go to `/insights` and load the market-change insight.
4. Go to `/reports` and open the action-items report with citations and lineage.
5. Go to `/actions` and show:
   - radar sources and recent high-severity event
   - daily digest and ROI metrics
   - generated GTM output and pending approval
   - action task tree for owner/status tracking
6. Go to `/jobs` and explain retry/cancel/dead-letter controls.
7. Use `/runs/{run_id}/replay` and `/runs/{left}/compare/{right}` from API docs to explain reproducibility and drift analysis.

## Interview Talking Points

- NoteMesh is not a generic chatbot; it is an evidence-first research operations system.
- Every generated artifact is tied to source evidence, run metadata, and operational controls.
- The demo shows the product loop: monitor -> detect change -> synthesize insight -> publish output -> assign action.
