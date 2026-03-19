"""
Notary data scraper — fetches real transaction closing prices from the
Spanish Notary Statistical Portal (penotariado.com) via their public
ArcGIS FeatureServer API.

Data source: Colegio General del Notariado
Layer 4 = Código Postal level granularity

Filter IDs:
  tipo_construccion_id: 7=nueva, 9=segunda_mano, 99=todos
  clase_finca_urbana_id: 14=pisos, 15=casas, 99=todos
"""
import logging
import requests
from sqlalchemy.orm import Session

from app.db.models import NotaryStat

logger = logging.getLogger(__name__)

FEATURE_SERVER = (
    "https://services-eu1.arcgis.com/UpPGybwp9RK4YtZj"
    "/arcgis/rest/services/agol_precio_m2/FeatureServer/4/query"
)

# All combinations we want to scrape
TIPO_IDS = {"todos": 99, "nueva": 7, "segunda_mano": 9}
CLASE_IDS = {"todos": 99, "pisos": 14, "casas": 15}


def fetch_notary_data_madrid(
    tipo_id: int = 99,
    clase_id: int = 99,
) -> list[dict]:
    """
    Query the ESRI FeatureServer for all Madrid city postal codes (28001–28055).
    Returns a list of dicts with notary stats per postal code.
    """
    params = {
        "f": "json",
        "where": (
            f"cp >= '28001' AND cp <= '28055' "
            f"AND tipo_construccion_id = {tipo_id} "
            f"AND clase_finca_urbana_id = {clase_id}"
        ),
        "outFields": "cp,precio_m2,precio_medio,superficie_media,total_informados,total",
        "returnGeometry": "false",
        "resultRecordCount": 200,
        "orderByFields": "cp ASC",
    }

    resp = requests.get(FEATURE_SERVER, params=params, timeout=30)
    resp.raise_for_status()
    data = resp.json()

    results = []
    for feature in data.get("features", []):
        attrs = feature.get("attributes", {})
        cp = attrs.get("cp")
        if not cp:
            continue
        results.append({
            "postal_code": cp,
            "notary_price_sqm": attrs.get("precio_m2"),
            "notary_avg_price": attrs.get("precio_medio"),
            "notary_avg_surface": attrs.get("superficie_media"),
            "notary_transactions": attrs.get("total_informados"),
            "notary_total": attrs.get("total"),
        })

    return results


def ingest_notary_data(db: Session) -> int:
    """
    Fetch notary data for all tipo×clase combinations and upsert.
    Returns total records upserted.
    """
    from sqlalchemy.dialects.postgresql import insert

    total = 0
    for tipo_name, tipo_id in TIPO_IDS.items():
        for clase_name, clase_id in CLASE_IDS.items():
            records = fetch_notary_data_madrid(tipo_id, clase_id)
            for rec in records:
                rec["construction_type"] = tipo_name
                rec["property_class"] = clase_name

                stmt = insert(NotaryStat).values(**rec)
                stmt = stmt.on_conflict_do_update(
                    index_elements=["postal_code", "construction_type", "property_class"],
                    set_={
                        "notary_price_sqm": stmt.excluded.notary_price_sqm,
                        "notary_avg_price": stmt.excluded.notary_avg_price,
                        "notary_avg_surface": stmt.excluded.notary_avg_surface,
                        "notary_transactions": stmt.excluded.notary_transactions,
                        "notary_total": stmt.excluded.notary_total,
                    },
                )
                db.execute(stmt)
            total += len(records)
            logger.info(
                "Fetched %d records for tipo=%s, clase=%s",
                len(records), tipo_name, clase_name,
            )

    db.commit()
    logger.info("Total notary records upserted: %d", total)
    return total
