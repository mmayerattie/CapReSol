"""
One-time cleanup: null out zone values that contain amenity keywords.
These were incorrectly scraped from Fotocasa address fields.

Run: python -m scripts.cleanup_bad_zones  (from backend/)
Or via API: POST /deals/cleanup-zones
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import or_, func
from app.db.session import SessionLocal
from app.db.models import Deal

BAD_KEYWORDS = [
    "calefaccion", "calefacción", "aire acondicionado", "terraza",
    "ascensor", "piscina", "garaje", "parking", "trastero",
    "reformar", "reformado", "amueblado", "luminoso", "soleado",
    "armarios", "parquet", "cocina", "lavadero", "portero",
]


def cleanup(db=None):
    close_db = False
    if db is None:
        db = SessionLocal()
        close_db = True

    try:
        # Find deals where zone contains any bad keyword
        filters = [Deal.zone.ilike(f"%{kw}%") for kw in BAD_KEYWORDS]
        # Also catch zones with commas (multi-value = likely amenity list)
        filters.append(Deal.zone.like("%,%"))

        bad_deals = db.query(Deal).filter(or_(*filters)).all()
        count = len(bad_deals)

        for deal in bad_deals:
            deal.zone = None

        db.commit()
        print(f"Cleaned {count} deals with bad zone values")
        return {"cleaned": count}
    finally:
        if close_db:
            db.close()


if __name__ == "__main__":
    cleanup()
