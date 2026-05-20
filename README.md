# Traffic Splitting

Internal VWO replacement for URL-based traffic splitting.

## What Is Implemented

- FastAPI backend for experiment CRUD, pause/resume, impression ingest, and reporting
- PostgreSQL schema + Alembic migration for `experiments`, `variants`, and `impressions`
- Redis-backed caching layer for reporting endpoints
- Prometheus-style metrics endpoint and request instrumentation
- Optional webhook-based alert hooks for Cloudflare sync failures
- React admin dashboard for experiment management and reporting
- Cloudflare Worker for slug-based routing, weighted variant selection, sticky assignment, UTM passthrough, and Hyros `test_tag`
- Cloudflare KV sync from backend to edge config
- Conversion ingest endpoint plus significance-aware reporting
- Monitoring summary and alert-evaluation endpoints
- Multivariate preview endpoint that generates factor combinations for use with the existing worker/variant model
- Experiment list/detail serialization verified after the variant metadata schema refactor
- Frontend multivariate builder for factor/option authoring and generated variant application
- Frontend multivariate reporting panels for factor-level and combination-level performance
- Monitoring UI support for threshold visibility, traffic/conversion ratios, and alert dispatch

## Project Structure

- [Backend](./Backend)
- [Frontend](./Frontend)
- [Worker](./Worker)
- [docs.md](./docs.md)

## Local Development Runbook

Use 5 terminals if you want the full local flow, including reporting from remote worker preview.

### Terminal 1: Redis

```bash
redis-server
```

`REDIS_URL` in [Backend/.env](</Users/apnitormacmini3/Desktop/Traffic Splitting/Backend/.env>) already points to:

```env
redis://127.0.0.1:6379/0
```

### Terminal 2: Backend

From `/Users/apnitormacmini3/Desktop/Traffic Splitting/Backend`:

```bash
source .venv/bin/activate
alembic upgrade head
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

Backend uses [Backend/.env](</Users/apnitormacmini3/Desktop/Traffic Splitting/Backend/.env>).

Important local values:

```env
DATABASE_URL=postgresql://apnitormacmini3@localhost:5432/traffic_splitting
ADMIN_API_KEY=dev-admin-key
INGEST_API_KEY=dev-ingest-key
```

Optional monitoring/alerts values:

```env
APP_ENV=development
ALERT_WEBHOOK_URL=
```

### Terminal 3: Expose Backend Publicly For Worker Testing

The remote Cloudflare Worker cannot call `http://127.0.0.1:8000` directly, so expose the backend with ngrok:

```bash
ngrok http 8000
```

Take the HTTPS forwarding URL from ngrok, for example:

```txt
https://your-subdomain.ngrok-free.app
```

Put that URL into [Worker/.dev.vars](</Users/apnitormacmini3/Desktop/Traffic Splitting/Worker/.dev.vars>):

```env
BACKEND_BASE_URL=https://your-subdomain.ngrok-free.app
INGEST_API_KEY=dev-ingest-key
ASSIGNMENT_TTL_SECONDS=2592000
ALLOW_DIRECT_INGEST_FALLBACK=true
```

If the ngrok URL changes, update `BACKEND_BASE_URL` and restart the worker.

### Terminal 4: Frontend

From `/Users/apnitormacmini3/Desktop/Traffic Splitting/Frontend`:

```bash
npm run dev
```

Frontend uses [Frontend/.env](</Users/apnitormacmini3/Desktop/Traffic Splitting/Frontend/.env>).

Default local values:

```env
VITE_API_BASE_URL=http://127.0.0.1:8000
VITE_API_KEY=dev-admin-key
```

Open:

```txt
http://localhost:5173
```

### Terminal 5: Worker

From `/Users/apnitormacmini3/Desktop/Traffic Splitting/Worker`:

```bash
npm run dev:remote
```

For local testing, use `dev:remote`, not plain `wrangler dev`, because:

- we need real Cloudflare KV access
- the worker uses remote preview for redirect testing
- the worker has a dev fallback path that posts impressions directly to the backend instead of relying on queues in preview mode

Test a slug like:

```txt
http://localhost:8787/new-entry-slug?utm_source=google&utm_medium=cpc
```

The worker now appends these query params to destination URLs so conversion events can be attributed back to the experiment:

- `exp_id`
- `variant_id`
- `test_tag`

## Cloudflare Worker Configuration

### If You Are Using The Existing Glowante Cloudflare Account

The current worker config is already wired to the Cloudflare account used during development.

Current files:

- [Worker/wrangler.toml](/Users/apnitormacmini3/Desktop/Traffic%20Splitting/Worker/wrangler.toml)
- [Worker/wrangler.dev.toml](/Users/apnitormacmini3/Desktop/Traffic%20Splitting/Worker/wrangler.dev.toml)

Current remote preview flow assumes access to the Cloudflare account connected to `developer@glowante.com`.

That means:

- Wrangler login must use the same Cloudflare account that owns the configured KV namespace
- if you log in with another Cloudflare account that does not own that namespace, worker preview will fail

### If Someone Else Runs This On Another System Or Cloudflare Account

They need to replace the Cloudflare-specific bindings with values from their own account.

Required changes:

1. Backend env:

Set these in [Backend/.env](</Users/apnitormacmini3/Desktop/Traffic Splitting/Backend/.env>):

```env
CLOUDFLARE_ACCOUNT_ID=their_account_id
CLOUDFLARE_KV_NAMESPACE_ID=their_kv_namespace_id
CLOUDFLARE_API_TOKEN=their_api_token
```

2. Worker config:

Update both:

- [Worker/wrangler.toml](/Users/apnitormacmini3/Desktop/Traffic%20Splitting/Worker/wrangler.toml)
- [Worker/wrangler.dev.toml](/Users/apnitormacmini3/Desktop/Traffic%20Splitting/Worker/wrangler.dev.toml)

Replace:

- `kv_namespaces.id`
- `kv_namespaces.preview_id`

with namespace IDs from their own Cloudflare account.

3. If they want production queue-based ingest:

They must also create their own Cloudflare Queue and update:

- `[[queues.producers]]`
- `[[queues.consumers]]`

in [Worker/wrangler.toml](/Users/apnitormacmini3/Desktop/Traffic%20Splitting/Worker/wrangler.toml).

4. Wrangler authentication:

They must log into Wrangler using the Cloudflare account that owns those Worker/KV/Queue resources.

## GitHub Actions CI/CD

This repo now includes GitHub Actions workflows in [.github/workflows](./.github/workflows):

- `ci.yml`
  - backend: installs dependencies, runs `ruff`, applies Alembic migrations against Postgres, runs `pytest`, and compiles the app
  - frontend: runs `npm ci`, `npm run lint`, and `npm run build`
  - worker: runs `npm ci` and `npm run check`
- `cd.yml`
  - builds a backend package artifact
  - builds a frontend static artifact
  - can manually deploy the Cloudflare Worker with `workflow_dispatch`

### Required GitHub Secrets For Worker Deploy

Set these repository or environment secrets before using the manual worker deploy job:

```txt
CLOUDFLARE_API_TOKEN
CLOUDFLARE_ACCOUNT_ID
```

The deploy job uses `Worker/wrangler.toml`, so production KV and queue bindings must already be correct there.

## Recommended Local Test Flow

1. Start Redis
2. Start backend
3. Start ngrok for backend `8000`
4. Update `BACKEND_BASE_URL` in `Worker/.dev.vars`
5. Start frontend
6. Start worker with `npm run dev:remote`
7. Create an experiment in the frontend
8. Activate the experiment
9. Visit the worker slug URL
10. Refresh reporting in the frontend

If you want to test conversions/significance locally, POST conversion events to:

```txt
POST /ingest/conversions
```

Example payload:

```json
{
  "events": [
    {
      "experiment_id": "00521e5f-6914-4cbb-9523-24d09039fa13",
      "variant_id": "12f4288b-e263-4af8-9420-48c24d9d3f29",
      "conversion_type": "signup",
      "visitor_id": "optional-visitor-id"
    }
  ]
}
```

Send it with:

```txt
Authorization: Bearer dev-ingest-key
```

Monitoring endpoints:

- `GET /metrics`
- `GET /monitoring/summary`
- `POST /monitoring/alerts/dispatch`

Multivariate preview endpoint:

```txt
POST /experiments/multivariate/preview
```

Example payload:

```json
{
  "destination_url": "https://example.com/landing",
  "hyros_tag_prefix": "mv",
  "factors": [
    {
      "key": "headline",
      "label": "Headline",
      "options": [
        { "key": "a", "label": "A" },
        { "key": "b", "label": "B" }
      ]
    },
    {
      "key": "cta",
      "label": "CTA",
      "options": [
        { "key": "x", "label": "X" },
        { "key": "y", "label": "Y" }
      ]
    }
  ]
}
```

The response returns generated combination variants with equalized weights and `multivariate_values` metadata. The worker automatically forwards these assignments as query params such as `mv_headline=a`.

The frontend now includes a multivariate builder that calls this preview endpoint and applies the generated combinations into the experiment draft before save.

## Example Behavior

If:

- experiment is `active`
- traffic is admitted by segmentation

then:

```txt
http://localhost:8787/new-entry-slug?utm_source=google&utm_medium=cpc
```

should redirect to one of the configured variant URLs.

If:

- experiment is `paused`

then it should redirect to the configured `entry_url`.

## Notes

- Redis is optional in development, but recommended for testing reporting cache behavior
- `wrangler dev --remote` with queue bindings was unstable during development, so local testing uses direct HTTP ingest fallback in worker preview mode
- Production should still use the intended queue-based ingest path
- Raw `impressions` data is now monthly partitioned, and reporting reads from daily rollups
- `/metrics` exposes Prometheus-compatible metrics for API traffic, ingest counts, and Cloudflare sync activity
- Significance reporting currently uses a two-sided z-test against the control variant based on ingested conversion counts
- Monitoring summaries evaluate configurable thresholds from env vars like `ALERT_LOOKBACK_MINUTES` and `ALERT_MIN_TRAFFIC_RATIO`
- Multivariate support now includes a frontend builder and reporting overlays, but it still uses the existing variant model under the hood
- `GET /experiments`, frontend experiment loading, reporting, and monitoring are currently working in local development

## Remaining Work

- Final production validation of the Cloudflare Queue consumer path
- Production Worker deployment config against the real Cloudflare account/resources
- Production hosting targets for backend and frontend
- Live Cloudflare route/domain cutover for real entry traffic
- Production secrets rotation process and deployment runbook
- Broader monitoring dashboards/alert rules in external observability tooling on top of `/metrics` and webhook alerts
