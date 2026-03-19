# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Goal

CapReSol is a real estate investment analysis system for Madrid-focused funds. Five core capabilities:
1. **Portal scraping** — automated ingestion from 5 sources (Idealista API, Idealista HTML, Redpiso, Fotocasa, Pisos.com) into PostgreSQL
2. **ML valuation** — Gradient Boosting model predicts market price from property features
3. **Fix & Flip analysis** — user inputs investment parameters, system returns IRR, ROE, Equity Multiple, Gross Margin
4. **Frontend** — Next.js UI to search deals, view ML predictions, and run financial analyses
5. **Multi-user auth** — JWT-based authentication with 6 user accounts

## Important: Git Policy

**Do NOT create git commits or push to the repository.** Only edit/write files. The user will commit and push manually.

## Commands

### Infrastructure (local development)
```bash
cd infra && docker compose up -d    # Start Postgres 16 (required before backend)
cd infra && docker compose down     # Stop Postgres
```

### Backend
```bash
cd backend && uvicorn app.main:app --reload --port 8000
# API docs (Swagger UI): http://localhost:8000/docs
```

### Database Migrations
```bash
cd backend
alembic upgrade head                               # Apply all migrations
alembic revision --autogenerate -m "description"  # Generate migration from model changes
alembic downgrade -1                               # Roll back one step
```

### Frontend
```bash
cd frontend && npm run dev    # http://localhost:3000
```

## Production Deployment

### Architecture
- **Backend**: Railway (Docker) → `https://capresol-production.up.railway.app`
- **Frontend**: Vercel → `https://cap-re-sol.vercel.app`
- **Database**: Railway Postgres (internal: `postgres.railway.internal`, public URL available for external access)

### Backend (Railway)
- Dockerfile at `backend/Dockerfile`: Python 3.11-slim, installs deps, runs alembic migrations + seeds users + starts uvicorn
- `--proxy-headers --forwarded-allow-ips='*'` on uvicorn — required because Railway terminates SSL at the load balancer; without these flags, FastAPI's trailing-slash redirects generate `http://` URLs causing Mixed Content blocks
- `PYTHONPATH=/app` set in Dockerfile for alembic module resolution
- `config.py` auto-converts Railway's `postgresql://` to `postgresql+psycopg2://` for SQLAlchemy
- Users are seeded automatically on every deploy from `USERS_CONFIG` env var (idempotent)

### Frontend (Vercel)
- Root directory: `frontend`
- `NEXT_PUBLIC_API_URL` env var must be set to the Railway HTTPS URL (all environments)
- `lib/api.ts` calls Railway directly (not via Next.js rewrites) — Vercel rewrites to external URLs behave as client-visible redirects causing Mixed Content. CORS on the backend allows the Vercel origin.
- `lib/auth.ts` also calls Railway directly for login
- HTTP→HTTPS forced in code as safety net (`replace(/^http:\/\//, 'https://')`)
- `app/api/auth/login/route.ts` — Route Handler for login proxy (fallback for local dev)
- `app/api/deals/scrape/route.ts` — Route Handler with `maxDuration=300` for scrape proxy (local dev)

### Railway Environment Variables
```
DATABASE_URL          — auto-injected by Railway Postgres
IDEALISTA_API_KEY     — Idealista OAuth2 client ID
IDEALISTA_SECRET      — Idealista OAuth2 client secret
FIRECRAWL_API_KEY     — Firecrawl API key
JWT_SECRET            — random 32-char string for JWT signing
USERS_CONFIG          — JSON array: [{"username":"...","password":"..."},...]
ALLOWED_ORIGINS       — JSON array: ["http://localhost:3000","https://cap-re-sol.vercel.app"]
```

### Key deployment files
- `backend/Dockerfile` — build + startup (alembic → seed_users → uvicorn)
- `backend/.dockerignore` — excludes .env, __pycache__, .git, *.md
- `backend/scripts/seed_users.py` — reads USERS_CONFIG, creates users (skips existing)
- `frontend/vercel.json` — Vercel framework config
- `frontend/next.config.js` — rewrites (used locally), backend URL from env

## Architecture

### Data Flow
```
Idealista API / Idealista HTML (Firecrawl) / Redpiso JSON API / Fotocasa (Firecrawl) / Pisos.com (Firecrawl)
        ↓
  normalize_district() → 21 canonical Madrid districts
        ↓
  extract_postal_code() → regex on address + ZONE_TO_POSTAL fallback
        ↓
  ingest_listings() → filter (require price + size + Madrid district) → upsert
        ↓
   deals table  (message_id = null for portal scrapes)
        ↓
  ML prediction  →  predictions table
        ↓
 Fix & Flip analysis  →  financial_analyses table (persisted)
```

### Backend (`backend/app/`)

**Entry point**: `main.py` — FastAPI app with CORS middleware (`allow_origins` from `ALLOWED_ORIGINS` env var, `allow_credentials=True`), mounts `/auth`, `/messages`, `/deals`, `/analyses`, `/analytics` routers.

**Authentication** (`api/auth.py`):
- `POST /auth/login` — accepts `{username, password}`, returns `{access_token, token_type}`
- `get_current_user` dependency — validates Bearer JWT, returns `User` ORM object
- All routers except `/auth/login` and `GET /` are protected with `Depends(get_current_user)`
- Passwords hashed with `bcrypt` directly (not passlib — incompatible with bcrypt 4.x)
- JWT tokens expire after 7 days (`JWT_EXPIRE_MINUTES = 60 * 24 * 7`)

**Database models** (`db/models.py`):
- `User` — id, username, hashed_password, created_at
- `Message` — raw inbound data; `channel` field: `portal | gmail | whatsapp`
- `Deal` — structured property record. Full field list: address, city, country, property_type, size_sqm, bedrooms, bathrooms, floor, asking_price, currency, url (unique), broker_name, broker_contact, district, zone, condition, orientation, storage_room, terrace, balcony, elevator, garage, listed_date, postal_code
- `Prediction` — ML output: predicted_price, model_version, FK to deal
- `FinancialAnalysis` — all FlipInput fields + computed outputs

**API layer** (`api/`):
- `auth.py` — `POST /auth/login`, `get_current_user` dependency
- `deals.py` — `GET /deals`, `POST /deals/from-message`, `POST /deals/scrape`, `POST /deals/predict` (batch), `DELETE /deals/predictions/{id}`
- `analyses.py` — `GET /analyses`, `POST /analyses`, `PUT /analyses/{id}`, `DELETE /analyses/{id}`
- `analytics.py` — `GET /analytics?max_price_sqm=&min_price_sqm=`
- `messages.py` — message CRUD
- `schemas.py` — all Pydantic models

**Scraping** (`services/portal_scraper.py`):
- `scrape_idealista_api()` — OAuth2 → form-encoded POST. 50 results/page, 100 req/month quota.
- `scrape_idealista_html()` — Firecrawl bypasses DataDome. 30 listings/page, ~15,374 available. No API quota cost.
- `scrape_redpiso_html()` — Redpiso JSON API, no auth, 50/page, 1,284+ listings.
- `scrape_fotocasa_firecrawl()` — Firecrawl + geo-proxy. ~31 listings/page, 9,439 available.
- `scrape_pisos_firecrawl()` — Firecrawl, 30 listings/page, ~10,500 available. Orientation + amenity keyword extraction.
- `normalize_district()` — Maps ~150 barrio names to 21 canonical Madrid districts.
- `extract_postal_code(text, zone)` — Regex `r'\b(28\d{3})\b'` on address/title, falls back to `ZONE_TO_POSTAL[zone]` (131 barrios mapped).
- `ZONE_TO_POSTAL` — dict mapping 131 Madrid barrios to their primary postal codes.
- `ingest_listings(db, listings)` — PostgreSQL upsert via `ON CONFLICT DO UPDATE`. Auto-derives `postal_code`. COALESCE for data-quality fields, OVERWRITE for mutable fields.

**Data quality rules** (enforced in `ingest_listings()`):
- Listings without `asking_price` are dropped
- Listings without `size_sqm` are dropped
- Listings outside Madrid's 21 canonical districts are dropped
- District names are normalised before insert (barrio → district mapping)

**ML pipeline** (`ml/`):
- `features.py` — `deal_to_features(deal)`: Deal ORM → feature dict. Categoricals: `Distrito`, `Zona`, `Estado`, `Ubicacion`.
- `model.py` — `predict_price_from_features(features)`: one-hot encodes, aligns to training columns, scales, runs GB model. Uses `@lru_cache` for artifacts.
- `artifacts/` — `best_gb_model.pkl`, `scaler.pkl`, `model_columns.pkl`
- `train.py` — Queries DB, filters outliers, one-hot encodes, StandardScaler, GradientBoostingRegressor(n_estimators=300, max_depth=5, lr=0.05, subsample=0.8). Run: `python -m app.ml.train` from `backend/`. Last trained 2026-03-13: 2,461 deals, R²=0.791, MAE≈€198k. **Restart backend after retraining** to clear `@lru_cache`.

**Financial model** (`utils/excel.py`): `run_flip_analysis()` — pure-Python Fix & Flip with monthly equity cash flows and leverage. Computes IRR via `numpy_financial.irr`.

**Config** (`config.py`): reads `DATABASE_URL` (auto-converts `postgresql://` → `postgresql+psycopg2://`), `IDEALISTA_API_KEY`, `IDEALISTA_SECRET`, `FIRECRAWL_API_KEY`, `JWT_SECRET`, `JWT_ALGORITHM`, `JWT_EXPIRE_MINUTES`, `ALLOWED_ORIGINS`, `USERS_CONFIG`.

### Idealista API — Critical Notes

- **Token URL**: `POST https://api.idealista.com/oauth/token` (NOT `/oauth/accesstoken`)
- **Auth**: Basic auth with `base64(api_key:secret)`, body: `grant_type=client_credentials&scope=read`
- **Search URL**: `POST https://api.idealista.com/3.5/es/search`
- **Search body**: form-encoded (`data=`, NOT `json=`) — the API rejects JSON
- **Madrid location ID**: `0-EU-ES-28`
- **Quota**: 100 req/month, 1 req/sec — enforce with `time.sleep(1.1)` between calls
- **Pagination**: `numPage` param, up to 50 results/page via `maxItems: 50`
- Token expires in ~12 hours (43,200 seconds)
- **HTML via Firecrawl**: Bypasses DataDome. Use `scrape_idealista_html()` for quota-free scraping.

### Redpiso API — Critical Notes

- **Endpoint**: `GET https://www.redpiso.es/api/properties` — no auth required
- **Params**: `page`, `pageSize` (max 50), `type` ("sale"/"rent"), `statuses[]` (["ongoing","pending_signature"]), `sort` ("recent"), `province_slug` ("madrid"), `property_group_slug` ("viviendas")
- **URL pattern**: `https://www.redpiso.es/inmueble/{slug}`
- **Total available**: ~1,283 Madrid sale listings
- No quota limits observed. Add `time.sleep(1.1 + random(0, 0.5))` between pages.

### District Normalisation

Madrid has 21 official districts. The `normalize_district()` function maps ~150 barrio names and spelling variants to canonical names: Centro, Arganzuela, Retiro, Salamanca, Chamartín, Tetuán, Chamberí, Fuencarral-El Pardo, Moncloa-Aravaca, Latina, Carabanchel, Usera, Puente de Vallecas, Moratalaz, Ciudad Lineal, Hortaleza, Villaverde, Villa de Vallecas, Vicálvaro, San Blas-Canillejas, Barajas.

### Postal Code Mapping

`ZONE_TO_POSTAL` dict maps 131 Madrid barrios to their primary postal codes (28xxx format). Used by `extract_postal_code()` as fallback when regex extraction from listing text fails.

### Infrastructure (`infra/`)
- `docker-compose.yml` — Postgres 16, container `capresol-postgres`, port 5432, DB `capresol`
- Local development only; production uses Railway Postgres

### Frontend (`frontend/`)
Next.js 14 App Router + Tailwind CSS.

**API architecture**: In production (Vercel), `lib/api.ts` calls Railway backend directly using `NEXT_PUBLIC_API_URL`. Locally, falls back to `/api` proxy via `next.config.js` rewrites to `localhost:8000`.

**Authentication**:
- `lib/auth.ts` — `login()`, `logout()`, `getToken()`, `setToken()`, `clearToken()`, `isAuthenticated()`. JWT stored in both localStorage (for API calls) and cookie `capresol_token` (for middleware).
- `middleware.ts` — checks `capresol_token` cookie, redirects unauthenticated requests to `/login`
- `app/login/page.tsx` — username + password form, calls Railway directly, full page reload on success

**Pages**:
- `/` (home) — dashboard with quick stats, recent deals, scrape button, nav cards
- `/deals` — listings table with column filters, pagination, ML predictions inline
- `/valuaciones` — batch ML predictions + per-row delete
- `/analyses` — Fix & Flip history + new analysis modal + edit/delete
- `/analytics` — Recharts dashboards, outlier filter presets, portfolio KPIs
- `/login` — authentication form

**Key files**:
- `lib/api.ts` — typed fetch helpers. `BASE` = `NEXT_PUBLIC_API_URL` (production) or `/api` (local). Forces HTTPS. `apiFetch()` injects auth header, redirects to `/login` on 401.
- `lib/auth.ts` — auth helpers, calls backend directly for login
- `middleware.ts` — auth guard via cookie check
- `components/Sidebar.tsx` — nav with active state + logout button

**Analytics dashboard** (`app/analytics/page.tsx`):
Built with Recharts. Outlier filter presets control data bounds. Charts: Precio €/m² por Distrito, Upside de Reforma, Distribución por Estado, Spread ML vs Precio Pedido, Cartera analizada (KPIs), expandable histograms.

## Current Status

| Component | Status |
|---|---|
| JWT Authentication | ✅ Complete — 6 users, login endpoint, protected routes |
| Production deployment | ✅ Live — Railway backend + Vercel frontend |
| DB schema (all fields + users + postal_code) | ✅ Complete |
| 5-portal scraping pipeline | ✅ Working |
| Postal code auto-extraction | ✅ Working — regex + ZONE_TO_POSTAL fallback (131 barrios) |
| Pisos.com orientation + amenities | ✅ Working — keyword extraction from Firecrawl markdown |
| Idealista API balcony fix | ✅ Working — `hasBalcony` mapped |
| ML prediction (batch) | ✅ Working — R²=0.791, MAE≈€198k |
| Fix & Flip financial model | ✅ Working — LTV/mortgage/capex debt |
| All frontend pages | ✅ Working — deals, valuaciones, analyses, analytics, login |
| Railway DB | ⚠️ Fresh — needs scraping to populate (~300 listings so far, local had ~2,464) |

## Roadmap — Next Steps

### Workstream C — Notary Data Integration (blocked: needs penotariado.com credentials)
- Scraper for penotariado.com real closing prices by postal code
- New `notary_stats` DB table (postal_code, period, avg_price_sqm, transaction_count)
- Analytics integration: ask-vs-close spread per district/barrio
- Frontend chart: "Precio escritura vs Precio pedido"

### Workstream D — Analytics Redesign
- Remove/demote generic distribution charts (price histogram, size histogram, bedrooms)
- New lead chart: "Oportunidad por Distrito" — composite opportunity score table
- Fix `listed_over_time` to use `listed_date` instead of `created_at`
- Simplify condition analysis to focus on reform upside signal
- Add ML spread annotation noting it's based on manually-valued deals only

### Workstream E — ML Retraining
- **E1**: `POST /ml/retrain` endpoint + "Reentrenar modelo" button in frontend
- **E2**: Training improvements — 5-fold CV, log-transform target, orientation features, per-district outlier filtering, versioned artifacts
- **E3**: Auto-prediction on scrape — run ML on newly ingested deals, write to predictions table

### Data Population
- Railway DB is fresh — run scrapes from deployed app to populate
- Available inventory: Idealista HTML ~15k, Fotocasa ~9k, Pisos.com ~10k, Redpiso ~1.3k

### Other (lower priority)
- Prompt-based scraping (search box on home page)
- Deal detail page `/deals/[id]`
- Rental / Cap Rate financial model

## Reference Files

- `idealista-integration-guide.md` — API field mapping and request examples
- `ModelEconomics.xlsx` — Fix & Flip Excel model (reference spec)
- `~/.claude/plans/polished-strolling-rainbow.md` — full deployment + feature roadmap plan
