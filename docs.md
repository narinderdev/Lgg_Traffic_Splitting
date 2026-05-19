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

## Completed With Dev-Only Workaround

- Impression delivery from worker to backend works in development through direct HTTP ingest fallback
- Remote worker preview testing works using public backend tunnel (`ngrok` / `trycloudflare`) instead of local-only backend access

## Pending

- Production queue-based impression delivery needs final production validation
- Production Worker deployment config still needs to be finalized
- Cloudflare Queue consumer flow needs full production verification
- Public deployment setup for backend/frontend/worker is not finalized
- Cloudflare route/domain setup for real entry traffic is not finalized
- Production secrets management and rotation process is not documented
- Dedicated production auth values should replace local dev keys
- Monthly partitioning for `impressions` table is not implemented
- Rollup/aggregation table for reporting is not implemented
- Advanced monitoring/alerting is not implemented
- CI/CD pipeline is not implemented
- Production Redis setup is not finalized

## Out Of Scope / Not Implemented Yet

- Multivariate testing
- Statistical significance tooling
- Slack/webhook alerting

## Notes

- The core MVP flow from the PDF is working in development
- `impressions` table population and dashboard reporting are verified in development
- Current worker code includes a dev fallback path so local testing does not depend on Cloudflare Queue support in preview mode
