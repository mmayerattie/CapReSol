"""
Backfill postal_code for deals that have a zone but no postal_code.

Three-phase approach:
  1. Exact match:   zone name matches ZONE_TO_POSTAL dictionary (case-insensitive)
  2. Partial match:  strip prefixes, split compound names, normalize accents
  3. District fallback: assign the most common postal code for the deal's district

Run:  python -m scripts.backfill_postal_codes          (from backend/)
      python -m scripts.backfill_postal_codes --dry-run  (preview without writing)
"""
import sys
import os
import unicodedata
import re

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.db.session import SessionLocal
from app.db.models import Deal
from app.services.portal_scraper import ZONE_TO_POSTAL


# ── Phase 2 helpers ──────────────────────────────────────────────────────────

def strip_accents(s: str) -> str:
    """Remove diacritics: Zofío → Zofio, Jerónimos → Jeronimos."""
    nfkd = unicodedata.normalize("NFKD", s)
    return "".join(c for c in nfkd if not unicodedata.combining(c))


def build_lookup() -> dict[str, str]:
    """Build a case- and accent-insensitive lookup from ZONE_TO_POSTAL."""
    lookup = {}
    for name, code in ZONE_TO_POSTAL.items():
        lookup[name.lower()] = code
        lookup[strip_accents(name).lower()] = code
    return lookup


# Manual mappings for common compound zone names that the dict doesn't cover
# but where the correct postal code is obvious from the component barrio names.
MANUAL_OVERRIDES: dict[str, str] = {
    "lavapiés-embajadores":       "28012",
    "lavapies-embajadores":       "28012",
    "embajadores-lavapiés":       "28012",
    "embajadores-lavapies":       "28012",
    "malasaña-universidad":       "28015",
    "malasana-universidad":       "28015",
    "universidad-malasaña":       "28015",
    "universidad-malasana":       "28015",
    "huertas-cortes":             "28014",
    "cortes-huertas":             "28014",
    "chueca-justicia":            "28004",
    "justicia-chueca":            "28004",
    "nuevos ministerios-ríos rosas": "28003",
    "nuevos ministerios-rios rosas": "28003",
    "cuzco-castillejos":          "28020",
    "bernabéu-hispanoamérica":    "28016",
    "bernabeu-hispanoamerica":    "28016",
    "ventilla-almenara":          "28029",
    "ensanche de vallecas - la gavia": "28051",
    "ensanche de vallecas-valdecarros": "28051",
    "valdebebas - valdefuentes":  "28050",
    "valdebebas-valdefuentes":    "28050",
    "valdebernardo - valderrivas": "28032",
    "campo de las naciones-corralejos": "28042",
    "conde orgaz-piovera":        "28016",
    "virgen del cortijo - manoteras": "28043",
    "virgen del cortijo-manoteras": "28043",
    "parque lisboa - la paz":     "28034",
    "tres olivos - valverde":     "28034",
    "mirasierra-arroyo del fresno": "28034",
    "12 de octubre-orcasur":      "28041",
    "manuela malasaña":           "28015",
    "centro - ayuntamiento":      "28013",
    "centro sur - casco antiguo":  "28013",
    "pau de carabanchel":         "28025",
    "las tablas":                 "28050",
    "sanchinarro":                "28050",
    "montecarmelo":               "28035",
    "arroyo del fresno":          "28035",
    "peña grande":                "28035",
    "pena grande":                "28035",
    # Shortened versions of dict entries (missing article)
    "jerónimos":                  "28014",
    "jeronimos":                  "28014",
    "concepción":                 "28017",
    "concepcion":                 "28017",
    "cármenes":                   "28044",
    "carmenes":                   "28044",
    # One-word vs two-word variants
    "buena vista":                "28047",
    "buenavista":                 "28047",
    "palos de moguer":            "28045",
    "palos de la frontera":       "28045",
    # Redpiso compound names
    "río rosas":                  "28003",
    "rio rosas":                  "28003",
    "las águilas":                "28044",
    "las aguilas":                "28044",
    "los ángeles":                "28041",
    "los angeles":                "28041",
    "la chopera":                 "28045",
    "las acacias":                "28005",
    "casco histórico":            "28013",
    "casco historico":            "28013",
    "casco antiguo":              "28013",
    "salvador":                   "28022",
    "san andrés":                 "28021",
    "san andres":                 "28021",
    "ambroz":                     "28032",
    "los cerros":                 "28032",
    "los ahijones":               "28032",
    "los berrocales":             "28032",
    "valdemarín":                 "28023",
    "valdemarin":                 "28023",
    "sector 3":                   "28025",
    "la alhóndiga":               "28019",
    "la alhondiga":               "28019",
    "el bercial":                 "28025",
}


# Most common postal code per district (fallback for phase 3)
DISTRICT_FALLBACK: dict[str, str] = {
    "Centro":               "28013",
    "Arganzuela":           "28045",
    "Retiro":               "28007",
    "Salamanca":            "28001",
    "Chamartín":            "28016",
    "Tetuán":               "28020",
    "Chamberí":             "28003",
    "Fuencarral-El Pardo":  "28034",
    "Moncloa-Aravaca":      "28008",
    "Latina":               "28044",
    "Carabanchel":          "28019",
    "Usera":                "28026",
    "Puente de Vallecas":   "28018",
    "Moratalaz":            "28030",
    "Ciudad Lineal":        "28017",
    "Hortaleza":            "28043",
    "Villaverde":           "28021",
    "Villa de Vallecas":    "28031",
    "Vicálvaro":            "28032",
    "San Blas-Canillejas":  "28022",
    "Barajas":              "28042",
}


def try_partial_match(zone: str, lookup: dict[str, str]) -> str | None:
    """Phase 2: try several strategies to match a zone name."""
    z = zone.strip().lower()
    z_no_accent = strip_accents(z)

    # 2a. Check manual overrides first
    if z in MANUAL_OVERRIDES:
        return MANUAL_OVERRIDES[z]
    if z_no_accent in MANUAL_OVERRIDES:
        return MANUAL_OVERRIDES[z_no_accent]

    # 2b. Strip common prefixes: "La Chopera" → "Chopera", "Las Acacias" → "Acacias"
    for prefix in ("la ", "las ", "los ", "el "):
        stripped = z.removeprefix(prefix)
        if stripped in lookup:
            return lookup[stripped]
        stripped_na = strip_accents(stripped)
        if stripped_na in lookup:
            return lookup[stripped_na]

    # 2c. Split compound names on " - " or "-" and check each part
    parts = re.split(r'\s*[-–]\s*', z)
    for part in parts:
        part = part.strip()
        if part in lookup:
            return lookup[part]
        part_na = strip_accents(part)
        if part_na in lookup:
            return lookup[part_na]
        # Also try stripping prefix on each part
        for prefix in ("la ", "las ", "los ", "el "):
            stripped = part.removeprefix(prefix)
            if stripped in lookup:
                return lookup[stripped]

    # 2d. Check if any dict key is contained in the zone string (longest first)
    sorted_keys = sorted(lookup.keys(), key=len, reverse=True)
    for key in sorted_keys:
        if key in z_no_accent and len(key) >= 5:  # min 5 chars to avoid false matches
            return lookup[key]

    return None


def backfill(dry_run: bool = False) -> dict:
    """Run the three-phase backfill. Returns stats dict."""
    db = SessionLocal()
    lookup = build_lookup()

    stats = {
        "phase1_exact": 0,
        "phase2_partial": 0,
        "phase3_district": 0,
        "skipped_no_zone": 0,
        "skipped_outside_madrid": 0,
        "already_has_postal": 0,
        "total_updated": 0,
    }

    try:
        deals = db.query(Deal).all()
        print(f"Total deals in database: {len(deals)}")

        already = sum(1 for d in deals if d.postal_code)
        stats["already_has_postal"] = already
        print(f"Already have postal_code: {already}")

        candidates = [d for d in deals if not d.postal_code]
        print(f"Candidates for backfill: {len(candidates)}\n")

        for deal in candidates:
            zone = deal.zone
            district = deal.district

            if not zone:
                stats["skipped_no_zone"] += 1
                continue

            z_lower = zone.strip().lower()
            z_no_accent = strip_accents(z_lower)

            postal = None
            phase = None

            # Phase 1: exact match
            if z_lower in lookup:
                postal = lookup[z_lower]
                phase = "phase1_exact"
            elif z_no_accent in lookup:
                postal = lookup[z_no_accent]
                phase = "phase1_exact"

            # Phase 2: partial match
            if not postal:
                postal = try_partial_match(zone, lookup)
                if postal:
                    phase = "phase2_partial"

            # Phase 3: district fallback
            if not postal and district and district in DISTRICT_FALLBACK:
                postal = DISTRICT_FALLBACK[district]
                phase = "phase3_district"

            if postal:
                stats[phase] += 1
                stats["total_updated"] += 1
                if not dry_run:
                    deal.postal_code = postal

        if not dry_run:
            db.commit()
            print("Changes committed to database.\n")
        else:
            print("DRY RUN — no changes written.\n")

        print("Results:")
        print(f"  Phase 1 (exact match):      {stats['phase1_exact']}")
        print(f"  Phase 2 (partial match):     {stats['phase2_partial']}")
        print(f"  Phase 3 (district fallback): {stats['phase3_district']}")
        print(f"  Skipped (no zone):           {stats['skipped_no_zone']}")
        print(f"  Already had postal_code:     {stats['already_has_postal']}")
        print(f"  ─────────────────────────────")
        print(f"  Total updated:               {stats['total_updated']}")

        new_total = stats["already_has_postal"] + stats["total_updated"]
        total = len(deals)
        print(f"\n  Postal code coverage: {new_total}/{total} ({100*new_total/total:.1f}%)")
        print(f"  (was {already}/{total} = {100*already/total:.1f}%)")

        return stats

    finally:
        db.close()


if __name__ == "__main__":
    dry_run = "--dry-run" in sys.argv
    if dry_run:
        print("=== DRY RUN MODE ===\n")
    backfill(dry_run=dry_run)
