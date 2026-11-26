# SAHAAYA

**Smart Disaster Resource Allocation and Coordination Platform**

*Intelligent Prioritization. Optimized Resources. Coordinated Response.*

Sahaaya is a software-only decision-support prototype. It organizes fictional incident data, demonstrates priority and demand services, and proposes resource allocations for human review. It does not connect to live emergencies and never automatically dispatches resources.

## Current prototype

Sahaaya is the official project name. Its full title is **Smart Disaster Resource Allocation and Coordination Platform** and its tagline is **Intelligent Prioritization. Optimized Resources. Coordinated Response.**

- Dark, responsive React command center with a landing page, role-aware sign-in, persistent navigation, fictional Leaflet map, and demo dashboard.
- FastAPI + SQLAlchemy backend with role-based authentication and SQLite local storage; PostgreSQL is supported through `DATABASE_URL`.
- CRUD for affected areas, resources, resource centers, and emergency requests; CSV area import and CSV report exports.
- Synthetic Random Forest priority demo model with feature signals and a held-out synthetic-label metric. It is not trained or validated on historical disaster outcomes.
- Transparent demand estimation heuristics that report demand separately from available supply and unmet demand.
- Inspectable custom Genetic Algorithm with per-resource supply constraints, elitism, selection, crossover, mutation, response-cost weighting, fitness history, and configurable parameters.
- Optimization results are saved as pending review. Officers can approve, modify, or reject per-area recommendations; rejection requires a reason. Approval records manual deployment allocations. No automatic dispatch or live GPS tracking exists.
- Officers can submit operator-authored alerts across geological, hydrological, meteorological, climatological, biological, technological, and other hazards. The app records in-app notifications for all department inboxes and creates category-based response tasks. These are coordination records only: the app does not contact departments, send SMS/push messages, verify reports, or dispatch responders.
- Analytics, what-if simulations, alert acknowledgement, audit history, settings, and CSV exports are backed by API data.

All bundled scenario data and coordinates are fictional. Use the prototype only for software evaluation and demonstration.

## Brand identity

The official visual identity uses the supplied Sahaaya shield-and-rescue logo. The reusable React component is `src/components/FlowShieldLogo.tsx`. Optimized transparent WebP versions for the full logo and emblem, plus a PNG browser icon, are in `public/assets/` as `sahaaya-logo.webp`, `sahaaya-emblem.webp`, and `sahaaya-app-icon.png`. High-resolution PNG logo and emblem files are available alongside them.

## Architecture

```text
src/                         React + TypeScript frontend
  components/ui/             Shared UI primitives
  data/                      Centralized fictional demo data and demo identity
  pages/                     Operational pages and workflows
  services/api.ts            Authenticated API client and session storage
backend/app/                 FastAPI application and SQLAlchemy models
  services/                  Synthetic priority model, demand heuristic, custom GA
  migrations/                Alembic migration environment and initial schema
```

The frontend and backend are intentionally separate. In local development the browser uses `/api`, which Vite proxies to `http://127.0.0.1:8000` to avoid local CORS issues. Set `VITE_API_BASE_URL` when the frontend and backend are hosted on different origins. The backend reads configuration from environment variables or `backend/.env`.

## Requirements

- Node.js 20.19+ or 22.12+, and npm
- Python 3.11+ (tested with Python 3.14)
- PostgreSQL only if you do not want local SQLite

## Frontend

From the project root:

```bash
npm install
npm run dev:all
```

`npm run dev:all` starts the FastAPI backend and Vite frontend together. Open `http://localhost:5173` (Vite uses `5174` if `5173` is already occupied). The frontend's `/api` requests are proxied to the backend at `http://127.0.0.1:8000`. Press `Ctrl+C` once to stop both services. For a production bundle:

```bash
npm run build
npm run preview
```

Set `VITE_API_BASE_URL` in a root `.env` file to override the API base path or URL. Leave it unset for local Vite development, which uses the `/api` proxy.

## Backend and database

If you use `npm run dev:all`, it automatically selects the project `.venv` Python when available (otherwise it uses `python` on Windows or `python3` on macOS/Linux). Create the environment and install the dependencies first:

```bash
python -m venv .venv
# Windows PowerShell
.venv\Scripts\Activate.ps1
pip install -r backend/requirements.txt
Copy-Item backend/.env.example backend/.env
```

Review `backend/.env` and set unique credentials and a long random `JWT_SECRET`. The example values are for local demonstration only. Start the API from the project root:

```bash
python -m uvicorn backend.app.main:app --reload
```

The default local database is `sqlite:///./resqai.db` in the project root. The filename is retained to preserve existing local demo data; the application identity is Sahaaya. SQLite tables and fictional seed data are created at startup. To use PostgreSQL, set for example:

```text
DATABASE_URL=postgresql+psycopg://sahaaya:your-password@localhost:5432/sahaaya
```

Configure the matching database/user first. Add the database URL to `backend/.env`.

Alembic migration commands (run from the project root):

```bash
python -m alembic -c backend/alembic.ini upgrade head
python -m alembic -c backend/alembic.ini revision --autogenerate -m "describe schema change"
```

The app also calls SQLAlchemy `create_all` at startup for an easy local demo bootstrap. Production schema changes should be managed and reviewed through Alembic migrations.

## Demo deployment (Vercel + Render)

The repository includes `vercel.json` for the Vite frontend and `render.yaml` for the FastAPI API plus PostgreSQL. Vercel proxies `/api/*` to `https://sahaaya-api.onrender.com`, so the frontend can keep using the same `/api` base path as local development.

1. Import the GitHub repository into Vercel from [vercel.com/new](https://vercel.com/new). Keep the repository root as the project root; `vercel.json` sets the build command, output directory, API proxy, and React Router fallback.
2. In Render, create a Blueprint from this repository and the `main` branch. During setup, enter the exact Vercel site origin for `CORS_ORIGINS` and set unique values for `DEMO_USER_PASSWORD`, `DEMO_ADMIN_PASSWORD`, and `DEMO_VIEWER_PASSWORD`. Render generates `JWT_SECRET` and connects the API to the Blueprint's Postgres database.
3. After both services deploy, open `https://<your-vercel-domain>/api/health`. It should report the API and database as connected. Sign in as `sumith@sahaaya.demo` using the `DEMO_USER_PASSWORD` you set in Render.

This is a free demo configuration. Render's free API can spin down after 15 minutes of inactivity, causing a slow first request, and its free Postgres database expires after 30 days. Do not use this tier for persistent or real emergency operations. See [Render free-tier limits](https://render.com/docs/free), [Vercel rewrites](https://vercel.com/docs/routing/rewrites), and [Render FastAPI deployment](https://render.com/docs/deploy-fastapi).

## Demo credentials

Default local-only accounts (override passwords in `backend/.env` before first startup):

| Role | Email | Password |
|---|---|---|
| Emergency Officer | `sumith@sahaaya.demo` | `demo-preview` |
| Administrator | `admin@sahaaya.demo` | `demo-admin-preview` |
| Viewer | `viewer@sahaaya.demo` | `demo-viewer-preview` |

The frontend login form is prefilled with the emergency officer demo account. On startup, the backend updates known legacy ResQAI demo email addresses to their Sahaaya addresses in the existing database, preserving account IDs and password hashes. Viewer access is read-only. Only an Administrator can persist GA and priority-threshold settings. Passwords are stored as salted PBKDF2 hashes; tokens use a signed HMAC format. Use a deployment-grade authentication provider and secret rotation before production use.

## ML priority demonstration

`backend/app/services/priority.py` fits a deterministic Random Forest to generated examples whose classes are derived from synthetic rules. The API returns class, score, probabilities, feature importance, local feature signals, and a held-out metric against those generated labels. This metric demonstrates the pipeline only; it is not evidence of real-world predictive performance. Production use requires authorized historical incident data, carefully defined labels, geographic/time-aware evaluation, bias review, and expert validation.

## Demand estimation

`backend/app/services/demand.py` contains isolated, readable formulas for ambulance, rescue, medical, food, water, shelter, and transport demand. They are prototype heuristics, not forecasts. Responses label estimated demand, available resources, and unmet demand separately. Replace the module with a validated model only after it has suitable data and field review.

## Genetic Algorithm

`backend/app/services/optimizer.py` has the full custom GA: bounded integer allocation chromosomes, repair against each resource supply, seeded population initialization, weighted tournament-like top-half selection, single-point crossover, mutation, elitism, a generation loop, and best-solution extraction. Fitness rewards demand satisfaction and serving higher-priority areas while penalizing critical unmet need, response distance, and unused supply. Resource types are optimized separately, each under its own available-supply limit. Parameters: population size, generations, mutation rate, crossover rate, and reproducibility seed.

The response includes before/after allocation metrics calculated from the run, per-area demand/allocation/unmet quantities, utilization, estimated travel cost, and convergence history. Every run is saved with `pending_review`; an authority must review recommendations. Modified quantities are validated against demand and supply. Decisions create manual deployment records only.

## API reference

Interactive OpenAPI documentation is available at `http://127.0.0.1:8000/docs` when the backend is running.

Key endpoints (authenticated endpoints require `Authorization: Bearer <token>`):

| Method | Endpoint | Purpose |
|---|---|---|
| POST | `/api/auth/login` | Sign in and receive a token |
| GET/POST/PUT/DELETE | `/api/areas` | List and manage affected areas |
| POST | `/api/areas/import` | Validate and import areas from CSV |
| GET/POST/PUT | `/api/resources` | List and maintain resource inventory |
| GET/POST | `/api/resource-centers` | List/create resource centers |
| GET/POST/PATCH | `/api/requests` | Track emergency requests and statuses |
| POST | `/api/ml/priority` | Synthetic demo model prediction |
| POST | `/api/areas/recalculate-priorities` | Recalculate all demo priority records |
| POST | `/api/resources/estimate-demand` | Estimate per-area demand and unmet need |
| POST | `/api/optimization/run` | Run the custom Genetic Algorithm |
| GET | `/api/optimization/{id}` | Retrieve a persisted run and decisions |
| POST | `/api/optimization/{id}/approve` | Approve an area recommendation |
| POST | `/api/optimization/{id}/modify` | Save an officer-modified allocation |
| POST | `/api/optimization/{id}/reject?area_id=...` | Reject with a required reason |
| GET/PATCH | `/api/deployments` | Review/update manual deployment records |
| GET/PATCH | `/api/alerts` | List and acknowledge alerts |
| GET/POST | `/api/disaster-alerts` | Review or create operator-reported disaster alerts and in-app department notifications/tasks |
| PATCH | `/api/disaster-alerts/tasks/{task_id}` | Update a department response task status |
| GET | `/api/analytics/overview` | Aggregated demo metrics and charts |
| POST | `/api/simulation/run` | Compare baseline and simulated scenario |
| GET | `/api/history` | Audit timeline |
| GET | `/api/reports/{type}.csv` | Export areas, requests, resources, runs, decisions, or audit history |

## Known limitations

- Provider connectors and storage are implemented, but external services do not become connected until required authorization/configuration is supplied and a successful ingestion is recorded. No real disaster feed was imported during this implementation.
- The model uses synthetic labels. The demand rules and travel-distance cost are approximations and have not been field validated.
- The GA enforces resource stock constraints per resource center and estimates response cost using straight-line distance from a center to an area. It does not yet optimize road-network travel time or multi-stop routing.
- Demo map coordinates are illustrative and use OpenStreetMap tiles when the browser has internet access; the map is not live tracking.
- JWT/HMAC auth is a prototype. There is no password reset, account management UI, refresh-token flow, rate limiting, or production security review.
- SQLite is suitable for local development only. PostgreSQL is supported through SQLAlchemy but needs a provisioned database and deployment configuration.
- The historical import supports CSV/JSON with explicit mapping, provenance and validation; it does not perform automatic unit conversions or silently harmonize geographic resolution.
- PostGIS boundaries, external population exposure datasets, verified impact labels, and production ML evaluation remain future work.

## Real-data integration

The integration layer is under `backend/app/integrations/`. It stores source records and content hashes in `raw_source_records`, normalizes supported observations/incidents into separate tables, and records every attempt in `ingestion_logs`. API-triggered ingestion is available to Emergency Officers and Administrators. A per-source database lease prevents concurrent manual/scheduled fetches. Set `SAHAAYA_INGESTION_ENABLED=true` to start the opt-in scheduler; `SAHAAYA_INGESTION_INTERVAL_SECONDS` controls its interval (minimum 60 seconds). Keep scheduling disabled until source terms and polling cadence are reviewed.

Configure sources in the authenticated **Data Sources** page when an Administrator account is used. The NWIC and CWC forms accept HTTPS URLs on the reviewed provider hosts only. The NWIC resource also needs an explicit JSON column mapping before rainfall rows are normalized. Unmapped rows remain stored as raw records. IMD credentials/endpoints and the subscribed SACHET feed URL are server-side environment variables only. The app never asks for or sends these secrets to the browser.

| Provider | Connector behavior | Configuration state / limitation |
|---|---|---|
| USGS | Parses the official all-day GeoJSON earthquake feed, including event ID, magnitude/depth in the raw record, coordinates, event/update timestamps and source URL. | Public feed URL is configured; no successful external connection is implied until source health shows a successful fetch. Historical FDSN querying is not yet exposed as a scheduled connector. |
| GDACS | Fetches recent earthquake, flood and tropical cyclone event list; stores provider IDs, geometries and links. | Public endpoint configured; attribution and source terms apply. |
| NWIC / Telangana SW | Fetches a configured CSV resource; exact mappings create rainfall observations with station and optional state/district hierarchy. Future timestamps are rejected. | Public dataset URL can be configured, but schema mapping must match the selected resource. The portal offers separate 2021–2025 and 2026–2030 CSV resources; future-dated rows in the latter are not accepted as observations. |
| NDMA SACHET | Parses subscribed CAP XML, including issuer, event, severity, urgency, certainty, effective/expiry, description, instructions and affected area. Uses ETag/304 support and rejects XML entity declarations. | Not configured until the account-specific feed identifier/URL from SACHET subscription is supplied. |
| IMD | Configurable documented endpoint set and field normalization for current weather fields, with raw provider payload retained. | Not configured until authorized endpoints and the exact account-issued auth headers are supplied. The application does not guess credentials or auth format. |
| CWC | Configurable HTTPS source fetch and raw CSV/JSON preservation. | No public API path is assumed. Configure only a verified authorized feed; normalized forecast schema mapping is not implemented. |

The NWIC source’s public resource page documents hourly Telangana SW rainfall telemetry and both historical and forward resource ranges: [National Water Data Portal dataset](https://nwdp.nwic.gov.in/dataset/rainfall-telemetry-hourly-telangana-sw). A future range is a dataset label, not proof that every row is an observation; Sahaaya validates each record timestamp before storing it as measured rainfall.

### Historical dataset import

1. Sign in and open **Historical Data**.
2. Choose a UTF-8 CSV or JSON file (maximum 12 MB).
3. Enter exact source columns for timestamp, numeric value, variable, and unit. Add the source record ID, hazard, station/location, coordinates, and state/district names or codes when available.
4. Add dataset/resource ID, publisher, license/terms and coverage dates.
5. Preview validation errors and valid rows before importing. Future timestamps and invalid coordinates are rejected; values with unspecified/ambiguous units should not be imported as a normalized measurement.
6. Re-importing identical rows is deduplicated. Changed source rows are retained as raw revisions and update the normalized observation for that time and variable.

Historical observations are stored separately from current observations and incidents. API queries support paging, time range, state and district filters. Example v1 endpoints include `GET /api/v1/historical/rainfall`, `GET /api/v1/historical/disasters`, `GET /api/v1/observations/rainfall`, and `GET /api/v1/map/layers`. Review exact query parameters in `/docs`.

### Integration API and source health

Authenticated v1 endpoints include:

- `GET /api/v1/sources` and `GET /api/v1/sources/status`
- `GET /api/v1/ingestion/logs?page=1&page_size=25`
- `POST /api/v1/sources/{source_key}/ingest`
- `GET /api/v1/alerts`, `GET /api/v1/incidents`
- `GET /api/v1/observations/weather`, `/rainfall`, and `/rivers`
- `GET /api/v1/dashboard/summary`, `/analytics/hazards`, and `/map/layers`
- `POST /api/v1/historical/import/preview` and `POST /api/v1/historical/import` (multipart form)
- `POST /api/v1/alerts/{id}/review`
- `POST /api/v1/optimization/run` and `POST /api/v1/optimization/{id}/approve`

Source freshness is based on each provider's last successful fetch and freshness threshold. The frontend's own refresh does not mark a provider live. Failed integrated map queries show an error or an empty state; synthetic preview locations require selecting **Demo preview** explicitly.

### Test commands

Run the backend unit and migration tests from the project root:

```bash
python -m unittest discover -s backend/tests -v
```

The tests use mocked provider payloads, temporary SQLite databases, and a legacy-row migration check. They do not make calls to external providers. Run the frontend type check and production build with:

```bash
npm run build
```
