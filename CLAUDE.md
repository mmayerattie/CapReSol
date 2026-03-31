# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Goal

CapReSol is a real estate investment analysis system for Madrid-focused funds. Six core capabilities:
1. **Portal scraping** — automated ingestion from 5 sources (Idealista API, Idealista HTML, Redpiso, Fotocasa, Pisos.com) into PostgreSQL
2. **ML valuation** — Gradient Boosting model (best of 4 tested: LR, RF, GB, XGB) predicts market price from 15 features. R-squared 0.883 CV on 4,425 deals. Zone cardinality reduction applied.
3. **Fix & Flip analysis** — user evaluates investment opportunities with IRR, ROE, MOIC, Gross Margin from monthly equity cash flows with leverage
4. **Notary data** — real transaction closing prices from penotariado.com (ArcGIS API), 55 Madrid postal codes, 9 filter combinations
5. **Analytics dashboard** — opportunity-focused: 3 upside charts, negotiation margins, ML spread, condition distribution, opportunity scoring
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
# Model comparison: POST /ml/compare?experiment=a (or b, c, c2, d)
```

### Production API calls (all need trailing-slash awareness — Railway 307 redirects)
```bash
# Authenticate
TOKEN=$(curl -s -X POST "https://capresol-production.up.railway.app/auth/login" -H "Content-Type: application/json" -d '{"username":"Admin","password":"Capstone26100"}' | python3 -c "import sys,json; print(json.load(sys.stdin)['access_token'])")

# Retrain ML model
curl -s -L -X POST "https://capresol-production.up.railway.app/ml/retrain" -H "Authorization: Bearer $TOKEN"

# Compare models (experiment a=baseline, b=drop zone, c=impute good, c2=impute segunda_mano, d=price/sqm target)
curl -s -L -X POST "https://capresol-production.up.railway.app/ml/compare?experiment=a" -H "Authorization: Bearer $TOKEN"

# Backfill postal codes
curl -s -L -X POST "https://capresol-production.up.railway.app/deals/backfill-postal-codes" -H "Authorization: Bearer $TOKEN"

# Backfill condition/exterior/orientation from detail pages (uses Firecrawl credits)
curl -s -L -X POST "https://capresol-production.up.railway.app/deals/backfill-details?limit=30" -H "Authorization: Bearer $TOKEN"

# Cleanup bad zone values
curl -s -L -X POST "https://capresol-production.up.railway.app/deals/cleanup-zones" -H "Authorization: Bearer $TOKEN"
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
- **IMPORTANT**: Railway has HTTP request timeout. ML compare endpoint must run one experiment at a time (4 models max). Use `?experiment=a` parameter.

### Frontend (Vercel)
- Root directory: `frontend`
- `NEXT_PUBLIC_API_URL` env var set to Railway HTTPS URL (all environments)
- `lib/api.ts` calls Railway directly (not via Next.js rewrites)
- HTTP→HTTPS forced in code, skipped for localhost
- `middleware.ts` excludes `/api` routes from auth check

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

**Entry point**: `main.py` — FastAPI app with CORS middleware, mounts routers: `/auth`, `/messages`, `/deals`, `/analyses`, `/analytics`, `/ml`, `/notary`.

**Database models** (`db/models.py`):
- `User` — id, username, hashed_password, created_at
- `Deal` — 26 fields including: address, city, property_type, size_sqm, bedrooms, bathrooms, floor, asking_price, url (unique), broker_name, broker_contact, district, zone, condition, orientation, storage_room, terrace, balcony, elevator, garage, **exterior** (boolean, added 2026-03-31), listed_date, postal_code
- `Prediction` — predicted_price, model_version, FK to deal
- `FinancialAnalysis` — all FlipInput fields + computed outputs
- `NotaryStat` — postal_code, construction_type, property_class, notary_price_sqm, notary_avg_price, notary_avg_surface, notary_transactions, notary_total

**API layer** (`api/`):
- `auth.py` — login + get_current_user
- `deals.py` — `GET /deals`, `POST /deals/scrape`, `POST /deals/predict` (batch, max 25), `DELETE /deals/predictions/{id}`, `POST /deals/backfill-postal-codes`, `POST /deals/backfill-details?limit=&portal=`, `POST /deals/cleanup-zones`
- `analyses.py` — CRUD for Fix & Flip analyses
- `analytics.py` — `GET /analytics?max_price_sqm=&min_price_sqm=&notary_construction=&notary_class=`
- `ml.py` — `POST /ml/retrain`, `POST /ml/compare?experiment=a|b|c|c2|d`
- `notary.py` — `POST /notary/scrape`, `GET /notary?construction_type=&property_class=`
- `messages.py` — message CRUD
- `schemas.py` — all Pydantic models

**Scraping** (`services/portal_scraper.py`):
- 5 scrapers: Idealista API, Idealista HTML (Firecrawl), Redpiso JSON, Fotocasa (Firecrawl), Pisos.com (Firecrawl)
- Shared helpers: `_detect_condition()` (13 Spanish keyword variants), `_detect_exterior()` (context-aware), `_detect_orientation()` (structured + fallback)
- `normalize_district()` — ~150 barrio→district mappings
- `extract_postal_code()` — regex + ZONE_TO_POSTAL fallback (131 barrios)
- `ingest_listings()` — upsert with COALESCE (preserve non-null) + OVERWRITE (price, amenities, exterior)
- Fotocasa zone: extracted from URL slug only (address fallback removed — was grabbing amenities as zone)
- **Known limitation**: Redpiso API has NO condition, orientation, floor, or amenity data. These can only be obtained by scraping individual detail pages via Firecrawl.

**Backfill scripts** (`scripts/`):
- `backfill_postal_codes.py` — 3-phase postal code backfill using ZONE_TO_POSTAL (exact, partial, district fallback)
- `backfill_detail_fields.py` — visits individual listing URLs via Firecrawl to fill condition/exterior/orientation. Handles expired listings (404/redirect). Rate limited at 2s per deal. Uses Firecrawl credits.
- `cleanup_bad_zones.py` — nulls out zone values containing amenity keywords
- `seed_users.py` — seeds users from USERS_CONFIG env var

**ML pipeline** (`ml/`):
- `train.py` — log-transform target, **zone cardinality reduction (zones < 10 deals → empty)**, 5-fold CV, timestamped artifacts
- `model.py` — `predict_price_from_features()`: applies `np.expm1` to reverse log-transform. `@lru_cache` on artifact loaders
- `features.py` — `deal_to_features(deal)`: 4 numeric (size, beds, baths, floor), 6 binary (storage, terrace, balcony, elevator, garage, **exterior**), 4 categorical (district, zone, condition, orientation)
- `compare_models.py` — trains LR, RF, GB, XGBoost with A/B experiments. Experiments: a=baseline, b=drop zone+orientation, c=impute condition as good, c2=impute as segunda_mano, d=target price/sqm
- Production model: GradientBoostingRegressor(n_estimators=300, max_depth=5, lr=0.05, subsample=0.8)
- Model version: `gb_20260331_155727`

**Financial model** (`utils/excel.py`): `run_flip_analysis()` — Fix & Flip with monthly equity cash flows, dual-debt leverage, IRR via `numpy_financial.irr`.

### Frontend (`frontend/`)
Next.js 14 App Router + Tailwind CSS + Recharts.

**Pages**:
- `/` — dashboard with stats, recent deals, scrape button, nav cards
- `/deals` — full table with column filters (including **Ext/Int** and **Orientation** columns), pagination, ML predictions inline, URL params `?district=X&condition=Y`
- `/valuaciones` — batch ML predictions (max 25), checkbox multi-select, bulk delete, delete all, newest first sorting
- `/analyses` — Fix & Flip history + modal + edit/delete
- `/analytics` — 10-section opportunity dashboard with global filters
- `/login` — auth form

## Current Status (as of 2026-03-31)

| Component | Status |
|---|---|
| JWT Authentication | ✅ 6 users, login, protected routes |
| Production deployment | ✅ Railway + Vercel, auto-redeploy on push |
| DB schema | ✅ deals (26 fields incl. exterior), users, predictions, financial_analyses, notary_stats |
| 5-portal scraping | ✅ Working with shared condition/exterior/orientation detectors |
| Notary data | ✅ 55 postal codes × 9 combos |
| Analytics dashboard | ✅ 3 opportunity charts, negotiation margins, ML spread, opportunity scoring |
| ML model | ✅ GB R²=0.883 CV, 4,425 deals, zone cleanup, 4-model comparison done |
| ML compare endpoint | ✅ POST /ml/compare with 5 experiment configurations |
| Postal code backfill | ✅ Coverage 11.9% → 71.4% |
| Detail page backfill | ✅ Condition 50.6% → 66.1%, Exterior 0% → 10.6% |
| Fix & Flip model | ✅ LTV/mortgage/capex debt supported |
| Valuaciones bulk actions | ✅ Multi-select delete, delete all, max 25 predictions |
| Deals page columns | ✅ Ext/Int + Orientation columns added |
| Dataset | 4,432 deals on Railway |
| EDA figures | ✅ 9 figures in figures/ directory |
| Thesis draft | ✅ FinalDraft.docx.md — restructured with EDA, model comparison, all 24 comments applied |

## EDA Key Findings (for thesis reference)

- **District** (eta²=0.52) and **zone** (eta²=0.49) explain ~50% of price variance each
- **Bathrooms** (r=+0.31) is the strongest numeric predictor; bedrooms has zero correlation with price/sqm
- **Condition** (eta²=0.006 aggregate) appears irrelevant but is a Simpson's paradox: renew is cheaper in 15/20 districts when controlling for location
- **Amenity premiums** (elevator +53%, terrace +50%) are confounded with district
- **Missing condition** (34% of dataset) comes mainly from Redpiso (100% missing) and behaves price-wise like "good" condition
- **Zone cardinality**: 35% of zones have < 5 deals. Mapping zones < 10 deals to empty reduces features 327→201 and improves all models

## ML Experiment Results (2026-03-31)

| Experiment | Best R² CV | Best MAE | Winner |
|---|---|---|---|
| A: Baseline (zone cleanup) | 0.883 | 167,418 | GB |
| B: Drop zone + orientation | 0.860 | 176,211 | XGB |
| C: B + impute as good | 0.858 | 180,846 | XGB |
| C2: B + impute as segunda_mano | 0.860 | 177,632 | XGB |
| D: B + target price/sqm | 0.856* | 174,415 | GB |

**Production uses Experiment A.** Zone carries too much signal to drop.

## Thesis Status

- **File**: `FinalDraft.docx.md`
- **Structure**: Abstract → Introduction → Literature Review → Methodology → EDA → ML Model → Financial Model → Analytics → Results → Conclusions
- **All 24 comments from docx review applied**
- **Estimated pages**: ~32 text + ~8 figures/screenshots = ~40 pages
- **Pending**: professional feedback [PLACEHOLDER], screenshots to insert, final formatting for .docx export
- **Figures**: 9 EDA charts in `figures/` directory, all regenerated with latest 4,432-deal data

## Roadmap — Next Steps

### Thesis Completion
- Fill in professional feedback from 5 practitioners (Argentina + Spain)
- Take screenshots of production app for Appendix
- Export to .docx and format (TNR 12pt, 1.5 spacing)
- Final review

### Data & Model
- More scraping cycles to grow dataset
- Get more Firecrawl credits for detail page backfill (condition gap)
- Improve condition detection in Pisos.com and Fotocasa scrapers

### Features (lower priority)
- "Reentrenar modelo" button in frontend
- Deal detail page `/deals/[id]`
- Cap Rate / rental financial model
- Scheduled scraping (cron)
- Export analytics to PDF/Excel

## Reference Files

- `idealista-integration-guide.md` — API field mapping and request examples
- `ModelEconomics.xlsx` — Fix & Flip Excel model (reference spec)
- `Distritos_Barrios_Madrid.md` — Madrid district/barrio structure reference
- `APA 6th Edition template.md` — Thesis formatting template
- `FinalDraft.docx.md` — Current thesis draft
- `FinalDraft_MayerATT.docx` — Version with 24 review comments (already applied)
