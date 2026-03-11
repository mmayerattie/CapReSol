from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.db import models
from app.api.schemas import DealRead, DealCreate, PredictRequest, PredictionRead
from app.services.extraction import create_deal_from_payload
from app.services.portal_scraper import (
    scrape_idealista_api,
    scrape_idealista_html,
    ingest_listings,
)
from app.ml.features import deal_to_features
from app.ml.model import predict_price_from_features

router = APIRouter(prefix="/deals", tags=["deals"])


# ---------- Existing endpoints ----------

@router.get("/", response_model=List[DealRead])
def list_deals(db: Session = Depends(get_db)):
    return db.query(models.Deal).order_by(models.Deal.created_at.desc()).all()


@router.post("/from-message", response_model=DealRead)
def create_deal_from_message(payload: DealCreate, db: Session = Depends(get_db)):
    try:
        deal = create_deal_from_payload(db, payload)
        return deal
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


# ---------- Scraping ----------

class ScrapeParams(BaseModel):
    operation: str = "sale"             # "sale" or "rent"
    property_type: str = "homes"        # "homes", "offices", "premises", "garages", "bedrooms"
    max_pages: int = 10                 # each page = 1 API request (50 results). Max 100/month total.
    max_price: Optional[int] = None
    min_price: Optional[int] = None
    bedrooms: Optional[int] = None
    use_html_fallback: bool = False     # True = skip API, use HTML scraper


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
    if params.use_html_fallback:
        operation_html = "venta" if params.operation == "sale" else "alquiler"
        listings = scrape_idealista_html(
            operation=operation_html,
            max_pages=params.max_pages,
        )
        source = "html"
    else:
        listings = scrape_idealista_api(
            operation=params.operation,
            property_type=params.property_type,
            max_pages=params.max_pages,
            max_price=params.max_price,
            min_price=params.min_price,
            bedrooms=params.bedrooms,
        )
        source = "api"

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
