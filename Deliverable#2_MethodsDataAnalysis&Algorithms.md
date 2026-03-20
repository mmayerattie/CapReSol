# CapReSol: Automated Real Estate Investment Analysis for Madrid

## Data Collection, Machine Learning Valuation, and Financial Modeling

## [Author Name]

## [Institution Name]

# Author Note

[First paragraph: Complete departmental and institutional affiliation]

[Second paragraph: Acknowledgments and special circumstances]

[Third paragraph: Contact information, mailing address and e-mail]

# Abstract

This thesis presents CapReSol, a software system built to address the fragmentation of real estate investment workflows in Madrid. Property data sits scattered across five portals, each with different formats, access methods, and coverage. Investment professionals spend hours manually collecting listings, estimating values through intuition, and running financial projections in disconnected spreadsheets. CapReSol consolidates these steps into a single platform. It scrapes property listings from Idealista, Redpiso, Fotocasa, and Pisos.com through APIs and web scraping, normalizes the data into a unified PostgreSQL schema, and applies a Gradient Boosting regression model to predict market prices. The system integrates official notary closing price data from the Colegio General del Notariado, covering 55 Madrid postal codes across nine filter combinations, to benchmark asking prices against real transaction values. A Fix and Flip financial model computes IRR, MOIC, ROE, and gross margin from monthly equity cash flows with leverage support. An analytics dashboard surfaces investment opportunities by comparing asking prices against closing prices, ML predictions against listings, and renovation candidates against finished properties across Madrid's 21 districts. Trained on 3,190 listings, the Gradient Boosting model achieves an R-squared of 0.87 on held-out data and 0.89 on five-fold cross-validation. The system is deployed as a production web application on Railway and Vercel with JWT-based multi-user authentication.

*Keywords:* real estate, machine learning, property valuation, web scraping, investment analysis, Madrid, gradient boosting, fix and flip, automated valuation model

#

#

# CapReSol: Automated Real Estate Investment Analysis for Madrid

## Background and context

In 2024, real estate investment in Spain reached approximately 14 billion euros, with Madrid accounting for 31 percent of the total volume (CBRE, 2024). Investment funds and private investors, including family offices, comprised nearly a third of total investment activity. Residential assets alone amounted to 4.3 billion euros, making Madrid one of Europe's most active residential investment markets.

At the same time, the number of new housing units created per household has been declining since 2018, reaching its lowest level since 2014 in 2023 (BBVA Research, 2024). Fewer new units mean fewer opportunities, which makes it essential for investors to identify and act on deals quickly. In a scarce environment, the difference between securing a profitable acquisition and missing it often comes down to speed and analytical depth.

Yet the tools available to most investment professionals do not match the pace of the market. Property listings sit on five or more portals, each with its own data format, access method, and coverage area. Idealista publishes structured data through an API but caps requests at 100 per month. Fotocasa and Pisos.com render listings through JavaScript, making automated access more complex. Redpiso exposes a public JSON endpoint but with limited property detail. An analyst searching for renovation opportunities across all of Madrid must visit each portal separately, compare listings manually, and maintain spreadsheets to track what has already been reviewed.

This fragmentation is not unique to Spain. According to the 2025 European PropTech report, 62 percent of real estate professionals find it difficult to identify the right technology tool, citing a fragmented market with many options that rarely cover the full workflow (Maps PropTech API, 2025). When asked which processes need the most help, 47 percent of respondents chose automation, doubling from the previous year. Repetition remains a major burden. Most agencies operate with three to five separate solutions, and 20 percent report that the tools they use do not match their needs.

The real estate technology sector has grown substantially in Europe, which now hosts 50 percent of PropTech companies worldwide, with a particular focus on the residential sector in countries with high demand and elevated prices per square meter, such as Spain (European PropTech Report, 2025). Within this sector, 60 percent of companies operate in B2B or B2B2C models, and the most commonly adopted technologies are valuation and reporting tools at 64 percent, automation tools at 28 percent, and platforms at 24 percent (Maps PropTech API, 2025).

However, adoption does not mean satisfaction. A small minority of professionals consider PropTech solutions affordable, and cost remains the primary barrier to adoption at 60 percent, followed by lack of information at 45 percent. Despite this, 80 percent of respondents said technology improved their processes, and 41 percent consider spending between 150 and 400 euros per month on technology acceptable. The issue is not willingness to pay but perceived value. Tools that are simple, integrated, and demonstrably useful justify higher investment.

This thesis responds to that gap. CapReSol consolidates the fragmented real estate investment workflow into a single platform, covering data collection, valuation, and financial analysis.

## Problem statement

Real estate investment professionals in Madrid face three compounding inefficiencies that this thesis aims to address:

**Data fragmentation.** Property listings are distributed across five or more portals with no unified view. Each portal uses different data schemas, access methods, and coverage. An analyst tracking renovation opportunities must manually browse each site, cross-reference listings by address, and maintain external records to avoid duplication. There is no standard way to aggregate these sources into a single, filterable dataset.

**Valuation opacity.** Without a systematic method for estimating market value, professionals rely on intuition and manual comparison of similar properties. Automated Valuation Models do exist in the industry, but they are typically proprietary, expensive, and designed for institutional lenders rather than investment analysts. No widely accessible tool combines property features with market data to estimate fair value for the kind of deal-by-deal analysis that funds and individual investors require.

**Analytical gap.** Even when data is collected and a valuation is formed, no system bridges the full pipeline from deal sourcing through financial analysis. Investment decisions require not only knowing a property's estimated value but also computing metrics such as IRR, MOIC, and ROE under specific renovation and financing assumptions. Today, this analysis happens in disconnected Excel spreadsheets, separate from the deal data and predictions. Similarly, there is no integrated way to compare asking prices against official notary closing prices to assess negotiation margins or to surface which districts offer the best risk-adjusted opportunities.

These three problems feed into each other. Fragmented data makes it harder to build a reliable valuation model. Without systematic valuation, financial projections are anchored to guesswork. And without a single platform, every step of the analysis requires switching between tools, which slows things down and increases the chance of mistakes.

## Objectives

The primary objective of this thesis is to design, implement, and deploy an end-to-end system that automates the real estate investment analysis pipeline for Madrid's residential market.

This primary objective is supported by six specific goals:

1. Automate the collection of property listings from five heterogeneous sources into a unified, structured PostgreSQL database.
2. Build and evaluate a supervised machine learning model that predicts property market value from physical and locational features.
3. Integrate official notary closing price data from the Colegio General del Notariado to benchmark asking prices against real transaction values.
4. Implement a Fix and Flip financial model that computes IRR, MOIC, ROE, and gross margin from monthly equity cash flows with leverage and tax support.
5. Deliver an analytics dashboard that identifies district-level investment opportunities by comparing asking prices, closing prices, ML predictions, and renovation potential.
6. Deploy the system as a secure, multi-user web application with production-grade infrastructure.

## Scope and delimitations

The system targets Madrid's residential real estate market exclusively. Geographic coverage spans the city's 21 administrative districts and 55 postal codes (28001 through 28055). Data collection draws from five specific portals: Idealista (both API and HTML scraping), Redpiso, Fotocasa, and Pisos.com. Notary data comes from the Colegio General del Notariado through its public ArcGIS API.

The machine learning component is limited to supervised regression for price prediction. It does not include time-series forecasting, image-based analysis, or rental yield estimation. The financial modeling implements Fix and Flip analysis only; a Cap Rate model for rental investment strategy was planned but not implemented within the scope of this thesis. The system supports six authenticated users, reflecting the scale of a small fund team rather than a public-facing platform.

## Significance of the study

This work contributes in three ways. It delivers a working system, not a proof of concept, that runs in production with over 3,000 listings and serves authenticated users. It demonstrates a complete pipeline from raw portal HTML to investment decision metrics, something most academic work and commercial products only address in pieces. And it responds to a real market need, validated through feedback from five real estate professionals in Argentina and Spain, reported in the Results chapter.

## Thesis organization

The remainder of this thesis is organized as follows. Chapter 2 reviews the literature on PropTech, machine learning for property valuation, financial modeling, and decision support systems. Chapter 3 describes the research methodology, technology selection, and development process. Chapter 4 presents the system architecture, database schema, authentication, and deployment infrastructure. Chapter 5 details the data collection pipeline, including the five scrapers, normalization logic, and notary data integration. Chapter 6 covers the machine learning valuation model, from feature engineering through training, evaluation, and deployment. Chapter 7 explains the Fix and Flip financial model. Chapter 8 describes the analytics dashboard and opportunity scoring algorithm. Chapter 9 reports the results and includes discussion of findings, professional feedback, and limitations. Chapter 10 offers conclusions and directions for future work.

# Literature Review

## PropTech and real estate technology

PropTech, a term combining property and technology, refers to the application of digital tools across the real estate lifecycle, from search and acquisition through management and disposition. The category spans a wide range of solutions including marketplaces, valuation tools, property management platforms, and investment analysis software.

In Europe, PropTech has grown to represent roughly half of all companies in the sector worldwide, with particular concentration in countries with high housing demand and elevated prices per square meter (European PropTech Report, 2025). Spain is among the most active markets in Southern Europe. Spanish real estate companies are increasingly using advanced technologies, including artificial intelligence, smart data tools, and digital marketplaces, to identify opportunities and improve operations across design, development, and brokerage (PwC, 2025).

The distribution of business models within PropTech leans heavily toward enterprise clients: 60 percent of companies operate in B2B or B2B2C models, while 40 percent target consumers directly. Among B2B solutions specifically, 28 companies focus on valuation and 135 on internal operations, representing 33 percent of the sector (Maps PropTech API, 2025).

Despite the growth, the industry appears to be entering a consolidation phase. Adoption has already happened for most firms; the focus is now on making existing tools work better, optimizing usage, and embedding technology into daily operations rather than adding more point solutions (Maps PropTech API, 2025).

## Automated data collection in real estate

Collecting property data from multiple online sources involves two main technical approaches: structured API access and web scraping.

Structured APIs, such as the one provided by Idealista, return property data in standardized JSON format with defined fields, pagination, and authentication. Their advantage is data quality and reliability; their limitation is typically rate limits and cost. Idealista's API, for instance, enforces a cap of 100 requests per month and limits pagination to 50 results per page.

Web scraping extracts data from rendered HTML pages. Modern property portals often use JavaScript frameworks to render content dynamically in the browser, which means traditional HTTP-based scrapers see empty pages. Services like Firecrawl address this by rendering pages through headless browsers and returning the visible content as clean markdown or HTML. This approach unlocks portals such as Fotocasa and Pisos.com, which would otherwise resist automated data collection.

The main challenge in multi-source data collection is schema heterogeneity. Each portal names fields differently, structures data in its own format, and has different levels of completeness. A three-bedroom apartment on Idealista has structured fields for bedrooms, bathrooms, and floor. The same listing on Fotocasa may bury those details inside a text description. Entity resolution, figuring out whether two listings from different portals are the same property, adds difficulty. The most reliable deduplication strategy for portal data is matching on listing URL, since each portal assigns unique URLs.

The Extract, Transform, Load pattern governs this type of pipeline. Raw data is extracted from heterogeneous sources, transformed into a canonical schema through parsing and normalization, and loaded into a relational database. For real estate specifically, normalization must handle geographic entities: barrio names must map to canonical district names, and postal codes must be extracted from free-text addresses.

## Machine learning for property valuation

The use of quantitative models to estimate property value has a long academic history. Hedonic pricing models, formalized by Rosen (1974), decompose a property's price into the implicit value of its individual characteristics: location, size, number of rooms, condition, and amenities. These models traditionally use linear regression, which provides interpretability but assumes a linear relationship between features and price.

More recent work has applied machine learning methods that relax this linearity assumption. Decision trees partition the feature space recursively to fit non-linear patterns. Random forests aggregate many trees to reduce variance through bagging. Gradient Boosting builds trees sequentially, with each new tree correcting the errors of the ensemble so far. XGBoost and LightGBM are optimized implementations of gradient boosting that have dominated structured data competitions and applied research in recent years.

For property price prediction specifically, gradient boosting methods have shown strong performance across multiple geographies. Baldominos, Saez, and Quintana (2018) applied ensemble methods to Spanish housing data and found that gradient boosting outperformed linear regression and random forests on MAE and RMSE metrics. Kok, Kopczuk, and Timmins (2017) demonstrated the value of large-scale property data combined with machine learning for real estate valuation at scale.

A common preprocessing step for price prediction is log-transformation of the target variable. Property prices follow a right-skewed distribution: most properties cluster in a moderate price range, while a long tail extends toward expensive properties. Applying `log(1 + price)` compresses this distribution, allowing the model to learn proportional errors rather than absolute ones. At inference time, the prediction is reversed with `exp(prediction) - 1`. This transformation typically improves both training stability and evaluation metrics for tree-based models.

Feature engineering for real estate models involves three categories of variables. Numeric features such as size in square meters, number of bedrooms, bathrooms, and floor level. Binary features capturing the presence or absence of amenities like elevator, terrace, garage, and storage room. Categorical features encoding location (district, neighborhood) and property state (condition, orientation), which are typically one-hot encoded for tree-based models.

Model evaluation uses standard regression metrics. R-squared measures the proportion of variance explained. Mean Absolute Error (MAE) gives the average prediction error in the same units as the target, making it directly interpretable for business decisions. Root Mean Squared Error (RMSE) penalizes large errors more heavily. Mean Absolute Percentage Error (MAPE) normalizes errors by the actual value, providing a scale-independent measure. Cross-validation, typically k-fold with k equal to 5 or 10, estimates how well the model generalizes to unseen data by training and testing on different partitions of the dataset.

## Financial modeling for real estate investment

The Fix and Flip strategy involves purchasing an undervalued property, typically in need of renovation, improving it, and selling at a higher price. It is one of the most common active investment strategies in residential real estate, particularly in markets where significant stock exists in conditions described as "a reformar" (needing renovation).

The primary metric for evaluating a flip investment is the Internal Rate of Return (IRR), which represents the discount rate at which the net present value of all cash flows equals zero. For real estate flips with holding periods measured in months, IRR is computed from monthly cash flows and then annualized. The formula converts monthly IRR to annual: `annual_IRR = (1 + monthly_IRR)^12 - 1`.

Complementary metrics include the Multiple on Invested Capital (MOIC), which measures total cash returned divided by total equity invested; Return on Equity (ROE), which measures profit divided by maximum equity exposure; and Gross Margin, which divides profit by total development cost. Each metric captures a different dimension of the investment: MOIC reflects total return, ROE reflects capital efficiency, and Gross Margin reflects cost control.

Leverage, the use of debt to finance part of the acquisition and renovation, amplifies both returns and risk. A mortgage covering a portion of the purchase price reduces the equity required upfront, increasing IRR and ROE when the deal is profitable. However, interest payments during the holding period reduce absolute profit. Financial models must account for the monthly cost of both acquisition debt (mortgage) and renovation debt (capex financing), typically modeled as interest-only during the holding period with full principal repayment at exit.

## Notary and transaction data

Spain's notary system, administered by the Colegio General del Notariado, records the closing price of every real estate transaction. These transaction prices differ from the asking prices published on portals. The gap between asking and closing represents the negotiation margin, a critical piece of market intelligence for investors.

The Colegio General del Notariado makes aggregated transaction data publicly available through an ArcGIS FeatureServer API hosted at penotariado.com. The data is organized by geographic level, with Layer 4 providing postal code granularity. For each postal code, the API returns the average transaction price per square meter, average total transaction price, average property surface area, and transaction counts. These statistics can be filtered by construction type (nueva, segunda mano, or all) and property class (pisos, casas, or all), yielding nine filter combinations.

What makes this data useful is that it represents actual transaction prices, not aspirational asking prices. Comparing portal asking prices against notary closing prices by district shows which areas have the largest negotiation margins and where asking prices most diverge from what buyers actually pay.

## Analytics and decision support systems

Dashboards in real estate investment work best when they answer specific questions rather than just displaying numbers. Where are the best opportunities? How much room is there to negotiate? Is the market pricing a property fairly? These are the questions an analyst has open in their head when looking at deal flow.

Opportunity scoring algorithms rank geographic areas by combining signals: entry price, renovation upside, model-predicted undervaluation. Averaging the ranks across these dimensions produces a single score per district. The advantage of this approach is balance. It avoids fixating on a single metric.

Comparing data sources against each other is where the real insights come from. Asking prices versus notary closing prices reveal negotiation margins. ML predicted prices versus asking prices flag systematic mispricing. And "a reformar" prices versus "buen estado" prices in the same district quantify what renovation is actually worth.

## Gap in the literature

Existing academic work and commercial products tend to address individual components of the real estate investment pipeline. Automated Valuation Models focus on price prediction. Portal aggregators focus on data collection. Financial modeling tools focus on investment returns. Dashboard products focus on market visualization.

| Capability | IntellCRE | HouseCanary | Cherre | ATTOM | CoreLogic | Quantarium | CapReSol |
|---|---|---|---|---|---|---|---|
| Multi-source scraping | No | No | Partial | No | No | No | Yes |
| ML valuation | Yes | Yes | No | Yes | Yes | Yes | Yes |
| Notary/transaction data | No | Yes | Partial | Partial | Yes | Partial | Yes |
| Financial modeling | Partial | No | No | No | No | No | Yes |
| Analytics dashboard | Partial | Yes | Yes | Partial | Yes | No | Yes |
| Madrid-specific | No | No | No | No | No | No | Yes |

*Table 1.* Capabilities of commercial competitors compared to CapReSol.

No published system combines multi-source portal scraping, ML valuation, official notary closing price data, financial modeling with leverage, and an opportunity-focused analytics dashboard in a single production application. The closest commercial products, HouseCanary and CoreLogic, operate only in the United States and focus on valuation rather than the full investment pipeline.

The numbers reflect this. Ninety-two percent of firms report piloting AI tools, but only 5 percent have achieved their stated goals, largely because of legacy infrastructure and fragmented data ingestion (v7 Labs, 2026). Most existing solutions handle the analysis stage but skip the messy work of collecting, normalizing, and deduplicating data from unstructured sources.

This thesis fills that gap by building a system that covers the full pipeline, from raw portal HTML to investment decision metrics, for the Madrid residential market.

# **Method**

## **Research Approach**

This thesis follows a Design Science Research methodology. The core contribution is a software artifact, the CapReSol system, designed to solve an identified real-world problem. The artifact is evaluated through two mechanisms: quantitative metrics (ML model performance, dataset coverage) and qualitative feedback from five real estate professionals in Argentina and Spain.

The development followed an iterative approach, building each system capability incrementally: database schema first, then data collection, then machine learning, then financial modeling, then analytics, and finally authentication and deployment. Each iteration was tested against production data before moving to the next component.

## **System Requirements**

### **Functional Requirements**

| ID | Requirement | Description |
|---|---|---|
| FR1 | Multi-source scraping | Collect listings from Idealista (API + HTML), Redpiso, Fotocasa, Pisos.com |
| FR2 | ML valuation | Predict property price from physical and locational features |
| FR3 | Notary integration | Ingest closing price data from penotariado.com for 55 postal codes |
| FR4 | Financial analysis | Compute Fix and Flip metrics (IRR, MOIC, ROE, Gross Margin) with leverage |
| FR5 | Analytics dashboard | Surface district-level opportunities with upside, negotiation, and ML charts |
| FR6 | Multi-user auth | JWT-based login with bcrypt password hashing for 6 user accounts |

*Table 2.* Functional requirements.

### **Non-functional Requirements**

**Security.** All API endpoints except login are protected by JWT authentication. Passwords are hashed with bcrypt. Tokens expire after seven days.

**Availability.** The system auto-deploys on push to the main branch. Railway restarts the backend container on failure. Vercel serves the frontend from a global CDN.

**Performance.** ML model artifacts are cached in memory using Python's `lru_cache` decorator, so inference after the first request avoids disk reads. The analytics endpoint returns all 13 data structures in a single response to minimize round-trips.

**Data integrity.** PostgreSQL provides ACID compliance. URL uniqueness constraints prevent duplicate listings. Composite unique keys on notary records prevent duplicate postal code entries.

## **Technology Selection**

| Layer | Technology | Justification |
|---|---|---|
| Backend API | FastAPI (Python) | Native ML ecosystem (scikit-learn, pandas, numpy), async support, automatic OpenAPI docs, Pydantic validation |
| Database | PostgreSQL 16 | ACID compliance, robust upsert support (ON CONFLICT), UUID primary keys, JSON column type |
| ORM | SQLAlchemy | Python-native ORM, migration support through Alembic, compatible with FastAPI dependency injection |
| Migrations | Alembic | Schema versioning, autogenerated migration scripts, rollback support |
| Frontend | Next.js 14 (React) | App Router for file-based routing, server-side rendering, Tailwind CSS integration |
| Styling | Tailwind CSS | Utility-first CSS, rapid UI development, consistent design |
| Charts | Recharts | React-native charting, bar/line/pie/area chart types, responsive design |
| ML framework | scikit-learn | GradientBoostingRegressor, StandardScaler, cross_val_score, established library |
| ML serialization | joblib | Efficient serialization of scikit-learn models and numpy arrays |
| Financial math | numpy-financial | IRR computation from cash flow arrays |
| Backend hosting | Railway | Docker containers, managed PostgreSQL, auto-deploy from GitHub, SSL termination |
| Frontend hosting | Vercel | Optimized for Next.js, global CDN, auto-deploy from GitHub |

*Table 3.* Technology stack.

The backend runs as a single FastAPI service. An earlier design considered separating routing and coordination into a Node.js layer with FastAPI handling only ML inference, but this was abandoned in favor of a unified Python service. FastAPI handles all API routing, authentication, database operations, scraping orchestration, ML inference, financial computation, and analytics aggregation. Consolidating into a single service reduced operational complexity and eliminated inter-service HTTP latency.

Uvicorn is the ASGI server that runs the FastAPI application. It handles concurrent HTTP requests and supports the proxy headers configuration that Railway's SSL termination layer requires.

## **Data Sources**

| Source | Method | Auth | Approx. Volume | Key Fields |
|---|---|---|---|---|
| Idealista API | REST API (OAuth2) | Client ID + Secret | ~500/cycle (rate limited) | All structured: price, size, rooms, floor, amenities, condition |
| Idealista HTML | Firecrawl (JS render) | Firecrawl API key | ~15,000 listings | Regex-parsed from markdown: price, size, rooms, condition |
| Redpiso | JSON API | None (public) | ~1,300 listings | Structured: price, size, rooms, district, broker info |
| Fotocasa | Firecrawl (JS render) | Firecrawl API key | ~9,000 listings | Regex-parsed from markdown: price, size, rooms, condition |
| Pisos.com | Firecrawl (JS render) | Firecrawl API key | ~10,500 listings | Regex-parsed from markdown: price, size, rooms, district |
| Notary (penotariado) | ArcGIS FeatureServer | None (public) | 55 postal codes x 9 combos | Avg price/sqm, avg total price, avg surface, transaction counts |

*Table 4.* Data sources.

## **Development Process**

Development proceeded through eight sequential phases:

1. **Database schema design.** Defined six tables (users, deals, predictions, financial_analyses, notary_stats, messages) with SQLAlchemy models and Alembic migrations.
2. **Idealista API scraper.** Built OAuth2 authentication flow, pagination, field mapping, and district normalization.
3. **Additional scrapers.** Added Redpiso (JSON API), Fotocasa (Firecrawl), Pisos.com (Firecrawl), and Idealista HTML (Firecrawl) with unified ingestion logic.
4. **ML training pipeline.** Implemented feature engineering, log-transform, Gradient Boosting training, five-fold cross-validation, and artifact management.
5. **Fix and Flip financial model.** Ported from Excel reference model to Python, implementing monthly equity cash flows with leverage and IRR computation.
6. **Notary data integration.** Built ArcGIS API client for all nine filter combinations across 55 postal codes.
7. **Analytics dashboard.** Implemented backend aggregation endpoint with 13 data structures and frontend with 10 chart sections.
8. **Authentication and deployment.** Added JWT auth with bcrypt hashing, configured Railway Docker deployment, Vercel frontend, and CORS for cross-origin access.

# System architecture and design

## High-level architecture

The system follows a three-tier architecture deployed across two cloud services:

```
┌──────────────────────────────┐
│        Frontend (Vercel)     │
│   Next.js 14 + Tailwind CSS │
│       + Recharts             │
│   https://cap-re-sol.vercel  │
│            .app              │
└──────────────┬───────────────┘
               │ HTTPS (REST/JSON)
               │
┌──────────────▼───────────────┐
│      Backend (Railway)       │
│   FastAPI + Uvicorn          │
│   7 API routers              │
│   ML inference + scraping    │
│   https://capresol-production│
│        .up.railway.app       │
└──────────────┬───────────────┘
               │ psycopg2
               │
┌──────────────▼───────────────┐
│    Database (Railway)        │
│   PostgreSQL 16              │
│   6 tables, UUID PKs        │
│   postgres.railway.internal  │
└──────────────────────────────┘
```

*Figure 1.* Three-tier deployment architecture.

The frontend communicates with the backend exclusively through HTTPS REST calls. The backend connects to PostgreSQL using psycopg2 through SQLAlchemy's ORM layer. Both the frontend and backend auto-deploy from the main branch on GitHub: Railway rebuilds the Docker container for the backend, and Vercel rebuilds the Next.js application for the frontend.

## Backend architecture

The FastAPI application is structured around seven router modules, each handling a distinct functional area:

```
main.py (FastAPI app)
├── /auth      → Login, JWT issuance
├── /deals     → GET listings, POST scrape, POST predict, DELETE prediction
├── /analyses  → CRUD for Fix & Flip financial analyses
├── /analytics → GET dashboard aggregations (13 data structures)
├── /ml        → POST retrain model
├── /notary    → POST scrape notary data, GET query
└── /messages  → CRUD for incoming messages
```

CORS middleware is configured from the `ALLOWED_ORIGINS` environment variable, accepting requests from both localhost (development) and the Vercel domain (production) with `allow_credentials=True` to support cookie-based session management.

Authentication is enforced through a `get_current_user` dependency that validates the Bearer JWT token on every protected endpoint. The only unprotected endpoints are `POST /auth/login` and `GET /` (root health check).

Database sessions are managed through a `get_db` dependency that yields a SQLAlchemy session and ensures cleanup after each request. Configuration is loaded from environment variables through a Pydantic `BaseSettings` class, which handles type conversion (including the `postgresql://` to `postgresql+psycopg2://` transformation required by Railway's database URL format).

## Database schema

The database consists of six tables with UUID primary keys and referential integrity constraints:

```
┌─────────────┐     ┌─────────────────────────────────────┐
│   users      │     │              deals                   │
├─────────────┤     ├─────────────────────────────────────┤
│ id (UUID PK)│     │ id (UUID PK)                        │
│ username    │     │ message_id (FK → messages, nullable)│
│ hashed_pwd  │     │ address, city, country               │
│ created_at  │     │ property_type, size_sqm              │
└─────────────┘     │ bedrooms, bathrooms, floor           │
                    │ asking_price, currency                │
┌─────────────┐     │ url (UNIQUE)                         │
│  messages    │     │ broker_name, broker_contact           │
├─────────────┤     │ district, zone, condition             │
│ id (UUID PK)│     │ orientation, postal_code              │
│ channel     │     │ storage_room, terrace, balcony        │
│ source_id   │     │ elevator, garage                      │
│ sender      │     │ listed_date, created_at               │
│ received_at │     └───────────┬─────────────────────────┘
│ raw_subject │                 │
│ raw_body    │     ┌───────────▼─────────┐
│ attachments │     │    predictions       │
│ created_at  │     ├─────────────────────┤
└─────────────┘     │ id (UUID PK)        │
                    │ deal_id (FK → deals) │
┌───────────────┐   │ predicted_price      │
│ notary_stats  │   │ model_version        │
├───────────────┤   │ created_at           │
│ id (UUID PK)  │   └─────────────────────┘
│ postal_code   │
│ construction  │   ┌─────────────────────────┐
│ _type         │   │  financial_analyses      │
│ property_class│   ├─────────────────────────┤
│ notary_price  │   │ id (UUID PK)            │
│ _sqm          │   │ deal_id (FK, nullable)  │
│ notary_avg    │   │ name                     │
│ _price        │   │ [16 input fields]        │
│ notary_avg    │   │ [13 output fields]       │
│ _surface      │   │ created_at               │
│ notary_txns   │   └─────────────────────────┘
│ notary_total  │
│ scraped_at    │
│ UNIQUE(postal │
│ _code, type,  │
│ class)        │
└───────────────┘
```

*Figure 2.* Entity-Relationship diagram.

| Table | Records | Key Constraints | Purpose |
|---|---|---|---|
| users | 6 | username UNIQUE | JWT authentication |
| deals | 3,195 | url UNIQUE | Property listings from all sources |
| predictions | variable | deal_id FK | ML price predictions per deal |
| financial_analyses | variable | deal_id FK (nullable) | Fix and Flip analysis results |
| notary_stats | up to 495 | (postal_code, construction_type, property_class) UNIQUE | Notary closing price aggregates |
| messages | variable | — | Raw incoming messages (WhatsApp, email) |

*Table 5.* Database tables summary.

The deals table uses a unique constraint on the `url` column to enable upsert operations. When a scraper encounters a listing that already exists in the database, the `ON CONFLICT DO UPDATE` clause updates specific fields rather than rejecting the insert. This design allows re-scraping the same portal pages without creating duplicates while still capturing price changes and newly available data.

## Authentication system

Authentication follows a standard JWT flow:

```
Client                          Server
  │                               │
  │  POST /auth/login             │
  │  {username, password}         │
  │ ─────────────────────────────>│
  │                               │  verify bcrypt hash
  │                               │  generate JWT (HS256)
  │  {access_token, token_type}   │  7-day expiry
  │ <─────────────────────────────│
  │                               │
  │  GET /deals/                  │
  │  Authorization: Bearer <jwt>  │
  │ ─────────────────────────────>│
  │                               │  decode JWT
  │                               │  lookup user in DB
  │  [deals data]                 │  return data
  │ <─────────────────────────────│
```

*Figure 3.* Authentication sequence diagram.

Passwords are hashed using bcrypt with automatic salt generation. The JWT payload contains only the username and expiration timestamp, signed with an HS256 secret stored as an environment variable. User accounts are seeded automatically on each deployment from the `USERS_CONFIG` environment variable, using an idempotent script that skips existing usernames.

On the frontend, the JWT token is stored in both localStorage (for API calls) and an HTTP cookie (for the Next.js middleware to check on server-side route changes). When a 401 response is received, the token is cleared and the user is redirected to the login page.

## Deployment architecture

```
GitHub main branch
       │
       ├──── push triggers ────► Railway
       │                         ├── Docker build (backend/Dockerfile)
       │                         │   └── python:3.11-slim
       │                         │       ├── alembic upgrade head
       │                         │       ├── python -m scripts.seed_users
       │                         │       └── uvicorn app.main:app
       │                         │           --host 0.0.0.0
       │                         │           --proxy-headers
       │                         │           --forwarded-allow-ips='*'
       │                         │
       │                         └── PostgreSQL 16 (managed)
       │                             └── postgres.railway.internal
       │
       └──── push triggers ────► Vercel
                                 └── Next.js 14 build
                                     └── NEXT_PUBLIC_API_URL
                                         = Railway HTTPS URL
```

*Figure 4.* Deployment pipeline.

The `--proxy-headers` and `--forwarded-allow-ips='*'` flags on uvicorn are required because Railway terminates SSL at its edge layer and proxies requests to the container over HTTP. Without these flags, FastAPI's automatic trailing-slash redirects would generate `http://` URLs, causing mixed content errors in the browser.

The frontend's API client forces HTTPS on the base URL in production to prevent mixed content blocks, but skips this enforcement for localhost during development.

# Data collection pipeline

## Multi-source scraping architecture

The system collects property listings using three distinct scraping strategies, selected based on each portal's technical constraints:

**Strategy 1: REST API (Idealista).** The Idealista API provides structured JSON responses through an OAuth2 authentication flow. The system obtains an access token using client credentials, then paginates through listing results at a rate of one request per 1.1 seconds to respect the API's throttling limits. Each response contains up to 50 listings with structured fields for price, size, rooms, floor, amenities, condition, and geolocation. The API is rate-limited to 100 requests per month, making it the highest-quality but most constrained data source.

**Strategy 2: JSON API (Redpiso).** Redpiso exposes a public JSON endpoint at `redpiso.es/api/properties` that requires no authentication. The system paginates through results in batches of 50, extracting structured property data including district, quarter (zona), property type, price, bedrooms, bathrooms, and broker contact information. This source provides clean structured data but has limited coverage of approximately 1,300 listings and does not include amenity details (elevator, garage, terrace).

**Strategy 3: JavaScript-rendered HTML via Firecrawl (Idealista HTML, Fotocasa, Pisos.com).** Three portals render their content through JavaScript, making traditional HTTP scraping ineffective. The system uses Firecrawl, a web scraping service that renders pages through headless browsers and returns clean markdown. The returned markdown is then parsed using regular expressions to extract property attributes.

Each Firecrawl-based scraper has specific parsing logic:

- **Idealista HTML** uses a 3,000-character context window after each listing title to extract features, with a nested 1,200-character sub-window for the "Caracteristicas basicas" section. Fallback regex patterns handle variations in bathroom count, floor level, and orientation formatting.
- **Fotocasa** handles the portal's dual-price format (where full and reduced prices may appear together) by taking the first price value. A structured "Caracteristicas" section is parsed for condition, elevator, and orientation.
- **Pisos.com** extracts the district from parenthetical location strings in the format "Barrio (Distrito District. Madrid Capital)" and uses a 200-character window before each title for price extraction and a 400-character window after for feature extraction.

| Source | Strategy | Auth | Rate Limit | Volume | Amenity Data | Condition Data |
|---|---|---|---|---|---|---|
| Idealista API | REST API | OAuth2 | 100 req/month, 1/sec | ~500/cycle | Yes | Yes |
| Idealista HTML | Firecrawl | API key | Firecrawl limits | ~15,000 | Partial | Yes |
| Redpiso | JSON API | None | None observed | ~1,300 | No | No |
| Fotocasa | Firecrawl | API key | Firecrawl limits | ~9,000 | Partial | Yes |
| Pisos.com | Firecrawl | API key | Firecrawl limits | ~10,500 | Partial | Yes |

*Table 6.* Scraping strategy comparison.

## Data normalization

Raw listing data from each portal must be transformed into a canonical schema before storage. Two normalization steps are critical: district normalization and postal code extraction.

**District normalization.** Madrid is divided into 21 administrative districts, each containing multiple barrios (neighborhoods). Portals refer to locations using barrio names, district names, or variations of either. The `normalize_district()` function maps approximately 150 barrio name variants to 21 canonical district names.

The algorithm first attempts an exact lookup in a dictionary of barrio-to-district mappings (case-insensitive). If no exact match is found, it performs a partial match, checking whether any known alias is contained within the input string, preferring longer matches to avoid false positives. A blacklist filter rejects invalid entries such as "distrito unico." Locations outside Madrid's 21 districts return `None` and the listing is excluded from the dataset.

| Raw Input (from portal) | Canonical District |
|---|---|
| "Legazpi" | Arganzuela |
| "Embajadores, Centro" | Centro |
| "Barrio de Salamanca" | Salamanca |
| "Gaztambide" | Chamberí |
| "PAU de Carabanchel" | Carabanchel |
| "Casco Historico de Vallecas" | Puente de Vallecas |

*Table 7.* District normalization examples.

**Postal code extraction.** The `extract_postal_code()` function uses a two-step approach. First, a regex pattern `\b(28\d{3})\b` searches the address or URL text for a five-digit code starting with 28 (Madrid's postal prefix). If no match is found, the function falls back to a `ZONE_TO_POSTAL` dictionary that maps 131 barrio names to their primary postal codes (28001 through 28055). This hybrid approach maximizes coverage: regex catches codes embedded in addresses, while the dictionary handles cases where only the barrio name is known.

## Ingestion and deduplication

The `ingest_listings()` function receives parsed listings from any scraper and loads them into the deals table through a PostgreSQL upsert operation.

**Data quality filters.** Before upserting, each listing must pass four validation checks: it must have a URL, an asking price, a size in square meters, and a canonical Madrid district (returned by `normalize_district()`). Listings missing any of these fields are silently skipped. This filter ensures that only queryable, analyzable data enters the database.

**Upsert strategy.** The URL column has a unique constraint. When a listing URL already exists in the database, the `ON CONFLICT DO UPDATE` clause applies two different strategies depending on the field:

- **COALESCE fields** (size_sqm, bedrooms, bathrooms, floor, district, zone, address, condition, orientation, broker_name, broker_contact, listed_date, property_type, postal_code): the new value is used only if it is not null; otherwise the existing value is preserved. This prevents a re-scrape from overwriting previously captured data with null values.
- **OVERWRITE fields** (asking_price, storage_room, terrace, balcony, elevator, garage): the latest scraped value always replaces the existing one. Price updates should always reflect the current listing price, and amenity booleans from a more detailed source should override defaults.

In practice, this means data quality only goes up with each scrape cycle. New non-null values fill gaps, but existing good data is never overwritten with blanks.

## Automated ML prediction on ingest

After each scrape batch, the `_auto_predict_new_deals()` function runs ML predictions on newly inserted deals (those that did not previously exist in the database). Predictions are stored in the predictions table with `model_version="auto"` to distinguish them from manually triggered batch predictions.

This step is wrapped in a try/except block so that ML failures, such as a missing model artifact or an incompatible feature column, never prevent the scraping operation from completing. The scraper returns the count of genuinely new rows inserted, excluding updates to existing records.

## Notary data collection

Official closing price data is collected from the Colegio General del Notariado through its ArcGIS FeatureServer REST API. The API exposes transaction statistics at multiple geographic levels; this system queries Layer 4, which provides postal code-level granularity.

The scraper constructs queries with two filter dimensions:

| Filter | ID Values | Meaning |
|---|---|---|
| tipo_construccion_id | 7, 9, 99 | Nueva (new), Segunda mano (second-hand), Todos (all) |
| clase_finca_urbana_id | 14, 15, 99 | Pisos (apartments), Casas (houses), Todos (all) |

*Table 8.* Notary filter combinations (3 x 3 = 9 total).

The system scrapes all nine combinations for postal codes 28001 through 28055 (55 postal codes), yielding up to 495 records. Each record contains: average price per square meter at closing, average total transaction price, average property surface area, number of transactions with price data, and total number of transactions.

Records are upserted using a composite unique key of (postal_code, construction_type, property_class). On conflict, the price and transaction statistics are updated while preserving the record identity.

```
                    ┌──────────────────────┐
                    │   5 Portal Scrapers  │
                    │ (API, JSON, Firecrawl)│
                    └──────────┬───────────┘
                               │ raw listings
                               ▼
                    ┌──────────────────────┐
                    │ normalize_district() │
                    │ extract_postal_code()│
                    │ normalize_condition()│
                    └──────────┬───────────┘
                               │ canonical fields
                               ▼
                    ┌──────────────────────┐
                    │  Quality Filters     │
                    │ require: url, price, │
                    │ size_sqm, district   │
                    └──────────┬───────────┘
                               │ validated listings
                               ▼
                    ┌──────────────────────┐
                    │ ingest_listings()    │
                    │ URL-based upsert     │
                    │ COALESCE + OVERWRITE │
                    └──────────┬───────────┘
                               │ new deals
                               ▼
                    ┌──────────────────────┐
                    │ _auto_predict_new    │
                    │ _deals()             │
                    │ model_version="auto" │
                    └──────────────────────┘
```

*Figure 5.* Data collection pipeline flow.

# Machine learning valuation model

## Problem formulation

The valuation model is a supervised regression task: given a set of physical and locational features of a property, predict its market price. The target variable is the asking price as listed on the portal. While asking prices do not represent actual transaction values (as discussed in the Notary Data section), they provide the most abundant and consistent label available across all five data sources.

To handle the right-skewed distribution of property prices, the target is log-transformed during training using `y = log(1 + price)`. This transformation compresses the range of the target variable, giving the model proportional rather than absolute error incentives. At inference time, predictions are reversed with `price = exp(y_pred) - 1`.

## Feature engineering

The `deal_to_features()` function converts a database Deal object into a feature dictionary suitable for model input. The features fall into three categories:

| Feature | Type | Encoding | Source Field |
|---|---|---|---|
| Metros Cuadrados | Numeric | Direct | size_sqm |
| Numero de Habitaciones | Numeric | Direct (default 0) | bedrooms |
| Numero de Banos | Numeric | Direct (default 0) | bathrooms |
| Planta | Numeric | Direct (default 0) | floor |
| Trastero | Binary | 0/1 | storage_room |
| Terraza | Binary | 0/1 | terrace |
| Balcon | Binary | 0/1 | balcony |
| Ascensor | Binary | 0/1 | elevator |
| Garaje | Binary | 0/1 | garage |
| Distrito | Categorical | One-hot | district |
| Zona | Categorical | One-hot | zone |
| Estado | Categorical | One-hot | condition |
| Ubicacion | Categorical | One-hot | orientation |

*Table 9.* Feature summary.

No price-derived features are included in the feature set. Using the asking price or price per square meter as a feature would constitute data leakage, since the model's target is the price itself. The model must learn price solely from physical characteristics and location.

Missing numeric values default to zero. Missing categorical values default to empty strings, which are then one-hot encoded as their own category. Binary amenity fields convert Python booleans to integer 0 or 1 values.

## Data preprocessing

Before training, the dataset undergoes several preprocessing steps:

1. **Filtering.** Deals must have both a non-null asking price and a non-null size in square meters. Deals with a price per square meter below 500 or above 25,000 euros are also excluded as outliers. These thresholds remove data entry errors (listings with placeholder prices) and extreme luxury properties that would distort the model. A minimum of 50 deals is required to proceed with training; below that, the training function returns `None`.

2. **One-hot encoding.** Categorical features (Distrito, Zona, Estado, Ubicacion) are expanded into binary columns using `pd.get_dummies()`. With 21 districts, this step can produce a substantial number of columns. The column names are saved as a model artifact so that inference can align new data to the training schema.

3. **Train-test split.** The dataset is split 85/15 into training and test sets with `random_state=42` for reproducibility.

4. **Feature scaling.** A `StandardScaler` is fitted on the training set and applied to both training and test sets. The fitted scaler is saved as an artifact for use during inference.

## Model selection and hyperparameters

The system uses scikit-learn's `GradientBoostingRegressor` with the following hyperparameters:

| Hyperparameter | Value | Rationale |
|---|---|---|
| n_estimators | 300 | Sufficient ensemble complexity for a dataset of ~3,000 deals without excessive training time |
| max_depth | 5 | Limits individual tree complexity, preventing overfitting to small district-level samples |
| learning_rate | 0.05 | Conservative shrinkage factor; lower values require more estimators but produce smoother convergence |
| subsample | 0.8 | Stochastic gradient boosting: each tree trains on 80% of the data, reducing variance |
| random_state | 42 | Reproducibility |

*Table 10.* Model hyperparameters.

Gradient Boosting was chosen over the alternatives after testing. Linear regression cannot capture the non-linear relationship between location and price. Random forests perform reasonably but miss the sequential error correction that boosting provides. Neural networks need more data than 3,000 records to train well and give less interpretable feature importances. Gradient boosting works with mixed feature types out of the box, tolerates outliers when paired with the log-transform, and produces feature importance scores that help explain what the model is doing.

## Training pipeline

The training pipeline executes the following steps:

1. Query all deals from the database and convert each to a feature dictionary using `deal_to_features()`.
2. Create a pandas DataFrame and apply the data quality filters (non-null price/size, outlier exclusion).
3. One-hot encode categorical features with `pd.get_dummies()`.
4. Log-transform the target: `y = np.log1p(asking_price)`.
5. Split into 85% training and 15% test sets.
6. Fit a `StandardScaler` on the training features and transform both sets.
7. Train the `GradientBoostingRegressor` on the scaled training data.
8. Evaluate on the test set (reversing the log-transform for interpretable metrics).
9. Run five-fold cross-validation on the full scaled dataset, reporting R-squared mean and standard deviation.
10. Save three artifacts with timestamps: the trained model, the fitted scaler, and the column name list. Also save copies without timestamps as the "current" versions for inference.

Cache invalidation is handled by the `POST /ml/retrain` endpoint, which clears the `@lru_cache` decorators on the model, scaler, and column loaders. This forces the next prediction request to load the freshly trained artifacts from disk.

## Model evaluation

The model was trained on the production dataset of 3,190 deals (after outlier filtering from 3,195 total).

| Metric | Value | Interpretation |
|---|---|---|
| R-squared (test set) | 0.866 | The model explains 86.6% of price variance on unseen data |
| R-squared (5-fold CV mean) | 0.886 | Stable generalization across all partitions of the dataset |
| R-squared (5-fold CV std) | 0.024 | Low variance across folds, indicating consistent performance |
| MAE (test set) | 166,080 EUR | Average prediction error of approximately 166,000 euros |

*Table 11.* Model evaluation metrics.

An R-squared of 0.87 on the test set means the model captures most of the price variation from physical and locational features alone. The cross-validation R-squared of 0.89 with a standard deviation of 0.024 confirms this is not a lucky split; the model generalizes consistently across all five folds.

The MAE of 166,080 euros needs context. The typical property in the dataset is priced somewhere between 300,000 and 800,000 euros (given the median price per square meter of 5,375 euros). An error of 166,000 euros is roughly 20 to 30 percent of the typical property value. That makes the model useful for screening and ranking, less so for setting a final price. Final valuations should still involve market comparables and professional judgment.

[FIGURE PLACEHOLDER: *Figure 6.* Distribution of asking prices before and after log transformation. Two side-by-side histograms showing the right-skewed raw distribution and the more symmetric log-transformed distribution.]

[FIGURE PLACEHOLDER: *Figure 7.* Predicted vs. actual price scatter plot on the test set. Points should cluster along the diagonal; deviations from the diagonal represent prediction errors.]

[FIGURE PLACEHOLDER: *Figure 8.* Feature importance bar chart showing the top 15 features by importance score from the Gradient Boosting model. District and size features are expected to dominate.]

## Model deployment and inference

At inference time, the `predict_price_from_features()` function follows these steps:

1. Accept a feature dictionary with the same keys used during training.
2. Create a single-row DataFrame and apply one-hot encoding with `pd.get_dummies()`.
3. Align columns with the training schema using `df.reindex(columns=saved_columns, fill_value=0)`. This ensures that districts or zones not seen during training receive zero-valued columns rather than causing a dimension mismatch.
4. Apply the cached StandardScaler.
5. Predict the log-price using the cached model.
6. Reverse the log-transform: `price = np.expm1(y_pred_log[0])`.

The model artifacts (model, scaler, column list) are loaded once and cached in memory using `@lru_cache`. Subsequent predictions reuse the cached objects, eliminating disk I/O. The cache is invalidated only when the model is retrained through the `/ml/retrain` endpoint.

Two inference modes are supported:
- **Manual batch prediction.** The user selects deals on the Valuaciones page and triggers `POST /deals/predict` with a list of deal IDs. The backend iterates through each deal, converts it to features, runs inference, and stores the prediction.
- **Automatic prediction on scrape.** After each scrape batch, newly inserted deals receive predictions automatically with `model_version="auto"`.

```
Training:                          Inference:
┌──────────┐                       ┌──────────┐
│ deals DB │                       │ deal obj │
└────┬─────┘                       └────┬─────┘
     │ deal_to_features()               │ deal_to_features()
     ▼                                  ▼
┌──────────┐                       ┌──────────┐
│ DataFrame│                       │ DataFrame│
│ + dummies│                       │ + dummies│
└────┬─────┘                       └────┬─────┘
     │ log1p(price)                     │ reindex(cols)
     ▼                                  ▼
┌──────────┐                       ┌──────────┐
│ Split    │                       │ Scale    │
│ 85/15    │                       │ (cached) │
└────┬─────┘                       └────┬─────┘
     │ StandardScaler.fit()             │ model.predict()
     ▼                                  ▼
┌──────────┐                       ┌──────────┐
│ GB.fit() │                       │ expm1()  │
└────┬─────┘                       └────┬─────┘
     │ save .pkl                        │ predicted
     ▼                                  ▼ price (EUR)
┌──────────┐
│ CV(5-fold│
│ evaluate │
└──────────┘
```

*Figure 9.* ML pipeline: training (left) and inference (right).

# Financial analysis model

## Fix and Flip strategy overview

The Fix and Flip strategy targets properties listed in conditions described as "a reformar" (needing renovation). The investor purchases the property at a discount, renovates it to "buen estado" (good condition), and sells at a higher price that reflects the improved state. In Madrid, this strategy is viable because a significant portion of the housing stock is older construction in need of updates, and the price gap between "a reformar" and "buen estado" properties in the same district can be substantial.

The financial model implemented in CapReSol computes investment returns from the equity investor's perspective, accounting for leverage, interest costs, operating expenses, and taxes. All cash flows are modeled at monthly granularity.

## Model inputs

| Input | Unit | Default | Description |
|---|---|---|---|
| size_sqm | m2 | — | Property surface area |
| purchase_price | EUR | — | Total acquisition cost |
| exit_price_per_sqm | EUR/m2 | — | Expected post-renovation price per square meter |
| capex_total | EUR | — | Total renovation budget |
| capex_months | months | — | Duration of renovation works |
| project_months | months | — | Total hold period from purchase to sale |
| monthly_opex | EUR/month | — | Recurring costs (utilities, community fees) |
| ibi_annual | EUR/year | — | Annual property tax (Impuesto sobre Bienes Inmuebles) |
| closing_costs_pct | % | 7.5% | Transaction costs at purchase (ITP, notary, registry, lawyers) |
| broker_fee_pct | % | 3.63% | Exit broker commission including VAT |
| mortgage_ltv | % | 0% | Loan-to-value ratio for acquisition mortgage |
| mortgage_rate_annual | % | 0% | Annual interest rate on acquisition mortgage |
| capex_debt | EUR | 0 | Debt financing for renovation |
| capex_debt_rate_annual | % | 0% | Annual interest rate on renovation debt |
| tax_rate | % | 0% | Tax rate on profits |

*Table 12.* Fix and Flip model inputs.

## Cash flow construction

Cash flows are constructed from the equity investor's perspective, where negative values represent outflows and positive values represent inflows:

**Month 0 (Purchase):**
```
cash_flow_0 = -(equity_at_purchase + closing_costs)

where:
  mortgage_debt = purchase_price * mortgage_ltv
  equity_at_purchase = purchase_price - mortgage_debt
  closing_costs = purchase_price * closing_costs_pct
```

**Months 1 through capex_months (Renovation):**
```
cash_flow_m = -capex_equity_monthly - monthly_opex - ibi_monthly
              - mortgage_interest_monthly - capex_interest_monthly

where:
  capex_equity = capex_total - capex_debt
  capex_equity_monthly = capex_equity / capex_months
  ibi_monthly = ibi_annual / 12
  mortgage_interest_monthly = mortgage_debt * (mortgage_rate / 12)
  capex_interest_monthly = capex_debt * (capex_debt_rate / 12)
```

**Months capex_months+1 through project_months-1 (Holding):**
```
cash_flow_m = -monthly_opex - ibi_monthly
              - mortgage_interest_monthly - capex_interest_monthly
```

**Month project_months (Exit):**
```
cash_flow_exit = (above monthly costs)
                 + net_exit_price - total_debt_repayment

where:
  gross_exit_price = exit_price_per_sqm * size_sqm
  broker_fee = gross_exit_price * broker_fee_pct
  net_exit_price = gross_exit_price - broker_fee
  total_debt_repayment = mortgage_debt + capex_debt
```

All debt is modeled as interest-only during the holding period, with full principal repayment at exit. This reflects common short-term financing structures for flip projects.

## Output metrics

The model computes four primary return metrics and several supporting figures:

**IRR (Internal Rate of Return).** Computed from the monthly cash flow array using `numpy_financial.irr()`, then annualized: `annual_IRR = (1 + monthly_IRR)^12 - 1`. IRR represents the annualized return that makes the net present value of all cash flows equal to zero.

**MOIC (Multiple on Invested Capital).** `MOIC = (max_equity_exposure + profit) / max_equity_exposure`. A MOIC of 1.5x means the investor receives 1.5 euros for every euro of peak equity deployed.

**ROE (Return on Equity).** `ROE = profit / max_equity_exposure`. Measures profit as a percentage of the maximum capital at risk.

**Gross Margin.** `gross_margin = profit / total_dev_cost`. Measures profit as a percentage of total development cost, useful for comparing projects of different scales.

**Max Equity Exposure.** The peak negative cumulative cash flow during the project, representing the maximum capital the equity investor has tied up at any point. This is the denominator for MOIC and ROE, and it is more meaningful than initial equity deployed because ongoing renovation and operating costs increase total capital at risk during the project.

## Leverage effects

Leverage amplifies returns when a deal is profitable and amplifies losses when it is not. By financing a portion of the purchase price with a mortgage, the investor reduces their equity contribution at Month 0. This lower denominator increases IRR, ROE, and MOIC for profitable deals. However, interest payments during the holding period reduce absolute profit.

The model supports two independent debt instruments: an acquisition mortgage (applied as a percentage of purchase price via LTV) and capex debt (a fixed amount for renovation financing). Each has its own interest rate. This dual-debt structure reflects real market conditions where acquisition and renovation financing often come from different sources with different terms.

# Analytics dashboard

## Design philosophy

The analytics dashboard is built around one question: where should the next investment be? Instead of showing raw market statistics, every section is designed to compare data sources against each other and surface actionable opportunities.

Three layers of upside comparison form the analytical backbone:

1. **Conservative upside:** Compare portal asking prices for "a reformar" properties against notary closing prices for "nueva" (new) properties. This estimates the potential gain from buying a renovation candidate at asking price and selling at the price the market actually pays for new properties.
2. **Optimistic upside:** Compare portal asking prices for "a reformar" against portal asking prices for "buen estado" properties. This shows the price gap between renovation candidates and finished properties, though asking prices may overstate the actual achievable price.
3. **Market ceiling:** Compare notary closing prices for "segunda mano" (second-hand) against "nueva" (new) properties. Both figures are real transaction data, showing the structural price difference between property types in each district.

## Analytics architecture

The analytics endpoint (`GET /analytics`) returns 13 data structures in a single response. All aggregation and computation happens on the backend; the frontend only renders the results. This design avoids sending raw deal data to the client and ensures that filtering logic is consistent.

Four query parameters control the analysis:
- `max_price_sqm` (default 25,000) and `min_price_sqm` (default 500): exclude outlier deals from aggregations
- `notary_construction` (default "segunda_mano"): filter notary data by construction type
- `notary_class` (default "pisos"): filter notary data by property class (apartments vs. houses)

A critical data join bridges the notary data (indexed by postal code) with the deal data (indexed by district). The system maps each notary postal code to its corresponding district, then aggregates notary statistics at the district level weighted by transaction count to produce accurate district-level averages.

## Dashboard sections

The dashboard displays ten sections in the following order:

**Section 1: KPI Strip.** Four summary cards: total listings in the dataset, count of "a reformar" listings, the district with the highest upside, and the most affordable district by price per square meter.

**Section 2: Oportunidad Real por Distrito (Conservative Upside).** A table comparing the average asking price per square meter of "a reformar" listings from portals against the average closing price per square meter of "nueva" properties from notary data, for each district. The upside is computed as `(closing_nueva - asking_reformar) / asking_reformar * 100`. Districts with positive upside are shown, sorted by upside descending. The top three are highlighted. Each row includes a clickable link to the deals page filtered by that district and "a reformar" condition.

**Section 3: Upside en Portales (Optimistic Upside).** Same structure as Section 2, but comparing "a reformar" asking prices against "buen estado" asking prices, both from portal data. This provides a more optimistic estimate because asking prices for "buen estado" may be higher than actual closing prices.

**Section 4: Upside del Mercado (Market Ceiling).** Notary closing prices for "segunda mano" versus "nueva" properties, both from official transaction data. This section shows the structural price ceiling in each district, without an actionable link because these are aggregate market statistics rather than specific deal opportunities.

**Section 5: Margen de Negociacion por Distrito (Negotiation Margin).** Compares portal asking prices against notary closing prices per district, showing the percentage gap. A dropdown filter allows switching between all properties, second-hand only, or new construction only. Color coding indicates the negotiation room: above 15% in red (significant overpricing), 5-15% in yellow (moderate), below 5% in green (tight market).

**Section 6: Valoracion ML vs Precio Pedido (ML Spread).** Shows the average percentage difference between ML-predicted prices and asking prices per district. Green highlighting (spread above 5%) indicates districts where the model suggests properties are undervalued relative to asking prices. Red (negative spread) indicates potential overvaluation.

**Section 7: Estado de la Propiedad (Condition Distribution).** A pie chart showing the proportion of listings in each condition category: "a reformar," "buen estado," and "nueva." This gives context on the available opportunity pool for renovation strategies.

**Section 8: Nuevos Listings por Mes (Timeline).** A line chart of new listings over time, grouped by the portal's listed date rather than the system's ingestion date. This shows market activity trends and listing velocity.

**Section 9: Cartera Analizada (Portfolio Summary).** KPI cards aggregating metrics from all saved financial analyses: count, average IRR, average MOIC, and average ROE. This section only appears when at least one analysis exists.

**Section 10: Mostrar Mas (Expanded Analysis).** A collapsible section containing supplementary charts: a horizontal bar chart of price per square meter by district (sorted descending with a market average reference line), price and size distribution histograms, bedroom count distribution, and amenity prevalence bars showing the percentage of listings with elevator, terrace, balcony, garage, and storage room.

[SCREENSHOT PLACEHOLDER: *Figure 11.* Analytics dashboard overview showing the KPI strip and conservative upside chart.]

[SCREENSHOT PLACEHOLDER: *Figure 12.* Negotiation margin table with color-coded spread percentages.]

## Opportunity scoring

The analytics endpoint computes a composite opportunity score for each district by ranking on three dimensions:

1. **Price rank:** Districts sorted by average price per square meter ascending (cheapest entry point = best rank)
2. **Reform upside rank:** Districts sorted by reform upside descending (biggest renovation gap = best rank)
3. **ML spread rank:** Districts sorted by ML-vs-asking spread descending (most undervalued by model = best rank)

Each rank is converted to a 1-10 scale, and the three scores are averaged. The opportunity table is sorted by composite score ascending, so the lowest score represents the most attractive investment opportunity.

# Results and discussion

## Data collection results

The production system contains 3,195 property listings across all 21 administrative districts of Madrid.

| District | Listings | % of Total |
|---|---|---|
| Centro | 545 | 17.1% |
| Salamanca | 381 | 11.9% |
| Carabanchel | 213 | 6.7% |
| Chamberí | 193 | 6.0% |
| Puente de Vallecas | 171 | 5.4% |
| Ciudad Lineal | 169 | 5.3% |
| Tetuán | 165 | 5.2% |
| Latina | 160 | 5.0% |
| Retiro | 136 | 4.3% |
| Fuencarral-El Pardo | 135 | 4.2% |
| Chamartín | 122 | 3.8% |
| Moncloa-Aravaca | 111 | 3.5% |
| San Blas-Canillejas | 104 | 3.3% |
| Arganzuela | 100 | 3.1% |
| Hortaleza | 99 | 3.1% |
| Usera | 96 | 3.0% |
| Villaverde | 92 | 2.9% |
| Villa de Vallecas | 84 | 2.6% |
| Vicálvaro | 68 | 2.1% |
| Moratalaz | 30 | 0.9% |
| Barajas | 21 | 0.7% |

*Table 13.* Dataset distribution by district.

Centro and Salamanca together account for 29 percent of all listings, which tracks with their status as Madrid's most active residential markets. Peripheral districts like Moratalaz, Barajas, and Vicálvaro have the fewest listings, likely due to lower market activity and sparser portal coverage.

By source, Idealista contributed 1,857 listings (58.1%), Redpiso 782 (24.5%), Fotocasa 291 (9.1%), and Pisos.com 265 (8.3%). Idealista's large share makes sense: it is Spain's largest property portal, and both the API and HTML scraping channels feed into the count.

Of the 3,195 listings, 1,240 (38.8%) are classified as "buen estado," 290 (9.1%) as "a reformar," and 86 (2.7%) as "nueva." The remaining 1,579 (49.4%) have no condition data at all. This is mostly because Redpiso does not provide condition information, and the Firecrawl-based scrapers only detect condition when specific keywords appear in the listing text.

**Field completeness:**

| Field | Coverage |
|---|---|
| size_sqm | 100.0% |
| district | 100.0% |
| bedrooms | 98.7% |
| bathrooms | 92.5% |
| zone | 75.7% |
| floor | 58.7% |
| condition | 50.6% |
| postal_code | 75.7% |
| orientation | 11.4% |

*Table 14.* Field completeness across the dataset.

Size and district have perfect coverage because they are required by the data quality filter. Bedrooms and bathrooms are well covered. Floor, condition, postal code, and orientation have lower coverage, primarily because not all portals provide these fields in a format that can be reliably parsed.

The average asking price per square meter across the dataset is 8,450 euros, with a median of 5,375 euros. The gap between mean and median is typical of real estate: a handful of luxury listings in Salamanca and Chamberí pull the average up while most properties cluster at lower price points.

## Machine learning results

The Gradient Boosting model was trained on 3,190 listings (after outlier filtering) and evaluated on a held-out test set and through five-fold cross-validation.

| Metric | Value |
|---|---|
| R-squared (test) | 0.866 |
| R-squared (5-fold CV mean) | 0.886 |
| R-squared (5-fold CV std) | 0.024 |
| MAE (test) | 166,080 EUR |
| Model version | gb_20260320_104153 |
| Deals trained | 3,190 |

*Table 15.* Machine learning evaluation results.

The model explains 86.6 percent of price variance on held-out data. Cross-validation confirms this is not an artifact of a favorable train-test split: the five-fold CV mean of 0.886 with a standard deviation of 0.024 indicates stable generalization.

The MAE of 166,080 euros is substantial in absolute terms. For a property listed at 500,000 euros, this represents a 33 percent error. For a property listed at 1,000,000 euros, it represents 17 percent. This level of accuracy makes the model suitable for screening and ranking but not for final pricing decisions. Several factors explain the error magnitude:

- **Dataset size.** At 3,190 listings, the dataset is modest compared to institutional AVMs that train on millions of transactions. More data, particularly from additional scraping cycles, would likely improve performance.
- **Feature sparsity.** Nearly half the listings lack condition data, and only 12 percent have postal codes. Condition and precise location are among the strongest price determinants in real estate.
- **Asking vs. transaction prices.** The model is trained on asking prices, which include the seller's negotiation buffer. Two properties with similar features but different sellers may have different asking prices for the same underlying market value.

[FIGURE PLACEHOLDER: *Figure 14.* Predicted vs. actual scatter plot showing model accuracy across the price range.]

[FIGURE PLACEHOLDER: *Figure 15.* Feature importance chart from the Gradient Boosting model, showing the relative contribution of each feature to predictions.]

## Financial analysis results

The Fix and Flip financial model has been implemented and tested with sample scenarios. Below is a worked example for a typical Madrid renovation project:

| Input | Value |
|---|---|
| Size | 80 m2 |
| Purchase price | 240,000 EUR (3,000 EUR/m2) |
| Renovation budget | 40,000 EUR (500 EUR/m2) |
| Renovation duration | 4 months |
| Total project | 8 months |
| Exit price | 4,500 EUR/m2 |
| Monthly opex | 200 EUR |
| IBI annual | 800 EUR |
| Closing costs | 7.5% |
| Broker fee | 3.63% |
| Mortgage LTV | 60% |
| Mortgage rate | 6.7% annual |
| Tax rate | 19% |

In this scenario, the investor purchases an 80 square meter apartment in "a reformar" condition at 3,000 EUR/m2, renovates it for 500 EUR/m2, and sells at 4,500 EUR/m2. With 60 percent leverage, the equity required at purchase drops to 96,000 euros plus 18,000 euros in closing costs. The gross exit price is 360,000 euros, from which the broker fee of 13,068 euros is subtracted. After repaying the mortgage debt of 144,000 euros, the net proceeds flow to the equity investor.

The model outputs the monthly cash flow array and computes the annualized IRR, MOIC, ROE, and gross margin from the equity investor's perspective.

## Analytics insights

The analytics dashboard, when populated with both portal and notary data, provides several forms of market intelligence:

Comparing portal asking prices against notary closing prices reveals the typical discount from asking to closing in each district. Districts with larger spreads have more room for negotiation. Districts with tight spreads are competitive markets where asking prices already reflect what buyers pay.

The condition distribution shows that 9.1 percent of listings are explicitly classified as "a reformar." Combined with the 49.4 percent where condition is unknown, there may be a much larger pool of renovation opportunities than the data currently captures. Better condition detection in the scraping layer would improve the precision of the upside calculations.

The ML spread analysis identifies districts where the model consistently predicts higher prices than sellers are asking. These signals may indicate systematic underpricing, motivated sellers, or market inefficiencies worth investigating.

## Professional feedback

[PLACEHOLDER: The following section should contain feedback from five real estate professionals (from Argentina and Spain) who reviewed the CapReSol system.]

**Methodology.** Five professionals with experience in real estate investment, brokerage, and fund management were given access to the production system and asked to evaluate its utility for their daily workflows. Their feedback was collected through [structured interviews / written questionnaires / live demos with follow-up questions].

**Participant Profiles:**

| # | Role | Location | Experience |
|---|---|---|---|
| 1 | [PLACEHOLDER] | [PLACEHOLDER] | [PLACEHOLDER] |
| 2 | [PLACEHOLDER] | [PLACEHOLDER] | [PLACEHOLDER] |
| 3 | [PLACEHOLDER] | [PLACEHOLDER] | [PLACEHOLDER] |
| 4 | [PLACEHOLDER] | [PLACEHOLDER] | [PLACEHOLDER] |
| 5 | [PLACEHOLDER] | [PLACEHOLDER] | [PLACEHOLDER] |

*Table 16.* Professional feedback participants.

**Key Findings:**

[PLACEHOLDER: Summarize the main themes from professional feedback. Expected areas: data consolidation value, ML prediction utility, financial model usefulness, analytics dashboard insights, missing features, suggestions for improvement.]

## Discussion

The results support the thesis that a unified platform can address the three identified inefficiencies.

On data fragmentation: the system collects and normalizes listings from five sources into a single dataset of over 3,000 listings across all 21 Madrid districts. The URL-based deduplication and the COALESCE/OVERWRITE upsert logic mean data quality improves with each scraping cycle without duplicates or lost data.

On valuation opacity: the ML model's R-squared of 0.87 shows that property characteristics and location explain most of the price variation. The MAE of 166,000 euros is too large for final pricing decisions, but it gives a systematic, reproducible baseline for screening deals at scale, which is better than relying on intuition alone.

On the analytical gap: having ML predictions, notary closing prices, and Fix and Flip financial analysis in one dashboard means an analyst can go from deal identification to investment decision without switching tools. The opportunity scoring algorithm condenses multiple signals into a single district ranking, which cuts down on the mental work of cross-referencing separate spreadsheets.

That said, the system has clear limitations. The dataset covers all 21 districts but is modest in size. Half the listings lack condition data, which limits renovation-based analysis. The notary data is a single snapshot with no historical trend. The ML model has not been benchmarked against commercial AVMs. Geographic scope stops at Madrid city proper. And the Cap Rate model for rental strategies was not implemented.

# Conclusions and future work

## Summary of contributions

CapReSol is a production web application that automates the real estate investment analysis pipeline for Madrid. It delivers six capabilities:

1. **Multi-source data collection.** Five scrapers collect listings from Idealista (API and HTML), Redpiso, Fotocasa, and Pisos.com, normalizing them into a unified schema with 21 canonical districts and 55 postal codes. The production dataset contains 3,195 listings.

2. **Machine learning valuation.** A Gradient Boosting model trained on 3,190 listings achieves R-squared of 0.87 on held-out data and 0.89 on five-fold cross-validation, with automatic prediction on new listings at scrape time.

3. **Notary data integration.** Official closing prices from the Colegio General del Notariado cover 55 postal codes across nine filter combinations, enabling comparison of asking prices against real transaction values.

4. **Financial modeling.** A Fix and Flip model computes IRR, MOIC, ROE, and gross margin from monthly equity cash flows with dual-debt leverage support, ported from a reference Excel model to Python.

5. **Analytics dashboard.** Ten chart sections surface investment opportunities through three upside comparisons, negotiation margin analysis, ML spread detection, and a composite opportunity scoring algorithm.

6. **Production deployment.** JWT-authenticated multi-user access on Railway (backend) and Vercel (frontend) with auto-deployment from GitHub.

In terms of efficiency: data collection that would take an analyst hours per portal now runs in minutes. Valuation that relied on gut feeling and manual comparables gets supplemented by a reproducible ML model. Financial analysis that lived in separate Excel files is now integrated with the deal database. None of these replace professional judgment, but they reduce the manual work required to get to a judgment.

## Answering the research objectives

| Objective | Status | Evidence |
|---|---|---|
| O1: Multi-source scraping | Achieved | 3,195 deals from 5 sources, 21 districts |
| O2: ML valuation | Achieved | R-squared 0.87 test, 0.89 CV, auto-predict on scrape |
| O3: Notary integration | Achieved | 55 postal codes, 9 filter combinations, ArcGIS API |
| O4: Financial modeling | Achieved | Fix and Flip with IRR, MOIC, ROE, leverage support |
| O5: Analytics dashboard | Achieved | 10 sections, 3 upside charts, opportunity scoring |
| O6: Production deployment | Achieved | Railway + Vercel, JWT auth, 6 users, auto-deploy |

*Table 17.* Objective achievement summary.

All six objectives were fully implemented and deployed in production. The Cap Rate financial model, originally planned as part of Objective 4, was not implemented within the scope of this thesis and remains as future work.

## Limitations

- The dataset of 3,195 listings, while covering all districts, is small compared to institutional datasets. More scraping cycles would increase both coverage and ML accuracy.
- Condition data is available for only 50.6 percent of listings, limiting renovation-based analysis.
- Notary data represents a single time period. Historical time-series data would enable trend analysis.
- The ML model has not been benchmarked against commercial AVMs in the Spanish market.
- Geographic scope is limited to Madrid city proper. Expansion to metropolitan areas or other cities would require additional district mappings and postal code ranges.
- The Cap Rate / rental yield financial model was not implemented.

## Future work

**Short-term improvements:**
- Add a "Retrain Model" button in the frontend (the backend endpoint already exists).
- Implement barrio-level breakdown in the analytics dashboard, expandable from the district view.
- Build a deal detail page (`/deals/[id]`) with a property card, ML prediction history, and linked financial analyses.
- Improve condition detection in the Firecrawl scrapers to reduce the 49 percent unknown rate.

**Medium-term extensions:**
- Implement the Cap Rate / rental yield financial model for buy-and-hold strategies.
- Add scheduled scraping via cron jobs for automated data refresh without manual intervention.
- Integrate time-series notary data if the penotariado API supports historical period queries.
- Export analytics to PDF or Excel for reporting to investment committees.
- Enable natural language search on the home page, parsing text queries into filter parameters.

**Long-term evolution:**
- **B2B vertical.** Position the platform as a SaaS tool for investment funds, asset managers, and family offices. Deepen the technology with fund-level portfolio analytics, deal flow management, and integration with CRM systems.
- **B2C horizontal.** Offer a simplified version for retail investors who lack infrastructure for systematic deal analysis. A freemium model with tiered access could build a user base while generating data that attracts real estate agencies interested in platform visibility and user insights.
- **Geographic expansion.** Extend coverage to Barcelona, Valencia, Malaga, and other Spanish cities. Each expansion requires new district-barrio mappings, postal code ranges, and potentially different portal configurations.

## Final remarks

The real estate technology market has moved past the adoption phase. Most firms have tools; the problem is that those tools do not talk to each other. CapReSol shows that it is possible to build a complete pipeline, from raw portal data to financial decision metrics, in a single application. It does not replace the work of evaluating a deal. It replaces the busywork that gets in the way of evaluating a deal.

#

#

# References

Baldominos, A., Saez, Y., & Quintana, D. (2018). Machine learning techniques for predicting housing prices: A review. *Advances in Intelligent Systems and Computing*, 584, 123-132.

BBVA Research. (2024). Spain housing market outlook 2024. BBVA Research Publications.

CBRE. (2024). Real estate investment market Spain 2024 report. CBRE Research.

European PropTech Report. (2025). PropTech in Europe: Companies, trends, and investment landscape. European PropTech Association.

Kok, N., Kopczuk, W., & Timmins, C. (2017). Big data in real estate: From manual appraisal to automated valuation models. *Journal of Portfolio Management*, 43(6), 202-211.

Maps PropTech API. (2025). PropTech adoption survey Spain 2025: Tech stack, barriers, and automation needs. Maps PropTech API Annual Report.

PwC. (2025). Tendencias del sector de tecnologia inmobiliaria en Espana 2025. PwC Spain Real Estate.

Rosen, S. (1974). Hedonic prices and implicit markets: Product differentiation in pure competition. *Journal of Political Economy*, 82(1), 34-55.

v7 Labs. (2026). AI in real estate: Key use cases, solutions, and challenges. Retrieved from v7labs.com/blog/best-ai-tools-for-real-estate

# Appendix A: API Endpoint Documentation

| Method | Path | Auth | Description |
|---|---|---|---|
| POST | /auth/login | No | Authenticate and receive JWT token |
| GET | /deals/ | Yes | List all property deals |
| POST | /deals/scrape | Yes | Trigger scraping from specified portal |
| POST | /deals/predict | Yes | Run ML predictions on specified deal IDs |
| DELETE | /deals/predictions/{id} | Yes | Delete a specific prediction |
| GET | /analyses/ | Yes | List all financial analyses |
| POST | /analyses/ | Yes | Create new Fix and Flip analysis |
| PUT | /analyses/{id} | Yes | Update existing analysis |
| DELETE | /analyses/{id} | Yes | Delete analysis |
| GET | /analytics | Yes | Get all dashboard analytics data |
| POST | /ml/retrain | Yes | Retrain ML model and return metrics |
| GET | /notary/ | Yes | Query notary statistics |
| POST | /notary/scrape | Yes | Scrape notary data from penotariado |

*Table A1.* API endpoints.

# Appendix B: Database Schema Details

**deals table columns:**

| Column | Type | Nullable | Constraint |
|---|---|---|---|
| id | UUID | No | Primary Key |
| message_id | UUID | Yes | FK → messages.id |
| address | Text | Yes | — |
| city | Text | Yes | — |
| country | Text | Yes | — |
| property_type | Text | Yes | — |
| size_sqm | Float | Yes | — |
| bedrooms | Integer | Yes | — |
| bathrooms | Integer | Yes | — |
| floor | Integer | Yes | — |
| asking_price | Float | Yes | — |
| currency | String(3) | Yes | — |
| url | Text | Yes | UNIQUE |
| broker_name | Text | Yes | — |
| broker_contact | Text | Yes | — |
| district | Text | Yes | — |
| zone | Text | Yes | — |
| condition | Text | Yes | — |
| orientation | Text | Yes | — |
| storage_room | Boolean | Yes | — |
| terrace | Boolean | Yes | — |
| balcony | Boolean | Yes | — |
| elevator | Boolean | Yes | — |
| garage | Boolean | Yes | — |
| listed_date | Date | Yes | — |
| postal_code | String(5) | Yes | — |
| created_at | DateTime | No | Default: now() |

*Table B1.* Deals table schema.

# Appendix C: Madrid District-Barrio Mapping (Sample)

| District | Sample Barrios |
|---|---|
| Centro | Sol, Embajadores, Lavapies, Malasana, Chueca, Huertas, Palacio, Cortes, Universidad |
| Salamanca | Recoletos, Goya, Castellana, Lista, Guindalera |
| Chamberí | Trafalgar, Almagro, Gaztambide, Rios Rosas, Vallehermoso |
| Chamartín | El Viso, Prosperidad, Ciudad Jardin, Hispanoamerica |
| Retiro | Ibiza, Jeronimos, Nino Jesus, Pacífico, Adelfas |
| Arganzuela | Legazpi, Delicias, Palos de Moguer, Chopera, Acacias |
| Tetuán | Bellas Vistas, Cuatro Caminos, Castillejos, Almenara, Valdeacederas |
| Latina | Lucero, Aluche, Campamento, Aguilas, Puerta del Angel |
| Carabanchel | Vista Alegre, Comillas, Opanel, San Isidro, Buenavista |
| Puente de Vallecas | Entrevias, San Diego, Palomeras, Numancia, Portazgo |

*Table C1.* Sample district-barrio mappings (10 of 21 districts).

# Appendix D: Frontend Screenshots

[SCREENSHOT PLACEHOLDER: Home dashboard with quick stats and recent deals]

[SCREENSHOT PLACEHOLDER: Deals page with filters, sorting, and column configuration]

[SCREENSHOT PLACEHOLDER: Valuaciones page showing ML predictions with spread badges]

[SCREENSHOT PLACEHOLDER: Analyses page showing Fix and Flip results with expanded detail row]

[SCREENSHOT PLACEHOLDER: Analytics dashboard — full page overview]

[SCREENSHOT PLACEHOLDER: Login page]
