# Traffic Splitting

Internal VWO replacement for URL-based traffic splitting.

## What Is Implemented

- FastAPI backend for experiment CRUD, pause/resume, impression ingest, and reporting
- PostgreSQL schema + Alembic migration for `experiments`, `variants`, and `impressions`
- Redis-backed caching layer for reporting endpoints
- React admin dashboard for experiment management and reporting
- Cloudflare Worker for slug-based routing, weighted variant selection, sticky assignment, UTM passthrough, and Hyros `test_tag`
- Cloudflare KV sync from backend to edge config

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
- The `impressions` table is currently a single table; monthly partitioning is still pending
