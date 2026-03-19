from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.auth import get_current_user
from app.db.session import get_db
from app.db.models import NotaryStat

router = APIRouter(prefix="/notary", tags=["notary"], dependencies=[Depends(get_current_user)])


@router.post("/scrape")
def scrape_notary(db: Session = Depends(get_db)):
    """Fetch latest notary closing prices from penotariado.com and upsert."""
    from app.services.notary_scraper import ingest_notary_data
    count = ingest_notary_data(db)
    return {"records_upserted": count}


@router.get("")
def get_notary_stats(
    db: Session = Depends(get_db),
    construction_type: str = "segunda_mano",
    property_class: str = "pisos",
):
    """Return notary stats filtered by construction type and property class."""
    rows = (
        db.query(NotaryStat)
        .filter(
            NotaryStat.construction_type == construction_type,
            NotaryStat.property_class == property_class,
        )
        .order_by(NotaryStat.postal_code)
        .all()
    )
    return [
        {
            "postal_code": r.postal_code,
            "construction_type": r.construction_type,
            "property_class": r.property_class,
            "notary_price_sqm": r.notary_price_sqm,
            "notary_avg_price": r.notary_avg_price,
            "notary_avg_surface": r.notary_avg_surface,
            "notary_transactions": r.notary_transactions,
            "notary_total": r.notary_total,
        }
        for r in rows
    ]
