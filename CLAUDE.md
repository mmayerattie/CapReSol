# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Goal

CapReSol is a real estate investment analysis system for Madrid-focused funds. Four core capabilities:
1. **Portal scraping** — automated ingestion from 5 sources (Idealista API, Idealista HTML, Redpiso, Fotocasa, Pisos.com) into PostgreSQL
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
Idealista API / Idealista HTML (Firecrawl) / Redpiso JSON API / Fotocasa (Firecrawl) / Pisos.com (Firecrawl)
        ↓
  normalize_district() → 21 canonical Madrid districts
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

**Entry point**: `main.py` — FastAPI app with CORS middleware (allows `localhost:3000`), mounts `/messages`, `/deals`, `/analyses` routers.

**Database models** (`db/models.py`):
- `Message` — raw inbound data; `channel` field: `portal | gmail | whatsapp`
- `Deal` — structured property record. Full field list: address, city, country, property_type, size_sqm, bedrooms, bathrooms, floor, asking_price, currency, url (unique), broker_name, broker_contact, district, zone, condition, orientation, storage_room, terrace, balcony, elevator, garage, listed_date
- `Prediction` — ML output: predicted_price, model_version, FK to deal
- `FinancialAnalysis` — all FlipInput fields + computed outputs (irr, moic, return_on_equity, gross_margin, profit, gross_exit_price, net_exit_price, total_dev_cost, max_equity_exposure, closing_costs, broker_fee, mortgage_debt, total_debt)

**API layer** (`api/`):
- `deals.py` — `GET /deals`, `POST /deals/from-message`, `POST /deals/scrape` (portal param: "idealista" | "redpiso" | "fotocasa" | "pisos" | "idealista_html"), `POST /deals/predict` (batch), `DELETE /deals/predictions/{id}` (delete single prediction)
- `analyses.py` — `GET /analyses` (history list), `POST /analyses` (run + save), `PUT /analyses/{id}` (re-run with new inputs, overwrites in-place), `DELETE /analyses/{id}` (delete)
- `messages.py` — message CRUD
- `schemas.py` — all Pydantic models. Note: boolean amenity fields (`storage_room`, `terrace`, etc.) are `Optional[bool] = False` to handle `None` from DB. `FlipResult` now exposes all 7 echoed input fields needed for edit pre-fill: `capex_months`, `monthly_opex`, `ibi_annual`, `closing_costs_pct`, `broker_fee_pct`, `tax_rate`, `capex_debt_rate_annual`.

**Scraping** (`services/portal_scraper.py`):
- `scrape_idealista_api()` — OAuth2 → form-encoded POST to search (see Idealista quirks below). 50 results/page, 100 req/month quota.
- `scrape_idealista_html()` — Firecrawl bypasses DataDome bot protection. 30 listings/page, ~15,374 available. No API quota cost. Parses markdown: title link `[Piso en X, Barrio, Madrid](url)`, price, features, amenities.
- `scrape_redpiso_html()` — Redpiso JSON API (`/api/properties`), no auth, 50/page, 1,284+ Madrid listings available. Includes `broker_name` and `broker_contact` (phone).
- `scrape_fotocasa_firecrawl()` — Firecrawl + `location={'country': 'ES'}` to bypass geo-block. ~31 listings/page, 9,439 available. Parses markdown via regex: title, price, features, amenities.
- `scrape_pisos_firecrawl()` — Firecrawl, 30 listings/page, ~10,500 available. Extracts district + zone from "Barrio (Distrito X. Madrid Capital)" pattern. Condition extracted via keyword matching on title + context text ("a reformar" → `renew`, "obra nueva" → `newdevelopment`, "buen estado" → `good`).
- `normalize_district()` — Maps scraped district/barrio names to one of Madrid's 21 canonical districts. Uses `_DISTRICT_ALIASES` dict with ~150 barrio→district mappings. Returns `None` for non-Madrid municipalities (which are then filtered out by `ingest_listings()`).
- `ingest_listings(db, listings)` — PostgreSQL upsert via `ON CONFLICT DO UPDATE`. Filters: requires `url`, `asking_price`, `size_sqm`, and a canonical Madrid district. COALESCE for data-quality fields, OVERWRITE for mutable fields. Deduplicates by `url` unique constraint. Reruns are fully safe.
- User-agent rotation: `USER_AGENTS` list + `_html_headers()` helper adds random UA + Referer to all requests.
- **Backfill removed** — `backfill_deal_details()`, `_extract_fields_from_idealista_detail()`, and `_extract_fields_from_fotocasa_detail()` were deleted (~230 lines). Strategy going forward: improve forward scrapers to capture all fields (amenities, condition, floor, zone) upfront at search-page level rather than revisiting individual detail pages. The `POST /deals/backfill-details` endpoint and the "Completar datos" UI button were also removed.

**Data quality rules** (enforced in `ingest_listings()`):
- Listings without `asking_price` are dropped
- Listings without `size_sqm` are dropped
- Listings outside Madrid's 21 canonical districts are dropped
- District names are normalised before insert (barrio → district mapping)

**ML pipeline** (`ml/`):
- `features.py` — `deal_to_features(deal)`: Deal ORM → feature dict (Spanish-language keys). Categoricals: `Distrito`, `Zona`, `Estado`, `Ubicacion`. Excludes asking price to prevent leakage.
- `model.py` — `predict_price_from_features(features)`: one-hot encodes categoricals, aligns to training columns, scales, runs GB model. Uses `@lru_cache` for artifact loading.
- `artifacts/` — `best_gb_model.pkl`, `scaler.pkl`, `model_columns.pkl`
- `train.py` — **fully implemented**. Queries DB, filters 500–25,000 €/m² outliers, one-hot encodes categoricals, StandardScaler, GradientBoostingRegressor(n_estimators=300, max_depth=5, lr=0.05, subsample=0.8). Run with `python -m app.ml.train` from `backend/`. Last trained 2026-03-13: 2,461 deals, sklearn 1.7.2, R²=0.791, MAE≈€198k. **Restart backend after retraining** to clear `@lru_cache` on artifact loaders.
- `scikit-learn` is unpinned in `requirements.txt` — version pin removed to avoid pickle incompatibility when upgrading.

**Financial model** (`utils/excel.py`): `run_flip_analysis()` — pure-Python Fix & Flip with monthly equity cash flows and leverage. Inputs: size_sqm, purchase_price, capex_total, capex_months, project_months, exit_price_per_sqm, monthly_opex, ibi_annual, closing_costs_pct (0.075), broker_fee_pct (0.0363), mortgage_ltv, mortgage_rate_annual, capex_debt, capex_debt_rate_annual. Computes IRR via `numpy_financial.irr`. Analyses persisted to `financial_analyses` table. `name` field: auto-populated from deal address if `deal_id` provided, otherwise required as free text.

**Config** (`config.py`): reads `DATABASE_URL`, `IDEALISTA_API_KEY`, `IDEALISTA_SECRET`, `FIRECRAWL_API_KEY` from `backend/.env`.

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
- **Response fields**: `slug` (for URL), `price`, `cadastre_property_summary.{bedrooms, bathrooms, usable_meters}`, `location.{district.name, quarter.name}`, `display_location` (address), `office.{name, phone}` (broker)
- **URL pattern**: `https://www.redpiso.es/inmueble/{slug}`
- **Total available**: ~1,283 Madrid sale listings (as of March 2026)
- No quota limits observed. Add `time.sleep(1.1 + random(0, 0.5))` between pages as courtesy.

### District Normalisation

Madrid has 21 official districts. The `normalize_district()` function in `portal_scraper.py` maps ~150 barrio names and spelling variants to canonical names: Centro, Arganzuela, Retiro, Salamanca, Chamartín, Tetuán, Chamberí, Fuencarral-El Pardo, Moncloa-Aravaca, Latina, Carabanchel, Usera, Puente de Vallecas, Moratalaz, Ciudad Lineal, Hortaleza, Villaverde, Villa de Vallecas, Vicálvaro, San Blas-Canillejas, Barajas.

Listings from suburban municipalities (Getafe, Alcobendas, Rivas, etc.) are automatically dropped during ingestion.

### Infrastructure (`infra/`)
- `docker-compose.yml` — Postgres 16, container `capresol-postgres`, port 5432, DB `capresol`
- Backend runs locally (not containerized)

### Frontend (`frontend/`)
Next.js 14 App Router + Tailwind CSS. Proxy: `/api/*` → `http://localhost:8000/*` (via `next.config.js` rewrites — no trailing slashes in fetch calls or CORS issues arise).

**Pages**:
- `/` (home) — dashboard with date header, natural-language search stub ("Busca propiedades… próximamente"), quick stats bar (total listings, districts, avg €/m²), recent 5 deals table with clickable URLs, "New listings" scrape button, and 4 quick-nav cards (Deals / Valuaciones / Análisis / Analytics).
- `/deals` — listings table with column-header inline filter dropdowns for every column (including null-include "Sin datos" options on categorical filters), "New listings" button (scrapes all 5 portals sequentially), "Tasación (N)" button → ML predicted price shown inline per row. Pagination: 25/50/100/All per page. Column picker "Columnas ⚙" persists selection to `localStorage`. New columns: **Fuente** (derived from URL — Idealista/Redpiso/Fotocasa/Pisos.com/Manual) and **F. Listing** (`listed_date`). Default hides Amenidades. Filters: Distrito, Zona (none), m², Hab. (+ sin datos), Baños (+ sin datos), Planta (checkbox list), Precio, €/m² (sort only), Estado (+ sin estado), Amenidades (Ascensor/Terraza/Garaje toggles), Fuente (checkbox). All filters have null-include "Sin datos" checkbox where applicable.
- `/valuaciones` — ML valuation page. Select deals, run batch prediction, view predicted vs asking price. Each prediction row has a 🗑 delete button with inline confirm.
- `/analyses` — history table of all past Fix & Flip analyses + "Nuevo Análisis" modal form with linked price pair inputs (total ↔ €/m² auto-calculate). Each row has ✎ edit (re-opens modal pre-filled, converts pct fields ×100 for display) and 🗑 delete with inline confirm. Edit calls `PUT /analyses/{id}` which re-runs the analysis and overwrites the record in-place (ID + `created_at` preserved).
- `/analytics` — market analytics dashboard (see Analytics section below).

**Key files**:
- `lib/api.ts` — typed fetch helpers (no trailing slashes on URLs). `scrapeDeals(portal, pageFrom?)` accepts `'idealista' | 'redpiso' | 'fotocasa' | 'pisos' | 'idealista_html'`. `getAnalyticsStats(maxPriceSqm?, minPriceSqm?)` passes outlier bounds as query params.
- `app/page.tsx` — home dashboard. Loads all deals client-side for quick stats; reuses `getDeals()` + `scrapeDeals()` from `lib/api`.
- `app/deals/page.tsx` — deals table. Filters are column-header dropdowns (not a panel). Sort arrows use ▲▼ (not ↑↓ which render as emoji). Pagination state: `page`, `pageSize`. Scraping flow: Idealista API → Redpiso → Fotocasa → Pisos.com → Idealista HTML. Column visibility controlled by `visibleCols` state (persisted to `localStorage` key `deals_visible_cols`). `getSource(url)` helper derives portal name from URL.
- `app/api/deals/scrape/route.ts` — Next.js Route Handler that proxies `POST /api/deals/scrape` to FastAPI with `maxDuration = 300` and a 4.5-minute AbortSignal timeout.
- `app/analytics/page.tsx` — analytics dashboard using Recharts. See Analytics section below.
- `app/analyses/page.tsx` — analysis history + new analysis form.
- `components/Sidebar.tsx` — nav with active state.

**Scraping flow per "New listings" click**:
1. Idealista API (10 pages, uses 100 req/month quota)
2. Redpiso JSON (3 chunks × 9 pages = 27 pages)
3. Fotocasa via Firecrawl (3 chunks × 3 pages = 9 pages)
4. Pisos.com via Firecrawl (3 chunks × 3 pages = 9 pages)
5. Idealista HTML via Firecrawl (3 chunks × 3 pages = 9 pages)

Each Firecrawl portal uses try/catch with break-on-failure to avoid blocking the flow. **Socket hang up fixed**: `app/api/deals/scrape/route.ts` is a Next.js Route Handler that intercepts `/api/deals/scrape` before the proxy rewrite, setting `maxDuration = 300` and `AbortSignal.timeout(270_000)` on the upstream fetch. This eliminates the 30s proxy timeout.

**Analytics dashboard** (`app/analytics/page.tsx`):
Built with Recharts (BarChart, PieChart). Outlier filter presets in the header control `maxPsqm` / `minPsqm` state, which trigger a `useEffect` re-fetch on change. Charts shown:
1. **Precio €/m² por Distrito** — horizontal bar, sorted desc, with city-average ReferenceLine.
2. **Upside de Reforma por Distrito** — gap between avg price of "good" vs "renew" listings per district (investment signal).
3. **Distribución por Estado** — stacked horizontal bar by district + overall pie chart (A reformar / Buen estado / Nueva).
4. **Spread ML vs Precio Pedido** — table of districts with avg `(ml_predicted - asking) / asking`. Green > +5%, yellow 0–5%, red < 0%. **Note**: only covers deals for which ML predictions have been manually run via `/valuaciones` — it is NOT market-wide. The "Deals valorados" count is the ML-prediction sample size per district, which is small and self-selected. Will become meaningful once auto-prediction on scrape is implemented.
5. **Cartera analizada** — KPI strip (avg IRR, MOIC, ROE) from `financial_analyses` table. Shown only if any analyses exist.
6. *(Expandable via "Mostrar más")* Price histogram, size histogram, bedrooms distribution, amenity prevalence bars (elevator/terrace/balcony/garage/storage).

KPI strip: Dataset count (with active filter label), avg city €/m², highest reform upside district, most affordable district.

**Analytics backend** (`api/analytics.py`):
`GET /analytics?max_price_sqm=25000&min_price_sqm=500` — both params default to their respective values (0 = no bound).
`price_ok` filter tuple applied consistently to all queries for a coherent dataset across all sections.
`by_district` returns per-district: `count`, `avg_price_sqm`, `avg_size`, `reform_upside` (avg_good − avg_renew), `ml_vs_ask_avg` (ratio of ML prediction vs asking, for deals with predictions), `condition_by_district` (renew/good/new counts).
`portfolio_summary` aggregates `financial_analyses` table: count, avg IRR, avg MOIC, avg ROE.

**CORS fix**: `main.py` adds `CORSMiddleware` allowing `localhost:3000`. Required because Next.js strips trailing slashes (308 redirect), FastAPI re-adds them (307 redirect to `localhost:8000` directly), bypassing the proxy and hitting a cross-origin block.

## Current Status

| Component | Status |
|---|---|
| DB schema (all fields) | ✅ Complete — migration `b6d9bcc0b86b` applied |
| Idealista API scraper | ✅ Working — 474 pages available (50/page), 100 req/month |
| Idealista HTML via Firecrawl | ✅ Working — ~15,374 listings, 30/page, no quota |
| Redpiso JSON API scraper | ✅ Working — 1,283 listings, includes broker phone |
| Fotocasa via Firecrawl | ✅ Working — 9,439 listings, 31/page, geo-proxied to ES |
| Pisos.com via Firecrawl | ✅ Working — 10,507 listings, 30/page, district+zone |
| District normalisation | ✅ Working — 21 canonical Madrid districts, ~150 barrio mappings |
| Data quality filters | ✅ Working — require price, size, Madrid district |
| `POST /deals/scrape` endpoint | ✅ Working — 5 portal options |
| `POST /deals/predict` (batch ML) | ✅ Working — retrained on 2,461 deals (sklearn 1.7.2, R²=0.791) |
| ML `train.py` | ✅ Implemented — run `python -m app.ml.train` from `backend/` |
| Analytics endpoint `GET /analytics` | ✅ Working — outlier filter params `min_price_sqm` / `max_price_sqm` |
| Fix & Flip financial model | ✅ Working — LTV/mortgage/capex debt supported |
| `financial_analyses` table + API | ✅ Working — migration `29ddff7d5d80` applied |
| Frontend — home dashboard `/` | ✅ Working — quick stats, recent deals, scrape button, nav cards |
| Frontend — `/deals` page | ✅ Working — full column filters (all columns), column visibility picker, Fuente + Fecha Listing columns |
| Frontend — `/valuaciones` page | ✅ Working — batch ML predictions + per-row delete |
| Frontend — `/analyses` page | ✅ Working — history table + new analysis form + per-row edit/delete |
| Frontend — `/analytics` page | ✅ Working — Recharts dashboards, outlier filter presets, portfolio KPIs |
| Pisos.com condition extraction | ✅ Added — keyword matching on listing text |
| Socket hang up fix | ✅ Fixed — Route Handler with maxDuration=300 at `app/api/deals/scrape/route.ts` |
| Edit/delete analyses + predictions | ✅ Working — PUT/DELETE endpoints + frontend inline confirm UI |
| Backfill feature | ❌ Removed — endpoint, functions, and UI deleted |
| Dataset size | ~2,464 clean Madrid deals (as of 2026-03-13) |

## Roadmap — Next Steps

### Priority 1 — Scale up data extraction
- Current dataset: ~2,464 deals. Available inventory: Idealista HTML ~15k, Fotocasa ~9k, Pisos.com ~10k
- Can increase page counts per scrape or run multiple scrape cycles
- Improve forward scrapers to capture more fields (floor, zone, amenities) upfront — avoids need for per-listing detail requests
- Redpiso condition: API has no condition field — only option is per-listing detail requests (against current strategy)

### Priority 2 — Prompt-based scraping
- UI stub already present on home page (`/`): disabled search box "Busca propiedades… próximamente"
- Backend: `POST /deals/scrape-prompt` — parse free text into Idealista/Redpiso filter params
- Can use Claude API or simple regex/keyword extraction to parse
- Reuses existing scraper functions from `portal_scraper.py`

### Priority 3 — Model retraining pipeline
- `train.py` is now fully functional; run manually: `python -m app.ml.train`
- Auto-retrain trigger: every 200 new deals OR every 3 weeks
- Endpoint `POST /ml/retrain` to trigger manually from the frontend
- Versioned artifact filenames (timestamp suffix)

### Priority 4 — Financial models
- Fix & Flip: review `ModelEconomics.xlsx` and align debt service schedule precisely
- New: Rental / Cap Rate model — `cap_rate = NOI / purchase_price` where `NOI = (monthly_rent × 12) - annual_opex - ibi_annual`
- Separate endpoint + frontend section for rental analysis

### Phase — Deal Detail Page (`/deals/[id]`) (deferred)
- Full property info card
- Latest ML prediction
- "Run Analysis" button pre-filling the analysis form with deal data
- History of analyses run against this deal

### Phase — Production (deferred)
- Backend on Railway, frontend on Vercel, DB on Railway Postgres or Supabase
- Basic auth: shared password or Vercel password protection

## Reference Files

- `idealista-integration-guide.md` — API field mapping and request examples
- `ModelEconomics.xlsx` — Fix & Flip Excel model (reference spec for the financial model)
- `~/.claude/plans/warm-wobbling-snowflake.md` — full original implementation roadmap
