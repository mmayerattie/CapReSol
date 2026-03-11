# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Goal

CapReSol is a real estate investment analysis system for Madrid-focused funds. Four core capabilities:
1. **Portal scraping** — automated ingestion of Idealista listings into PostgreSQL
2. **ML valuation** — Gradient Boosting model predicts market price from property features
3. **Fix & Flip analysis** — user inputs investment parameters, system returns IRR, ROE, Equity Multiple, Gross Margin
4. **Frontend** — Next.js UI to search deals, view ML predictions, and run financial analyses

## Commands

### Infrastructure
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

## Architecture

### Data Flow
```
Idealista API / HTML scraper
        ↓
   deals table  (message_id = null for portal scrapes)
        ↓
  ML prediction  →  predictions table
        ↓
 Fix & Flip analysis  →  financial_analyses table (persisted)
```

### Backend (`backend/app/`)

**Entry point**: `main.py` — FastAPI app with CORS middleware (allows `localhost:3000`), mounts `/messages`, `/deals`, `/analyses` routers.

**Database models** (`db/models.py`):
- `Message` — raw inbound data; `channel` field: `portal | gmail | whatsapp`
- `Deal` — structured property record. Full field list: address, city, country, property_type, size_sqm, bedrooms, bathrooms, floor, asking_price, currency, url (unique), broker_name, broker_contact, district, zone, condition, orientation, storage_room, terrace, balcony, elevator, garage, listed_date
- `Prediction` — ML output: predicted_price, model_version, FK to deal
- `FinancialAnalysis` — all FlipInput fields + computed outputs (irr, moic, return_on_equity, gross_margin, profit, gross_exit_price, net_exit_price, total_dev_cost, max_equity_exposure, closing_costs, broker_fee, mortgage_debt, total_debt)

**API layer** (`api/`):
- `deals.py` — `GET /deals`, `POST /deals/from-message`, `POST /deals/scrape`, `POST /deals/predict` (batch)
- `analyses.py` — `POST /analyses` (run + save), `GET /analyses` (history list)
- `messages.py` — message CRUD
- `schemas.py` — all Pydantic models. Note: boolean amenity fields (`storage_room`, `terrace`, etc.) are `Optional[bool] = False` to handle `None` from DB

**Scraping** (`services/portal_scraper.py`):
- `scrape_idealista_api()` — OAuth2 → form-encoded POST to search (see Idealista quirks below)
- `scrape_idealista_html()` — BeautifulSoup HTML fallback, no quota cost
- `ingest_listings(db, listings)` — bulk upsert, deduplicates by `url` unique constraint

**ML pipeline** (`ml/`):
- `features.py` — `deal_to_features(deal)`: Deal ORM → feature dict (Spanish-language keys). Categoricals: `Distrito`, `Zona`, `Estado`, `Ubicacion`. Excludes asking price to prevent leakage.
- `model.py` — `predict_price_from_features(features)`: one-hot encodes categoricals, aligns to training columns, scales, runs GB model. Uses `@lru_cache` for artifact loading.
- `artifacts/` — `best_gb_model.pkl`, `scaler.pkl`, `model_columns.pkl`

**Financial model** (`utils/excel.py`): `run_flip_analysis()` — pure-Python Fix & Flip with monthly equity cash flows and leverage. Inputs: size_sqm, purchase_price, capex_total, capex_months, project_months, exit_price_per_sqm, monthly_opex, ibi_annual, closing_costs_pct (0.075), broker_fee_pct (0.0363), mortgage_ltv, mortgage_rate_annual, capex_debt, capex_debt_rate_annual. Computes IRR via `numpy_financial.irr`. Analyses persisted to `financial_analyses` table. `name` field: auto-populated from deal address if `deal_id` provided, otherwise required as free text.

**Config** (`config.py`): reads `DATABASE_URL`, `IDEALISTA_API_KEY`, `IDEALISTA_SECRET` from `backend/.env`.

### Idealista API — Critical Notes

- **Token URL**: `POST https://api.idealista.com/oauth/token` (NOT `/oauth/accesstoken`)
- **Auth**: Basic auth with `base64(api_key:secret)`, body: `grant_type=client_credentials&scope=read`
- **Search URL**: `POST https://api.idealista.com/3.5/es/search`
- **Search body**: form-encoded (`data=`, NOT `json=`) — the API rejects JSON
- **Madrid location ID**: `0-EU-ES-28`
- **Quota**: 100 req/month, 1 req/sec — enforce with `time.sleep(1.1)` between calls
- **Pagination**: `numPage` param, up to 50 results/page via `maxItems: 50`
- Token expires in ~12 hours (43,200 seconds)

### Infrastructure (`infra/`)
- `docker-compose.yml` — Postgres 16, container `capresol-postgres`, port 5432, DB `capresol`
- Backend runs locally (not containerized)

### Frontend (`frontend/`)
Next.js 14 App Router + Tailwind CSS. Proxy: `/api/*` → `http://localhost:8000/*` (via `next.config.js` rewrites — no trailing slashes in fetch calls or CORS issues arise).

**Pages**:
- `/deals` — scraped listings table, checkbox selection, "Scrape Idealista" button, "Tasación (N)" button → ML predicted price shown inline per row
- `/analyses` — history table of all past analyses + "Nuevo Análisis" modal form with linked price pair inputs (total ↔ €/m² auto-calculate)

**Key files**:
- `lib/api.ts` — typed fetch helpers (no trailing slashes on URLs)
- `app/deals/page.tsx` — deals table with scrape + predict UX
- `app/analyses/page.tsx` — analysis history + new analysis form
- `components/Sidebar.tsx` — nav with active state

**CORS fix**: `main.py` adds `CORSMiddleware` allowing `localhost:3000`. Required because Next.js strips trailing slashes (308 redirect), FastAPI re-adds them (307 redirect to `localhost:8000` directly), bypassing the proxy and hitting a cross-origin block.

## Current Status

| Component | Status |
|---|---|
| DB schema (all fields) | ✅ Complete — migration `b6d9bcc0b86b` applied |
| Idealista API scraper | ✅ Working — 101 deals scraped and stored |
| HTML fallback scraper | ✅ Implemented (untested end-to-end) |
| `POST /deals/scrape` endpoint | ✅ Working |
| `POST /deals/predict` (batch ML) | ✅ Working — verified in production |
| Fix & Flip financial model | ✅ Working — LTV/mortgage/capex debt supported |
| `financial_analyses` table + API | ✅ Working — migration `29ddff7d5d80` applied |
| Frontend — `/deals` page | ✅ Working — scrape, select, predict all functional |
| Frontend — `/analyses` page | ✅ Working — history table + new analysis form functional |

## Roadmap — Next Steps

### Phase 6 — Financial Model Refinement ✅ (partial)
- ✅ Percentage inputs: LTV, rates, fees are entered as % (e.g. 7.5) — converted to decimals on submit
- ✅ Deals page: client-side filtering (district multi-select, m² range, bedrooms multi-select, ask price range, condition multi-select) + sortable columns (m², ask price, €/m²)
- Remaining: improve leverage section labels for non-technical users; validate capex_debt ≤ capex_total

### Phase 7 — Deal Detail Page (`/deals/[id]`)
- Full property info card
- Latest ML prediction
- "Run Analysis" button pre-filling the analysis form with deal data (address, size, price)
- History of analyses run against this deal

### Phase 8 — ML Model Improvement
- Current model trained on ~101 deals; retrain as dataset grows
- Retrain pipeline: `ml/train.py` is a stub — implement training loop, cross-validation, artifact versioning
- Add more features: orientation, amenities (terrace, elevator, garage), floor level
- Dataset growth: keep "Scrape" as a manual button for customers (protect quota); owner can run it freely

### Phase 9 — Scraper Improvements
- Support other portals (Fotocasa, Habitaclia) via HTML scraper for broader dataset
- Scrape filters: price range, size range, specific districts

### Phase 10 — Production (for presentations + small customer base)
- Simple deployment: backend on Railway (free tier, no Docker needed), frontend on Vercel (free), DB on Railway managed Postgres or Supabase
- Basic auth: single shared password or Vercel password protection (sufficient for demo + small customers)
- Environment variables via Railway/Vercel dashboards — no .env files in production

## Reference Files

- `idealista-integration-guide.md` — API field mapping and request examples
- `ModelEconomics.xlsx` — Fix & Flip Excel model (reference spec for the financial model)
- `~/.claude/plans/warm-wobbling-snowflake.md` — full original implementation roadmap
