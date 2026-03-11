from typing import Dict, Any
from app.db.models import Deal

def deal_to_features(deal: Deal) -> Dict[str, Any]:
    """
    Convert Deal -> feature dict expected by the ML model.
    This version avoids asking price / price-derived leakage.
    """

    features: Dict[str, Any] = {
        "Numero de Habitaciones": deal.bedrooms or 0,
        "Numero de Baños": deal.bathrooms or 0,
        "Metros Cuadrados": deal.size_sqm or 0,
        "Planta": getattr(deal, "floor", 0) or 0,
        "Trastero": 1 if getattr(deal, "storage_room", False) else 0,
        "Terraza": 1 if getattr(deal, "terrace", False) else 0,
        "Balcon": 1 if getattr(deal, "balcony", False) else 0,
        "Ascensor": 1 if getattr(deal, "elevator", False) else 0,
        "Garaje": 1 if getattr(deal, "garage", False) else 0,
        "Distrito": getattr(deal, "district", "") or "",
        "Zona": getattr(deal, "zone", "") or "",
        "Estado": getattr(deal, "condition", "") or "",
        "Ubicacion": getattr(deal, "orientation", "") or "",
    }

    return features