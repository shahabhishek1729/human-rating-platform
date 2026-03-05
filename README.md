# Human Rating Platform

A web platform for collecting human ratings on LLM responses, designed for Prolific studies.

## How It Works

An admin creates an experiment, uploads a CSV of questions, and shares a study URL
with Prolific. Prolific participants (raters) open the link, rate questions one at a
time, and are redirected to Prolific's completion page when done. The admin monitors
progress, views analytics, and exports ratings as CSV.

The frontend is a React SPA. The backend is a FastAPI JSON API. They talk over `/api`.
PostgreSQL stores everything. Alembic manages schema migrations.

## Project Layout

```text
backend/              FastAPI app, models, services, migrations, tests
  routers/            API route handlers (admin, raters)
  services/           Business logic (admin/, rater/)
  alembic/            Migration config + versions
  scripts/            migrate.sh, predeploy.sh, seed_dev.py, config_check.py
  config.toml         Default local settings
frontend/             React + TypeScript + Vite SPA
  src/api.ts          API client (route map, request pipeline, error handling)
  src/components/     UI components (AdminView, RaterView, ExperimentDetail, etc.)
scripts/              CI/deploy scripts (deploy.sh, resolve_deploy_target.sh)
.github/workflows/    CI (main.yml) + deploy (deploy.yml)
docker-compose.yml    Local dev stack (db + api + test runner)
sample_questions.csv  Example CSV for testing uploads
```

## Stack

- **Backend:** FastAPI + SQLModel (async), served on `:8000`
- **Frontend:** React + TypeScript + Vite, served on `:5173`
- **DB:** PostgreSQL, managed by Alembic migrations
- **Config:** Pydantic Settings (`backend/config.toml` + `.env` + env vars)
- **Python tooling:** `uv` / `uvx`

---

## Authentication (Clerk + Allowlist)

This project uses Clerk for frontend identity and a backend HTTP‑only cookie for invite‑only admin access.

- Frontend (Clerk): The React app is wrapped with `ClerkProvider` and uses prebuilt components for sign‑in/sign‑up. Configure with a publishable key.
- Backend (allowlist + session): After Clerk sign‑in, the frontend calls `POST /api/admin/auth/login` with `Authorization: Bearer <Clerk JWT (template=admin)>`. The backend verifies the JWT against Clerk JWKS, enforces issuer and audience, extracts the email from claims, checks an env‑based allowlist, and issues a signed HTTP‑only cookie that unlocks `/api/admin/*` routes. Signing out clears the cookie.

### Cookie model

- Name: `HRP_SESSION_COOKIE` (default `hrp_session`)
- Scope: `Path=/`, `HttpOnly`; SameSite depends on env — `Lax` in local dev, `None; Secure` in production (`COOKIE_SECURE=true`).
- Contents: a compact HMAC‑signed token with `{ email, iat, exp }`. No server‑side store is required.
- Validation: The server validates the signature and enforces `exp` on every request (session expires server‑side regardless of browser cookie TTL) and re‑checks the email against `ADMIN_ALLOWLIST`.
- Usage: The frontend sends requests with `credentials: 'include'`, so the browser includes the cookie on `/api` calls.

### Clerk Configuration

- Backend env (nested keys as configured in `config.py`):
  - `CLERK__ISSUER`: your Clerk issuer URL (e.g., `https://<your-tenant>.clerk.accounts.dev`).
  - `CLERK__JWKS_URL`: `https://<your-tenant>.clerk.accounts.dev/.well-known/jwks.json`.
  - `CLERK__AUDIENCE`: audience string set in your Clerk JWT template (e.g., `human-rating-platform-admin-api`).
- Clerk JWT template (Dashboard → JWT Templates):
  - Name: `admin`
  - Claims JSON:
    ```json
    { "email": "{{user.primary_email_address}}" }
    ```
  - Audience: set to match `CLERK__AUDIENCE`.
  - Issuer/JWKS: the values above are auto-derived by Clerk; copy them into backend env.
- Frontend usage:
  - Retrieve token with `useAuth().getToken({ template: 'admin' })` and send `Authorization: Bearer <token>` to `/api/admin/auth/login`.

### Allowlist

- Controlled by env var `ADMIN_ALLOWLIST` (comma‑separated or JSON array of emails).
- If your email isn’t in the allowlist, admin login returns 403 and the UI shows a friendly explanation.
# Admin allowlist + session cookie
ADMIN_ALLOWLIST=alice@example.com,bob@example.com
APP_SECRET_KEY=please-change-me-to-a-long-random-string
HRP_SESSION_COOKIE=hrp_session
HRP_SESSION_MAX_AGE=604800
COOKIE_SECURE=false

# CORS for local dev
APP__CORS_ORIGINS=["http://localhost:5173","http://localhost:8000"]

# Database
DATABASE__URL=postgresql://postgres:postgres@localhost:5432/human_rating_platform
```

### Render deployment envs

Frontend (Render Static Site):

- `VITE_CLERK_PUBLISHABLE_KEY=YOUR_PUBLISHABLE_KEY`
- `VITE_API_HOST=https://<your-api-service>.onrender.com`  (origin only; no path)

Backend (Render Web Service):

- `DATABASE__URL=postgresql://<user>:<pass>@<host>:5432/<db>` (Render Postgres internal URL)
- `APP__CORS_ORIGINS=["https://<your-web-service>.onrender.com"]`
- `ADMIN_ALLOWLIST=alice@example.com,bob@example.com`
- `APP_SECRET_KEY=<long-random-string>`
- `COOKIE_SECURE=true`

Clerk Dashboard: add your Render web domain under Settings → Domains so Clerk is allowed to operate on that origin. 

## Quick Start (~3 minutes)

### Prerequisites

- Python 3.10+
- Node.js 20+
- Docker + Docker Compose (must be running)
- Clerk Publishable Key (from Clerk Dashboard → API Keys)

### 1) Initialize env files

```bash
make env.sync
```

Creates `backend/.env` and `frontend/.env` from templates. Then set:

- `frontend/.env.local`
  
  ```
  VITE_CLERK_PUBLISHABLE_KEY=YOUR_PUBLISHABLE_KEY
  ```

- `backend/.env`
  
  ```
  ADMIN_ALLOWLIST=you@example.com
  APP_SECRET_KEY=please-change-me-to-a-long-random-string
  APP__CORS_ORIGINS=["http://localhost:5173","http://localhost:8000"]
  # DATABASE__URL=postgresql://postgres:postgres@localhost:5432/human_rating_platform
  ```

### 2) Start backend + DB (Terminal A)

```bash
make up
```

This starts Postgres, runs migrations, and launches the API with hot reload.

### 3) Start frontend (Terminal B)

```bash
cd frontend
make up
```

### 4) Open the app

- **App:** http://localhost:5173
- **API docs (Swagger):** http://localhost:8000/docs
- **Health check:** http://localhost:8000/api/health

Sign in with a Clerk account whose email appears in `ADMIN_ALLOWLIST`. The admin panel at `/admin` becomes available and the backend issues an HTTP‑only session cookie that authorizes `/api/admin/*` endpoints. Signing out clears this cookie.

---

## Daily Commands

```bash
make up          # start db + migrations + api (hot reload)
make ps          # show service status
make logs        # follow db/api logs
make test        # characterization tests (real db + migrations)
make fmt         # format backend with ruff
make down        # stop stack
```

DB lifecycle:

```bash
make db.up       # apply migrations
make db.down     # rollback one revision (or set MIGRATION_REVISION=...)
make db.new MIGRATION_NAME=add_new_column
make db.reset    # destructive: wipe + rebuild from migrations
make db.clear    # destructive: wipe local postgres volume
make db.seed     # seed local data (disabled by default, see config.toml [seeding])
```

---

## Migrations

SQLModels in `backend/models.py` are the **declarative source of truth** — they describe what the database schema should look like. Migrations are **incremental operations** that get the database from its current state to match the models.

This is the required workflow for schema changes:

### 1) Change models

Edit SQLModel definitions in `backend/models.py`. For new tables, add a new `SQLModel` class with `table=True`. For existing tables, modify the field definitions. Update related schemas and services as needed.

### 2) Generate migration

```bash
make db.new MIGRATION_NAME=describe_change
```

Creates a timestamped file in `backend/alembic/versions/`.

### 3) Review the migration file

Always review the generated SQL/ops before applying. Autogenerate is helpful but not infallible.

### 4) Apply + test

```bash
make db.up
make test
```

### Roll back / inspect

```bash
make db.down                          # rollback one revision
cd backend
sh scripts/migrate.sh current         # show current revision
sh scripts/migrate.sh history         # show full history
```

### If your local DB is stale or broken

```bash
make db.reset
```

> Migration history is squashed for v0. If you were on an older local schema, do `make db.reset` once.

---

## Configuration

Backend settings are loaded via `backend/config.py` (`get_settings()`), with this precedence:

1. Python init kwargs
2. Process env vars
3. `backend/.env`
4. `backend/config.toml`
5. Python defaults

Env keys use Pydantic's nested `__` delimiter for nested settings models:

- `APP__CORS_ORIGINS` — JSON array, e.g. `["http://localhost:5173","http://localhost:8000"]`
- `DATABASE__URL` — Postgres connection string
- `EXPORTS__STREAM_BATCH_SIZE` — CSV export chunking (memory/throughput tradeoff)
- `TESTING__EXPORT_SEED_ROW_COUNT` — characterization test dataset volume
- `SEEDING__*` — local seed generation (`enabled`, `experiment_name`, `question_count`, etc.)

Top‑level convenience envs (not nested):

- `ADMIN_ALLOWLIST` — comma‑separated or JSON array of admin emails
- `APP_SECRET_KEY` — HMAC signer for the HTTP‑only admin session cookie
- `HRP_SESSION_COOKIE`, `HRP_SESSION_MAX_AGE`, `COOKIE_SECURE` — cookie name/ttl/secure flag
 - `ADMIN_AUTH_ENABLED` — set to `false` to bypass admin auth in dev/tests

Frontend env (`frontend/.env`):

- `VITE_API_HOST` — optional API origin for cross-origin deployments
  - **Local dev (default):** empty → frontend uses same-origin `/api` via Vite proxy
  - **Render example:** `https://human-rating-platform-api-uxnt.onrender.com`

---

## Tailscale (optional)

[Tailscale Funnel](https://tailscale.com/kb/1223/funnel) gives your local machine a
public `https://<machine>.<tailnet>.ts.net` URL. Use it to test a live Prolific study
against your local stack — see real rater traffic in your terminal, iterate without
deploying to Render.

### Prerequisites

- [Tailscale](https://tailscale.com/download) installed and authenticated
- Funnel enabled for your tailnet ([setup guide](https://tailscale.com/kb/1223/funnel))

### Usage

```bash
make tailscale.up       # expose / → frontend, /api → backend
make tailscale.status   # show current Funnel URLs
make tailscale.down     # tear down
```

After `make tailscale.up`, use the `*.ts.net` URL as your study URL in Prolific.
Your local `make up` + `cd frontend && make up` stack serves traffic as-is — no
config changes needed.

---

## Render Deployment

Deploys are GitHub-driven and API-triggered (Render auto-deploy is off):

- `human-rating-platform-web` — static frontend
- `human-rating-platform-api` — FastAPI backend
- `human-rating-platform-db` — Postgres

### Backend runtime on Render

- **Build:** `uv sync --frozen --no-dev --no-install-project`
- **Predeploy:** `sh scripts/predeploy.sh`
- **Start:** `uv run --no-sync uvicorn main:app --host 0.0.0.0 --port $PORT`

### Required GitHub Actions secrets

Set in repo → **Settings** → **Secrets and variables** → **Actions**:

| Secret | Where to find it |
| --- | --- |
| `RENDER_API_KEY` | Render Dashboard → Account Settings → API Keys |
| `RENDER_API_SERVICE_ID` | Render Dashboard → API service → Settings → ID (`srv-...`) |
| `RENDER_WEB_SERVICE_ID` | Render Dashboard → Web service → Settings → ID (`srv-...`) |

### Required Render service env vars

**API service** (set in Render Dashboard → API service → Environment):
- `DATABASE__URL` — Render Postgres internal connection string
- `APP__CORS_ORIGINS` — JSON array including web origin, e.g. `["https://human-rating-platform-web.onrender.com"]`

**Web service** (set in Render Dashboard → Web service → Environment):
- `VITE_API_HOST` — public API origin, e.g. `https://human-rating-platform-api-uxnt.onrender.com`

### Deploy flow

1. CI workflow (`✅ CI Checks`) runs lint + characterization tests.
2. Deploy workflow (`🚀 Deploy Render`) gates on CI success for the same SHA.
3. Target resolution (`api`, `web`, `both`, `none`) is handled by `scripts/resolve_deploy_target.sh`.
4. Deploy execution and polling is handled by `scripts/deploy.sh`.
5. Deploys are commit-pinned — Render builds the exact SHA that passed CI.

### Quick verification

1. Trigger deploy (push to deploy branch, or manual dispatch).
2. Check workflow summary for expected target.
3. Verify web app network requests hit `.../api/...`.
4. Hit health check: `https://<api-host>/api/health`.

---

## CI Checks (local)

Run these locally to match what CI enforces:

```bash
uvx ruff==0.15.2 check backend
uvx ruff==0.15.2 format --check backend
npm --prefix frontend run lint
npm --prefix frontend run typecheck
uvx yamllint==1.38.0 .
```

---

## CSV Format

Upload questions as CSV. See `sample_questions.csv` for a working example.

| Column | Required | Description |
| --- | --- | --- |
| `question_id` | Yes | Unique identifier |
| `question_text` | Yes | Prompt shown to raters |
| `gt_answer` | No | Ground-truth answer |
| `options` | No | Comma-separated options for MC |
| `question_type` | No | `MC` or `FT` (default `MC`) |
| `metadata` | No | JSON string |

```csv
question_id,question_text,gt_answer,options,question_type
q1,"Is the sky blue?","Yes","Yes,No,Maybe",MC
q2,"Explain photosynthesis","Plants convert sunlight...",,FT
```

---

## Prolific Integration

1. **Create an experiment** in the admin UI (`/admin`).
2. **Upload questions** via CSV.
3. **Copy the study URL** from the experiment detail page in the admin UI.
4. **Paste it into Prolific** as the external study URL (Prolific Dashboard → Study → Study Link).
5. **Set the completion URL** in the experiment's settings in the admin UI — this is where raters are redirected after finishing.

Study URL format (Prolific fills in the `{{...}}` placeholders):

```text
https://your-app.com/rate?experiment_id=1&PROLIFIC_PID={{%PROLIFIC_PID%}}&STUDY_ID={{%STUDY_ID%}}&SESSION_ID={{%SESSION_ID%}}
```

---

## API Endpoints

Interactive Swagger docs are available at `/docs` when the backend is running.

### Admin

- `POST /api/admin/auth/login` — issue HTTP‑only admin cookie for allowlisted email
- `POST /api/admin/auth/logout` — clear admin cookie
- `POST /api/admin/experiments` — create experiment
- `GET /api/admin/experiments` — list experiments
- `POST /api/admin/experiments/{id}/upload` — upload question CSV
- `GET /api/admin/experiments/{id}/stats` — experiment statistics
- `GET /api/admin/experiments/{id}/analytics` — rating analytics
- `GET /api/admin/experiments/{id}/export` — export ratings as CSV
- `DELETE /api/admin/experiments/{id}` — delete experiment

### Rater

- `POST /api/raters/start` — start rating session
- `GET /api/raters/next-question` — get next question
- `POST /api/raters/submit` — submit a rating
- `GET /api/raters/session-status` — check session status
- `POST /api/raters/end-session` — end session

---

## Supported Targets

- **Local runtime:** Docker Compose
- **Hosted deployment:** Render, via GitHub Actions + Render API (`scripts/deploy.sh`)

## License

MIT
