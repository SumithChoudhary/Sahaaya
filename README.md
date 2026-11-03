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
- Analytics, what-if simulations, alert acknowledgement, audit history, settings, and CSV exports are backed by API data.

All bundled scenario data and coordinates are fictional. Use the prototype only for software evaluation and demonstration.

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

The frontend and backend are intentionally separate. The browser uses `VITE_API_BASE_URL` (default `http://127.0.0.1:8000/api`). The backend reads configuration from environment variables or `backend/.env`.

## Requirements

- Node.js 20.19+ or 22.12+, and npm
- Python 3.11+ (tested with Python 3.14)
- PostgreSQL only if you do not want local SQLite

## Frontend

From the project root:

```bash
npm install
npm run dev
```

Vite serves the interface at `http://localhost:5173`. For a production bundle:

```bash
npm run build
npm run preview
```

Set `VITE_API_BASE_URL` in a root `.env` file to override the API URL. Keep it pointed at the local backend during demo use.

## Backend and database

Create and activate a virtual environment, then install the dependencies:

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
| GET | `/api/analytics/overview` | Aggregated demo metrics and charts |
| POST | `/api/simulation/run` | Compare baseline and simulated scenario |
| GET | `/api/history` | Audit timeline |
| GET | `/api/reports/{type}.csv` | Export areas, requests, resources, runs, decisions, or audit history |

## Known limitations

- No real incident feeds, disaster victims, dispatch integrations, or device/IoT dependencies are used.
- The model uses synthetic labels. The demand rules and travel-distance cost are approximations and have not been field validated.
- Demo map coordinates are illustrative and use OpenStreetMap tiles when the browser has internet access; the map is not live tracking.
- JWT/HMAC auth is a prototype. There is no password reset, account management UI, refresh-token flow, rate limiting, or production security review.
- SQLite is suitable for local development only. PostgreSQL is supported through SQLAlchemy but needs a provisioned database and deployment configuration.
- PDF/Excel reporting, paging at the API level, automated alert generation, richer center/resource CRUD, and production ML evaluation remain future work.
