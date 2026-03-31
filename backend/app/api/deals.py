import uuid
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Response
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.db import models
from app.api.schemas import DealRead, DealCreate, PredictRequest, PredictionRead, PredictionWithDeal
from app.api.auth import get_current_user
from app.services.extraction import create_deal_from_payload
from app.services.portal_scraper import (
    scrape_idealista_api,
    scrape_idealista_html,
    scrape_redpiso_html,
    scrape_fotocasa_firecrawl,
    scrape_pisos_firecrawl,
    ingest_listings,
)
from app.ml.features import deal_to_features
from app.ml.model import predict_price_from_features

router = APIRouter(prefix="/deals", tags=["deals"], dependencies=[Depends(get_current_user)])


# ---------- Existing endpoints ----------

@router.get("/", response_model=List[DealRead])
def list_deals(db: Session = Depends(get_db)):
    return db.query(models.Deal).order_by(models.Deal.created_at.desc()).all()


@router.get("/predictions", response_model=List[PredictionWithDeal])
def list_predictions(db: Session = Depends(get_db)):
    """Return all predictions with their associated deal data, newest first."""
    rows = (
        db.query(models.Prediction, models.Deal)
        .join(models.Deal, models.Prediction.deal_id == models.Deal.id)
        .order_by(models.Prediction.created_at.desc())
        .all()
    )
    result = []
    for pred, deal in rows:
        result.append(PredictionWithDeal(
            id=str(pred.id),
            deal_id=str(pred.deal_id),
            predicted_price=pred.predicted_price,
            model_version=pred.model_version,
            created_at=pred.created_at,
            address=deal.address,
            district=deal.district,
            size_sqm=deal.size_sqm,
            asking_price=deal.asking_price,
            condition=deal.condition,
            url=deal.url,
        ))
    return result


@router.post("/from-message", response_model=DealRead)
def create_deal_from_message(payload: DealCreate, db: Session = Depends(get_db)):
    try:
        deal = create_deal_from_payload(db, payload)
        return deal
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


# ---------- Scraping ----------

class ScrapeParams(BaseModel):
    portal: str = "idealista"           # "idealista", "redpiso", "fotocasa", or "pisos"
    operation: str = "sale"             # "sale" or "rent"
    property_type: str = "homes"        # "homes", "offices", "premises", "garages", "bedrooms"
    max_pages: int = 10                 # each page = 1 API request (50 results). Max 100/month total.
    page_from: int = 1                  # starting page (for chunked Redpiso scraping)
    max_price: Optional[int] = None
    min_price: Optional[int] = None
    bedrooms: Optional[int] = None


class ScrapeResult(BaseModel):
    source: str
    listings_fetched: int
    new_deals_inserted: int


@router.post("/scrape", response_model=ScrapeResult)
def scrape_portal(params: ScrapeParams, db: Session = Depends(get_db)):
    """
    Trigger a scrape of Idealista Madrid listings and store new deals.

    API limits: 100 req/month, 1 req/sec.
    Each page costs 1 request and returns up to 50 listings.
    Set use_html_fallback=true to use the HTML scraper instead (no quota cost).
    """
    if params.portal == "redpiso":
        operation_es = "venta" if params.operation == "sale" else "alquiler"
        listings = scrape_redpiso_html(
            operation=operation_es,
            page_from=params.page_from,
            max_pages=params.max_pages,
        )
        source = "redpiso"
    elif params.portal == "fotocasa":
        operation_fc = "comprar" if params.operation == "sale" else "alquiler"
        listings = scrape_fotocasa_firecrawl(
            operation=operation_fc,
            page_from=params.page_from,
            max_pages=params.max_pages,
        )
        source = "fotocasa"
    elif params.portal == "pisos":
        operation_pisos = "venta" if params.operation == "sale" else "alquiler"
        listings = scrape_pisos_firecrawl(
            operation=operation_pisos,
            page_from=params.page_from,
            max_pages=params.max_pages,
        )
        source = "pisos"
    elif params.portal == "idealista_html":
        listings = scrape_idealista_html(
            page_from=params.page_from,
            max_pages=params.max_pages,
        )
        source = "idealista_html"
    else:
        listings = scrape_idealista_api(
            operation=params.operation,
            property_type=params.property_type,
            max_pages=params.max_pages,
            max_price=params.max_price,
            min_price=params.min_price,
            bedrooms=params.bedrooms,
        )
        source = "idealista_api"

    inserted = ingest_listings(db, listings)

    return ScrapeResult(
        source=source,
        listings_fetched=len(listings),
        new_deals_inserted=inserted,
    )


# ---------- ML Valuation ----------

MODEL_VERSION = "gb_v1"

@router.post("/predict", response_model=List[PredictionRead])
def predict_deals(payload: PredictRequest, db: Session = Depends(get_db)):
    """
    Run ML valuation on one or more deals by ID.
    Returns a predicted price for each. Saves results to predictions table.
    If a prediction already exists for a deal it is overwritten.
    """
    results = []
    for deal_id in payload.deal_ids:
        deal = db.query(models.Deal).filter(models.Deal.id == deal_id).first()
        if not deal:
            raise HTTPException(status_code=404, detail=f"Deal {deal_id} not found")

        features = deal_to_features(deal)
        predicted_price = predict_price_from_features(features)

        # Upsert: replace existing prediction for this deal
        existing = db.query(models.Prediction).filter(models.Prediction.deal_id == deal_id).first()
        if existing:
            existing.predicted_price = predicted_price
            existing.model_version = MODEL_VERSION
            prediction = existing
        else:
            prediction = models.Prediction(
                deal_id=deal_id,
                predicted_price=predicted_price,
                model_version=MODEL_VERSION,
            )
            db.add(prediction)

        db.commit()
        db.refresh(prediction)
        results.append(prediction)

    return results


@router.delete("/predictions/{prediction_id}", status_code=204)
def delete_prediction(prediction_id: uuid.UUID, db: Session = Depends(get_db)):
    obj = db.query(models.Prediction).filter(
        models.Prediction.id == prediction_id
    ).first()
    if not obj:
        raise HTTPException(status_code=404, detail="Prediction not found")
    db.delete(obj)
    db.commit()
    return Response(status_code=204)


# ---------- Postal code backfill ----------

@router.post("/backfill-postal-codes")
def backfill_postal_codes(db: Session = Depends(get_db)):
    """Backfill postal_code for deals that have a zone but no postal_code."""
    from app.services.portal_scraper import ZONE_TO_POSTAL
    import unicodedata
    import re

    def strip_accents(s: str) -> str:
        nfkd = unicodedata.normalize("NFKD", s)
        return "".join(c for c in nfkd if not unicodedata.combining(c))

    # Build accent-insensitive lookup
    lookup = {}
    for name, code in ZONE_TO_POSTAL.items():
        lookup[name.lower()] = code
        lookup[strip_accents(name).lower()] = code

    # Manual overrides for common compound zone names
    manual = {
        "lavapiés-embajadores": "28012", "lavapies-embajadores": "28012",
        "embajadores-lavapiés": "28012", "embajadores-lavapies": "28012",
        "malasaña-universidad": "28015", "malasana-universidad": "28015",
        "universidad-malasaña": "28015", "universidad-malasana": "28015",
        "huertas-cortes": "28014", "cortes-huertas": "28014",
        "chueca-justicia": "28004", "justicia-chueca": "28004",
        "nuevos ministerios-ríos rosas": "28003",
        "nuevos ministerios-rios rosas": "28003",
        "cuzco-castillejos": "28020",
        "bernabéu-hispanoamérica": "28016", "bernabeu-hispanoamerica": "28016",
        "ventilla-almenara": "28029",
        "ensanche de vallecas - la gavia": "28051",
        "ensanche de vallecas-valdecarros": "28051",
        "valdebebas - valdefuentes": "28050", "valdebebas-valdefuentes": "28050",
        "valdebernardo - valderrivas": "28032",
        "campo de las naciones-corralejos": "28042",
        "conde orgaz-piovera": "28016",
        "virgen del cortijo - manoteras": "28043",
        "virgen del cortijo-manoteras": "28043",
        "parque lisboa - la paz": "28034",
        "tres olivos - valverde": "28034",
        "mirasierra-arroyo del fresno": "28034",
        "12 de octubre-orcasur": "28041",
        "manuela malasaña": "28015",
        "centro - ayuntamiento": "28013",
        "centro sur - casco antiguo": "28013",
        "pau de carabanchel": "28025",
        "las tablas": "28050", "sanchinarro": "28050",
        "montecarmelo": "28035", "arroyo del fresno": "28035",
        "peña grande": "28035", "pena grande": "28035",
        "jerónimos": "28014", "jeronimos": "28014",
        "concepción": "28017", "concepcion": "28017",
        "cármenes": "28044", "carmenes": "28044",
        "buena vista": "28047", "buenavista": "28047",
        "palos de moguer": "28045", "palos de la frontera": "28045",
        "río rosas": "28003", "rio rosas": "28003",
        "las águilas": "28044", "las aguilas": "28044",
        "los ángeles": "28041", "los angeles": "28041",
        "la chopera": "28045", "las acacias": "28005",
        "casco histórico": "28013", "casco historico": "28013",
        "casco antiguo": "28013", "salvador": "28022",
        "san andrés": "28021", "san andres": "28021",
        "ambroz": "28032", "los cerros": "28032",
        "los ahijones": "28032", "los berrocales": "28032",
        "valdemarín": "28023", "valdemarin": "28023",
        "sector 3": "28025", "la alhóndiga": "28019",
        "la alhondiga": "28019", "el bercial": "28025",
    }

    district_fallback = {
        "Centro": "28013", "Arganzuela": "28045", "Retiro": "28007",
        "Salamanca": "28001", "Chamartín": "28016", "Tetuán": "28020",
        "Chamberí": "28003", "Fuencarral-El Pardo": "28034",
        "Moncloa-Aravaca": "28008", "Latina": "28044",
        "Carabanchel": "28019", "Usera": "28026",
        "Puente de Vallecas": "28018", "Moratalaz": "28030",
        "Ciudad Lineal": "28017", "Hortaleza": "28043",
        "Villaverde": "28021", "Villa de Vallecas": "28031",
        "Vicálvaro": "28032", "San Blas-Canillejas": "28022",
        "Barajas": "28042",
    }

    deals = db.query(models.Deal).filter(
        models.Deal.postal_code.is_(None),
        models.Deal.zone.isnot(None),
    ).all()

    phase1 = phase2 = phase3 = 0

    for deal in deals:
        z = deal.zone.strip().lower()
        z_na = strip_accents(z)
        postal = None

        # Phase 1: exact match
        if z in lookup:
            postal = lookup[z]
            phase1 += 1
        elif z_na in lookup:
            postal = lookup[z_na]
            phase1 += 1

        # Phase 2: manual overrides + prefix strip + compound split
        if not postal:
            if z in manual or z_na in manual:
                postal = manual.get(z) or manual.get(z_na)
            else:
                for prefix in ("la ", "las ", "los ", "el "):
                    s = z.removeprefix(prefix)
                    if s in lookup:
                        postal = lookup[s]
                        break
                    s_na = strip_accents(s)
                    if s_na in lookup:
                        postal = lookup[s_na]
                        break
            if not postal:
                parts = re.split(r'\s*[-–]\s*', z)
                for part in parts:
                    part = part.strip()
                    if part in lookup:
                        postal = lookup[part]
                        break
                    part_na = strip_accents(part)
                    if part_na in lookup:
                        postal = lookup[part_na]
                        break
                    for prefix in ("la ", "las ", "los ", "el "):
                        s = part.removeprefix(prefix)
                        if s in lookup:
                            postal = lookup[s]
                            break
                    if postal:
                        break
            if postal:
                phase2 += 1

        # Phase 3: district fallback
        if not postal and deal.district and deal.district in district_fallback:
            postal = district_fallback[deal.district]
            phase3 += 1

        if postal:
            deal.postal_code = postal

    db.commit()

    total_updated = phase1 + phase2 + phase3
    total_deals = db.query(models.Deal).count()
    with_postal = db.query(models.Deal).filter(models.Deal.postal_code.isnot(None)).count()

    return {
        "phase1_exact": phase1,
        "phase2_partial": phase2,
        "phase3_district": phase3,
        "total_updated": total_updated,
        "coverage": f"{with_postal}/{total_deals} ({100*with_postal/total_deals:.1f}%)",
    }


# ---------- Zone cleanup ----------

@router.post("/cleanup-zones")
def cleanup_zones(db: Session = Depends(get_db)):
    """Null out zone values that contain amenity keywords (bad Fotocasa scrapes)."""
    from scripts.cleanup_bad_zones import cleanup
    return cleanup(db)
