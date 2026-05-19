# Traffic Splitting

Internal VWO replacement for URL-based traffic splitting.

## What is implemented

- FastAPI backend for experiment CRUD, pause/resume, impression ingest, and reporting
- PostgreSQL schema + Alembic migration for experiments, variants, and impressions
- Redis-backed caching layer for reporting endpoints when `REDIS_URL` is configured
- Cloudflare KV sync hooks from the backend on experiment create/update/delete
- React admin dashboard for managing experiments and viewing launch metrics
- Cloudflare Worker for edge routing, segmentation, sticky assignment, UTM passthrough, and queue forwarding

## Project structure

- [Backend](./Backend)
- [Frontend](./Frontend)
- [Worker](./Worker)

## Local setup

### 1. Backend

```bash
cd Backend
python3 -m venv .venv
source .venv/bin/activate
pip install -e .
alembic upgrade head
uvicorn app.main:app --reload
```

Use [Backend/.env](/Users/apnitormacmini3/Desktop/Traffic%20Splitting/Backend/.env) for backend configuration.

The backend defaults to:

- `DATABASE_URL=postgresql://apnitormacmini3@localhost:5432/traffic_splitting`
- `ADMIN_API_KEY=dev-admin-key`
- `INGEST_API_KEY=dev-ingest-key`

### 2. Frontend

```bash
cd Frontend
npm install
npm run dev
```

### 3. Worker

```bash
cd Worker
cp .dev.vars.example .dev.vars
npm install
npm run dev
```

Before deploying the worker, replace the placeholder KV namespace IDs and queue names in [Worker/wrangler.toml](/Users/apnitormacmini3/Desktop/Traffic Splitting/Worker/wrangler.toml:1).

## Verified locally

- Backend imports and starts successfully
- Alembic migration applies against local Postgres
- Frontend passes `eslint` and production build
- Worker passes TypeScript check
- API smoke-tested for create/list/ingest/stats against local Postgres

## Notes

- Cloudflare sync is no-op until `CLOUDFLARE_ACCOUNT_ID`, `CLOUDFLARE_KV_NAMESPACE_ID`, and `CLOUDFLARE_API_TOKEN` are set in the backend environment.
- Redis is optional for local development. If `REDIS_URL` is unset, reporting still works without cache.
- The monthly partitioning strategy from the PDF is not implemented yet. The schema is a single `impressions` table for now.
# Lgg_Traffic_Splitting
