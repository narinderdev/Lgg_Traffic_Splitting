# Traffic Splitting Handoff

## Overview

This project is an internal traffic-splitting / VWO-replacement system with:

- a FastAPI backend for experiment management, ingest, reporting, monitoring, and Cloudflare KV sync
- a React frontend dashboard for creating experiments and viewing reporting
- a Cloudflare Worker for edge routing, sticky assignment, segmentation, and queue-based impression delivery
- PostgreSQL for experiments, variants, impressions, conversions, and reporting rollups
- Redis for caching/reporting support

The core MVP is implemented, deployed, and validated end-to-end.

## Live Endpoints

- Frontend: `https://lgg-traffic-splitting-frontend.onrender.com`
- Backend: `https://lgg-traffic-splitting-api.onrender.com`
- Worker: `https://traffic-splitting-worker.developer-c62.workers.dev`
- Example test URL:
  `https://traffic-splitting-worker.developer-c62.workers.dev/new-entry-slug?utm_source=google&utm_medium=cpc`

## What Is Working

- experiment CRUD from the frontend
- activate/pause flow
- backend API auth
- Cloudflare KV sync from backend
- worker redirect by `entry_slug`
- weighted variant routing
- sticky assignment
- segmentation by device type and traffic source
- UTM passthrough and tracking params
- queue-based impression delivery
- impression ingestion into backend/Postgres
- reporting in the deployed frontend
- monitoring summary in the deployed frontend
- Sentry error monitoring in the deployed backend
- Sentry error monitoring in the deployed Worker

## Deployment Layout

### Render

- Backend service:
  `lgg-traffic-splitting-api`
- Frontend static site:
  `lgg-traffic-splitting-frontend`
- PostgreSQL:
  `traffic-splitting-db`
- Redis / Key Value:
  `traffic-splitting-redis`

### Cloudflare

- Worker:
  `traffic-splitting-worker`
- KV namespace binding:
  `EXPERIMENTS_KV`
- Queue binding:
  `IMPRESSIONS_QUEUE`

## Environment Ownership

### Backend

Managed in Render environment variables.

Important variables:

- `APP_ENV`
- `DATABASE_URL`
- `REDIS_URL`
- `ADMIN_API_KEY`
- `INGEST_API_KEY`
- `CORS_ORIGINS`
- `CLOUDFLARE_ACCOUNT_ID`
- `CLOUDFLARE_KV_NAMESPACE_ID`
- `CLOUDFLARE_API_TOKEN`
- `STATS_CACHE_TTL_SECONDS`
- `SENTRY_DSN`
- `SENTRY_ENVIRONMENT`
- `SENTRY_TRACES_SAMPLE_RATE`

### Frontend

Managed in Render environment variables.

Important variables:

- `VITE_API_BASE_URL`
- `VITE_API_KEY`

### Worker

Managed in [Worker/wrangler.toml](/Users/apnitormacmini3/Desktop/Traffic%20Splitting/Worker/wrangler.toml).

Important production vars:

- `BACKEND_BASE_URL`
- `INGEST_API_KEY`
- `ASSIGNMENT_TTL_SECONDS`
- `SENTRY_ENVIRONMENT`
- `SENTRY_TRACES_SAMPLE_RATE`

Managed in Cloudflare Worker secret store:

- `SENTRY_DSN`

## Local Development

Use the main project README for local setup details. The short version is:

1. start Redis
2. start backend
3. start frontend
4. expose backend if needed for remote worker testing
5. run worker in remote/dev mode

Reference:
- [README.md](/Users/apnitormacmini3/Desktop/Traffic%20Splitting/README.md)

## Routine Deploy Steps

### Backend redeploy

Render auto-deploys from the connected GitHub branch.

If backend env vars change:

1. update Render backend env vars
2. trigger a manual or automatic redeploy
3. verify:
   - `GET /`
   - `GET /health`
   - authenticated `GET /experiments`
   - Sentry project receives real backend exceptions when tested

Useful check:

```bash
curl https://lgg-traffic-splitting-api.onrender.com/experiments \
  -H "Authorization: Bearer <ADMIN_API_KEY>"
```

### Frontend redeploy

Render static site auto-deploys from the connected GitHub branch.

If frontend env vars change:

1. update Render frontend env vars
2. redeploy static site
3. verify the dashboard loads and can fetch experiments

### Worker redeploy

From [Worker](/Users/apnitormacmini3/Desktop/Traffic%20Splitting/Worker):

```bash
npx wrangler deploy
```

If worker bindings or variables change:

1. update [wrangler.toml](/Users/apnitormacmini3/Desktop/Traffic%20Splitting/Worker/wrangler.toml)
2. redeploy
3. validate with:

```bash
npx wrangler tail
```

Worker Sentry secret update:

```bash
npx wrangler secret put SENTRY_DSN
```

## Validation Checklist

After any deployment, validate in this order:

1. Backend root:
   `https://lgg-traffic-splitting-api.onrender.com`
2. Backend health:
   `https://lgg-traffic-splitting-api.onrender.com/health`
3. Frontend:
   `https://lgg-traffic-splitting-frontend.onrender.com`
4. Authenticated API:
   `GET /experiments`
5. Worker redirect:
   `https://traffic-splitting-worker.developer-c62.workers.dev/new-entry-slug?utm_source=google&utm_medium=cpc`
6. Refresh reporting in the frontend and confirm impressions increase
7. Backend Sentry verification:
   `GET /debug-sentry` with admin auth
8. Worker Sentry verification:
   `GET /debug-sentry` on the worker with ingest auth

## Expected Runtime Behavior

### Active experiment

If the experiment is active and the request matches segmentation:

- worker redirects to one of the configured variant URLs
- repeat visits in the same session keep the same assigned variant

### Paused experiment

If the experiment is paused:

- worker redirects to the configured `entry_url`

### Tracking params

Worker appends/preserves:

- `utm_source`
- `utm_medium`
- `utm_campaign`
- `utm_term`
- `utm_content`
- `gclid`
- `fbclid`
- `msclkid`
- `test_tag`
- `exp_id`
- `variant_id`
- `mv_*` params when multivariate metadata exists

## Reporting Notes

- raw `impressions` are partitioned monthly
- reporting reads from daily rollups instead of raw full-table scans
- conversions can be ingested separately through `/ingest/conversions`
- significance reporting compares variants against the control using a two-sided z-test

## Monitoring Notes

Available backend endpoints:

- `GET /metrics`
- `GET /monitoring/summary`
- `POST /monitoring/alerts/dispatch`
- `GET /debug-sentry` (temporary demo/debug route; remove after verification window)

External observability currently in place:

- Sentry project for backend exceptions/traces
- Sentry project for Worker exceptions/traces

Current monitoring stack:

- in-app monitoring summary UI
- Prometheus-style `/metrics`
- Sentry for exception observability

Grafana/Datadog-style external metrics dashboards are still optional.

## Troubleshooting

### Frontend loads but experiments do not appear

Check:

- frontend `VITE_API_BASE_URL`
- frontend `VITE_API_KEY`
- backend `ADMIN_API_KEY`
- backend `CORS_ORIGINS`

### Backend deploy fails

Common causes:

- invalid `DATABASE_URL`
- invalid `REDIS_URL`
- `APP_ENV=production` with dev API keys

Check Render logs and verify the exact connection strings from Render services.

### Worker redirects work but reporting stays at 0

Check:

- queue exists in Cloudflare
- worker `BACKEND_BASE_URL` is set in `wrangler.toml`
- worker `INGEST_API_KEY` matches backend `INGEST_API_KEY`
- `npx wrangler tail` for queue consumer errors

### Worker queue error: `undefined/ingest/impressions`

Cause:

- missing `BACKEND_BASE_URL` in worker production vars

Fix:

- update [Worker/wrangler.toml](/Users/apnitormacmini3/Desktop/Traffic%20Splitting/Worker/wrangler.toml)
- redeploy worker

### `Invalid admin API key`

Cause:

- wrong frontend API key
- wrong curl header
- Render env var mismatch

Fix:

- verify `ADMIN_API_KEY` in Render backend
- verify `VITE_API_KEY` in Render frontend

### Sentry is installed but no real backend event appears

Check:

- backend redeployed after `SENTRY_DSN` and dependency changes
- `SENTRY_DSN` is set in Render backend env
- `SENTRY_ENVIRONMENT=production`
- `GET /debug-sentry` was called with valid admin auth

### Worker Sentry deploy fails with `node:async_hooks`

Cause:

- Worker Sentry SDK requires Node compatibility

Fix:

- keep `compatibility_flags = ["nodejs_compat"]` in:
  - [Worker/wrangler.toml](/Users/apnitormacmini3/Desktop/Traffic%20Splitting/Worker/wrangler.toml)
  - [Worker/wrangler.dev.toml](/Users/apnitormacmini3/Desktop/Traffic%20Splitting/Worker/wrangler.dev.toml)

### Worker Sentry is configured but no real event appears

Check:

- `SENTRY_DSN` uploaded with `wrangler secret put SENTRY_DSN`
- Worker redeployed after adding the secret
- `/debug-sentry` on worker was called with `Authorization: Bearer <INGEST_API_KEY>`

## Remaining Optional Work

- bind the worker to a custom project domain instead of `workers.dev`
- add an external observability stack such as Grafana/Prometheus, Datadog, or Sentry
- add metrics dashboards/alerting on top of `/metrics` in Grafana/Datadog if desired
- expand multivariate editing/reporting UX further
- write a more formal operations/rollback SOP if required by the team

## Final Status

The project MVP is complete and deployed.

Validated in the deployed stack:

- frontend
- backend
- database
- Redis
- worker
- KV
- queue
- reporting
- monitoring
- backend Sentry
- worker Sentry

Remaining work is operational polish, optional observability, and optional domain customization.
