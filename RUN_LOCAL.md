# Local development — PostgreSQL + PostGIS (v3 migration)

Everything below is **local only**. It never touches Firestore writes or production.

## Prerequisites
- Docker Desktop running.
- Python: use the **conda** interpreter (`python` → `C:\Users\juanp\anaconda3\python.exe`).
  The `back/.venv` is broken (built against a Python that no longer exists) — do not use it.
  The DB stack (sqlalchemy, asyncpg, geoalchemy2, alembic, pydantic-settings) is already
  installed in conda.

## One-shot setup
From `back/`:

```powershell
# 1. Start PostGIS (host port 5433 — 5432 is taken by a native PG service)
docker compose -f docker-compose.dev.yml up -d

# 2. Point the tools at the local DB
$env:DATABASE_URL = "postgresql+asyncpg://calitrack:calitrack@localhost:5433/calitrack_dev"

# 3. Apply the schema
python -m alembic upgrade head

# 4. Run the tests
python -m pytest -m "unit or integration" --no-cov
```

Or run the helper that does all four: `powershell scripts/dev/setup_db_local.ps1`.

## What you can test today (Wave 0 complete)
- **Schema**: 13 tables, `v_intervenciones` view, `calcular_estado` SQL function, GIST indexes,
  generated geometry-validity columns. Migration `0001_wave1` is reversible
  (`alembic downgrade base` then `alembic upgrade head`).
- **Domain rules**: `domain/geospatial/estado.py` — pure `calcular_estado` / `clasificar_frente_activo`,
  verified for three-way parity with the legacy implementation.
- **ETL geometry transform**: `etl/transform_geo.py` — parses the messy Firestore GeoJSON encodings
  (dict / JSON string / double-encoded / coords-as-string) and flags `[0,0]` placeholders.
- **Tests**:
  - `pytest -m unit` — pure, no DB (estado parity, geometry transform).
  - `pytest -m integration` — against the live PostGIS: schema presence, SQL↔Python estado parity,
    geometry round-trip with validity flags. Skips automatically if the DB is down.

## Useful commands
```powershell
# psql into the container
docker exec -it calitrack_pg_dev psql -U calitrack -d calitrack_dev

# stop / reset the DB (‑v wipes the volume)
docker compose -f docker-compose.dev.yml down
docker compose -f docker-compose.dev.yml down -v   # full reset
```

## Connection (local)
`postgresql+asyncpg://calitrack:calitrack@localhost:5433/calitrack_dev`

Production will use Neon with `?sslmode=require` via the `DATABASE_URL` env var (never committed).

## Live migration (Firestore -> local Postgres) — WORKS
Firebase credentials are configured locally (service account), so the real ETL runs:

```powershell
$env:DATABASE_URL = "postgresql+asyncpg://calitrack:calitrack@localhost:5433/calitrack_dev"
python -m etl.run_wave1            # full load + parity report
python -m etl.run_wave1 --dry-run  # extract + transform only (no DB writes)
python -m etl.run_wave1 --limit 50 # small slice
```
Read-only on Firestore; writes only to the local Postgres. Last run loaded
**2376 unidades, 2534 intervenciones, 429/432 avances** (3 orphan avances skipped
+ reported); unidades parity OK (0 changed). The load is resilient (per-row
SAVEPOINT) so bad rows are reported, not fatal.

### Repository adapter (Wave 1)
`infrastructure/postgres/{unidades_proyecto_repo,intervenciones_repo,mappers}.py`
implement the ports in `domain/geospatial/ports.py`. Covered by:
- `test/integration/test_postgres_repo.py` (adapter vs live PostGIS),
- `test/contract/` — the SAME assertions run against the in-memory fake AND the
  Postgres adapter, proving behavioural parity.

## Isolated API over Postgres (test the migration end-to-end)
`pg_app.py` is a minimal FastAPI app that serves the migrated data from Postgres
with **no Firebase and no auth** — it cannot touch production. The Next.js front
can point at it to render the map from PostGIS.

```powershell
# from the repo root (CaliTrack/): brings up DB + isolated API (:8000) + front (:3000)
.\start-local-pg.ps1
.\kill-local.ps1        # stop API + front
.\kill-local.ps1 -Db    # also stop the DB container (volume kept)
```
Endpoints: `GET /health`, `GET /unidades-proyecto` (same `{success,data,count}`
envelope as the legacy API), `GET /unidades-proyecto/geojson` (FeatureCollection).
Each UP is enriched with consolidated intervención fields (estado, avance_obra,
tipo_intervencion, frente_activo) so the map can colour by them — consolidation
mirrors the front (presupuesto-weighted avance, "Varios estados", etc.).
Run the API alone: `DATA_BACKEND=postgres uvicorn pg_app:app --port 8000`.

Why a separate app instead of the monolith in "postgres mode": the production
`AuthorizationMiddleware` returns 401 globally and loads the user from Firestore,
so serving the monolith without Firebase would require bypassing production auth
in two places. The isolated app avoids touching auth entirely.

### Login in local mode
The front's login is built around the Firebase client SDK, which the isolated
backend deliberately does not have — so login would 404 ("Error de autenticación
Not Found"). For local testing, `AuthContext` bypasses auth entirely when
`NEXT_PUBLIC_LOCAL_NO_AUTH=true` (set automatically by `start-local-pg.ps1`):
it injects a synthetic super-admin user and skips Firebase. **Off by default —
production auth is untouched.** You land straight on the dashboard, no login.

Scope: only the **project units** tab/map is served from Postgres. Other tabs
(projects, contracts, empréstito, …) call endpoints `pg_app` doesn't have yet,
so they stay empty in this isolated mode.

> Data note: the live load reported 2376 unidades but the table holds **2365** —
> the upsert collapsed **11 duplicate upids** that existed in Firestore (which did
> not enforce upid uniqueness). The relational PK fixes that.

## Not yet wired (next)
- `ports_di.py` provider + `DATA_BACKEND` dual-read composite (run Firestore and
  Postgres side by side in the API), router re-pointing, the Firestore adapter +
  its contract test, then Waves 2-5 (empréstito, presupuestal, métricas, decom).
- ETL data-quality follow-ups: 3 orphan avances (intervención missing), 8 unidades
  with null geometry.
