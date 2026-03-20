# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Goal

CapReSol is a real estate investment analysis system for Madrid-focused funds. Six core capabilities:
1. **Portal scraping** — automated ingestion from 5 sources (Idealista API, Idealista HTML, Redpiso, Fotocasa, Pisos.com) into PostgreSQL
2. **ML valuation** — Gradient Boosting model predicts market price from property features (log-transformed, 5-fold CV)
3. **Fix & Flip analysis** — user inputs investment parameters, system returns IRR, ROE, Equity Multiple, Gross Margin
4. **Notary data** — real transaction closing prices from penotariado.com (ArcGIS API), 55 Madrid postal codes, 9 filter combinations
5. **Analytics dashboard** — opportunity-focused: 3 upside charts, negotiation margins, ML spread, condition distribution
6. **Multi-user auth** — JWT-based authentication with 6 user accounts, deployed on Railway + Vercel

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

### ML Retraining
```bash
cd backend && python -m app.ml.train    # Manual retrain from CLI
# Or via API: POST /ml/retrain (clears lru_cache automatically)
```

## Production Deployment

### Architecture
- **Backend**: Railway (Docker) → `https://capresol-production.up.railway.app`
- **Frontend**: Vercel → `https://cap-re-sol.vercel.app`
- **Database**: Railway Postgres (internal: `postgres.railway.internal`, public URL for external access)
- Both auto-redeploy on push to `main`

### Backend (Railway)
- Dockerfile at `backend/Dockerfile`: Python 3.11-slim, runs alembic migrations + seeds users + starts uvicorn
- `--proxy-headers --forwarded-allow-ips='*'` on uvicorn — required because Railway terminates SSL; without these, FastAPI's trailing-slash redirects generate `http://` URLs
- `PYTHONPATH=/app` for alembic module resolution
- `config.py` auto-converts Railway's `postgresql://` to `postgresql+psycopg2://`
- Users seeded automatically on every deploy from `USERS_CONFIG` (idempotent)

### Frontend (Vercel)
- Root directory: `frontend`
- `NEXT_PUBLIC_API_URL` env var set to Railway HTTPS URL (all environments)
- `lib/api.ts` calls Railway directly (not via Next.js rewrites) — Vercel rewrites to external URLs behave as client-visible redirects causing Mixed Content
- HTTP→HTTPS forced in code, skipped for localhost
- `middleware.ts` excludes `/api` routes from auth check
- `.env.local` (git-ignored) sets `NEXT_PUBLIC_API_URL=http://localhost:8000` for local dev

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
   deals table → auto ML prediction on new deals (model_version="auto")
        ↓
  Analytics: joins deals (asking) with notary_stats (closing) by postal_code → district

penotariado.com ArcGIS API → notary_stats table (55 postal codes × 9 combos)
```

### Backend (`backend/app/`)

**Entry point**: `main.py` — FastAPI app with CORS middleware (`allow_origins` from env, `allow_credentials=True`), mounts routers: `/auth`, `/messages`, `/deals`, `/analyses`, `/analytics`, `/ml`, `/notary`.

**Authentication** (`api/auth.py`):
- `POST /auth/login` — accepts `{username, password}`, returns `{access_token, token_type}`
- `get_current_user` dependency — validates Bearer JWT
- All routers protected except `/auth/login` and `GET /`
- bcrypt password hashing, 7-day JWT expiry

**Database models** (`db/models.py`):
- `User` — id, username, hashed_password, created_at
- `Deal` — full field list: address, city, country, property_type, size_sqm, bedrooms, bathrooms, floor, asking_price, currency, url (unique), broker_name, broker_contact, district, zone, condition, orientation, storage_room, terrace, balcony, elevator, garage, listed_date, postal_code
- `Prediction` — predicted_price, model_version, FK to deal
- `FinancialAnalysis` — all FlipInput fields + computed outputs
- `NotaryStat` — postal_code, construction_type (todos/nueva/segunda_mano), property_class (todos/pisos/casas), notary_price_sqm, notary_avg_price, notary_avg_surface, notary_transactions, notary_total

**API layer** (`api/`):
- `auth.py` — login + get_current_user
- `deals.py` — `GET /deals`, `POST /deals/scrape`, `POST /deals/predict` (batch), `DELETE /deals/predictions/{id}`
- `analyses.py` — CRUD for Fix & Flip analyses
- `analytics.py` — `GET /analytics?max_price_sqm=&min_price_sqm=&notary_construction=&notary_class=`
  - Returns: by_district (with avg_price_renew, avg_price_good, avg_price_new, avg_size_renew, n_renew, n_good, n_new), notary_by_district (unified filtered), notary_prices_by_type (segunda_mano + nueva per district), opportunity_table, condition_by_district, histograms, amenities, timeline, portfolio
  - Unified filters: notary_construction maps to deal conditions (segunda_mano → renew+good, nueva → newdevelopment), notary_class maps to deal property_type
- `ml.py` — `POST /ml/retrain` — retrains model, clears lru_cache, returns metrics
- `notary.py` — `POST /notary/scrape`, `GET /notary?construction_type=&property_class=`
- `messages.py` — message CRUD
- `schemas.py` — all Pydantic models

**Scraping** (`services/portal_scraper.py`):
- 5 scrapers: Idealista API, Idealista HTML (Firecrawl), Redpiso JSON, Fotocasa (Firecrawl), Pisos.com (Firecrawl)
- `normalize_district()` — ~150 barrio→district mappings
- `extract_postal_code()` — regex + ZONE_TO_POSTAL fallback (131 barrios)
- `ingest_listings()` — upsert + auto ML prediction on new deals (`_auto_predict_new_deals`)
- Idealista HTML: context window 3000 chars, features sub-window 1200 chars, fallback regex for bathrooms/floor/orientation

**Notary scraper** (`services/notary_scraper.py`):
- Source: `https://services-eu1.arcgis.com/UpPGybwp9RK4YtZj/arcgis/rest/services/agol_precio_m2/FeatureServer/4/query`
- Layer 4 = Codigo Postal level
- Filter IDs: tipo_construccion_id (7=nueva, 9=segunda_mano, 99=todos), clase_finca_urbana_id (14=pisos, 15=casas, 99=todos)
- Scrapes all 9 combinations (3 tipo × 3 clase) for postal codes 28001–28055
- Public API, no auth required
- Data from Colegio General del Notariado (official notary body)

**ML pipeline** (`ml/`):
- `train.py` — log-transform target (`np.log1p`), 5-fold CV, timestamped artifacts, returns metrics dict
- `model.py` — `predict_price_from_features()`: applies `np.expm1` to reverse log-transform. `@lru_cache` on artifact loaders
- `features.py` — `deal_to_features(deal)`: categoricals: Distrito, Zona, Estado, Ubicacion
- GradientBoostingRegressor(n_estimators=300, max_depth=5, lr=0.05, subsample=0.8)
- Auto-predict on scrape: new deals get predictions with `model_version="auto"`

**Financial model** (`utils/excel.py`): `run_flip_analysis()` — Fix & Flip with monthly equity cash flows, leverage, IRR via `numpy_financial.irr`.

### Frontend (`frontend/`)
Next.js 14 App Router + Tailwind CSS + Recharts.

**API architecture**: `NEXT_PUBLIC_API_URL` controls backend target. Production calls Railway directly. Local uses `/api` proxy. HTTPS forced except for localhost.

**Authentication**:
- `lib/auth.ts` — JWT in localStorage + cookie `capresol_token`
- `middleware.ts` — redirects unauthenticated (no cookie) to `/login`, excludes `/api` routes
- `app/login/page.tsx` — full page reload on success (`window.location.href`)

**Pages**:
- `/` — dashboard with stats, recent deals, scrape button, nav cards
- `/deals` — full table with column filters, pagination, ML predictions inline. Supports URL params `?district=X&condition=Y` for pre-filtered views (linked from analytics)
- `/valuaciones` — batch ML predictions + per-row delete
- `/analyses` — Fix & Flip history + modal + edit/delete
- `/analytics` — opportunity-focused dashboard (see Analytics section)
- `/login` — auth form

**Analytics dashboard** (`app/analytics/page.tsx`):
Section order:
1. **KPI Strip** — Dataset count, listings a reformar, top opportunity district, most affordable district
2. **Oportunidad real por distrito** — Ask reformar (portal) vs Closing nuevo (notary). Conservative upside with clickable listings → deals page filtered by district+condition
3. **Upside en portales** — Ask reformar vs Ask buen estado. Optimistic upside with clickable listings
4. **Upside del mercado** — Closing segunda mano vs Closing nueva (both notarial). Market ceiling
5. **Margen de negociacion** — Ask vs closing spread per district (how much room to negotiate). Filter: Todos/Segunda mano/Obra nueva
6. **Valoracion ML** — ML predicted vs asking price spread per district
7. **Estado de la propiedad** — Condition pie chart (reformar/buen estado/nueva)
8. **Nuevos listings por mes** — Timeline (listed_date, not created_at)
9. **Cartera analizada** — Portfolio KPIs (IRR, MOIC, ROE) from financial analyses
10. **Mostrar mas** — Precio/m2 por distrito, price/size/bedrooms histograms, amenities

Global filters: Max/Min EUR/m2 presets + Pisos/Casas/Todos (applies to all charts)

## Current Status

| Component | Status |
|---|---|
| JWT Authentication | ✅ 6 users, login, protected routes |
| Production deployment | ✅ Railway + Vercel, auto-redeploy on push |
| DB schema | ✅ deals, users, predictions, financial_analyses, notary_stats |
| 5-portal scraping | ✅ Working with auto ML prediction on new deals |
| Notary data (penotariado) | ✅ 55 postal codes × 9 combos, ArcGIS API |
| Analytics dashboard | ✅ 3 opportunity charts, negotiation margins, ML spread |
| ML retrain endpoint | ✅ POST /ml/retrain with log-transform, 5-fold CV, cache clear |
| Auto-predict on scrape | ✅ New deals get ML predictions automatically |
| Postal code extraction | ✅ Regex + ZONE_TO_POSTAL fallback (131 barrios) |
| Idealista HTML scraper | ✅ Improved: 3000-char context, bathroom/orientation fallbacks |
| Fix & Flip model | ✅ LTV/mortgage/capex debt supported |
| Deals page URL params | ✅ ?district=X&condition=Y pre-filters from analytics links |
| Dataset | ~2,699 deals on Railway (migrated from local) |
| Notary data on Railway | ⚠️ Need to run POST /notary/scrape after deploy |

## Roadmap — Next Steps

### Data Population
- Run POST /notary/scrape on Railway after deploy
- Run more scrape cycles to grow dataset (available: Idealista HTML ~15k, Fotocasa ~9k, Pisos.com ~10k)

### Analytics Improvements
- Add "Reentrenar modelo" button in frontend (endpoint exists: POST /ml/retrain)
- Barrio-level breakdown (expandable from district view)
- Time-series notary data (if penotariado API supports historical periods)

### New Features (lower priority)
- Prompt-based scraping (search box on home page, parse text to filter params)
- Deal detail page `/deals/[id]` with property card, ML prediction, analysis history
- Rental / Cap Rate financial model
- Export analytics to PDF/Excel

## Reference Files

- `idealista-integration-guide.md` — API field mapping and request examples
- `ModelEconomics.xlsx` — Fix & Flip Excel model (reference spec)
- `Distritos_Barrios_Madrid.md` — Madrid district/barrio structure reference
