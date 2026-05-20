# Traffic Splitting Status

## Completed

- FastAPI backend implemented
- Experiment CRUD implemented
- Pause/resume toggle implemented
- Experiment stats endpoint implemented
- Daily stats endpoint implemented
- Impression ingest endpoint implemented
- PostgreSQL schema created for `experiments`, `variants`, and `impressions`
- Alembic migration added and tested
- Frontend dashboard implemented for creating and managing experiments
- Frontend reporting view implemented
- Cloudflare KV sync from backend implemented
- Worker routing by `entry_slug` implemented
- Weighted traffic split implemented
- Traffic percentage gate implemented
- Segmentation by device type implemented
- Segmentation by traffic source implemented
- Sticky assignment implemented with KV + cookie
- UTM passthrough implemented
- Hyros `test_tag` append implemented
- Pause fallback redirect implemented
- Redirect flow tested end-to-end
- Sticky assignment tested end-to-end
- Pause behavior tested end-to-end
- Reporting tested end-to-end in development
- Monthly partitioning implemented for `impressions`
- Daily rollup table implemented for reporting
- Backend health endpoint now checks database and Redis availability
- GitHub Actions CI pipeline implemented
- GitHub Actions release/deploy workflow implemented for artifacts and manual worker deploy
- Prometheus-style `/metrics` endpoint implemented
- Request instrumentation and ingest metrics implemented
- Optional webhook alert hook implemented for Cloudflare sync failures
- Conversion ingest endpoint implemented
- Variant conversion rate / uplift / significance reporting implemented
- Monitoring summary endpoint and alert dispatch endpoint implemented
- Multivariate preview / combination generation endpoint implemented
- `GET /experiments` schema serialization bug fixed after variant metadata refactor
- Experiment list, reporting, monitoring, and conversion/significance views verified from the frontend
- Frontend multivariate builder implemented for factor/option authoring and combination generation
- Frontend multivariate reporting panels implemented for factor-level and combination-level performance
- Monitoring UI now exposes thresholds, traffic ratio, conversion rate, and alert dispatch action

## Completed With Dev-Only Workaround

- Impression delivery from worker to backend works in development through direct HTTP ingest fallback
- Remote worker preview testing works using public backend tunnel (`ngrok` / `trycloudflare`) instead of local-only backend access

## Pending

- Production queue-based impression delivery needs final end-to-end validation on real Cloudflare Queue infrastructure
- Production Worker deployment config still needs to be finalized against the live Cloudflare account/resources
- Public deployment setup for backend and frontend is not finalized
- Cloudflare route/domain setup for real entry traffic is not finalized
- Production secrets management and rotation process is not documented
- Dedicated production auth values should replace local dev keys
- Production Redis setup is not finalized
- Automated backend/frontend production deployment targets are not implemented because no hosting platform is chosen yet
- Alert routing policies, dashboards in external observability tooling, and on-call thresholds are not implemented beyond the in-app metrics/summary/webhook foundation

## Out Of Scope / Not Implemented Yet

- Slack-specific alert destinations

## Notes

- The core MVP flow from the PDF is working in development
- `impressions` table population and dashboard reporting are verified in development
- `GET /experiments` and experiment detail loading are verified again after the metadata/routing metadata schema fix
- Current worker code includes a dev fallback path so local testing does not depend on Cloudflare Queue support in preview mode
- Reporting summary/daily queries now read from rollup data instead of scanning the raw impressions table
- CI now validates backend, frontend, and worker on GitHub Actions
- Conversion significance is available once conversion events are ingested into the new `/ingest/conversions` endpoint
- Multivariate combinations can be generated through the API and forwarded by the worker via `mv_*` query params
- The frontend now supports multivariate factor authoring and shows factor/combo performance summaries from variant-level stats
