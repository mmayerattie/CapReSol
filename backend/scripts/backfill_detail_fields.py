"""
Backfill missing condition, exterior, and orientation by visiting
individual listing detail pages via Firecrawl.

Only processes deals where condition IS NULL or exterior IS NULL.
Skips Redpiso (detail data not available via their API).
Handles expired listings gracefully (404/redirect = skip, don't overwrite).

Usage:
  python -m scripts.backfill_detail_fields              # all portals, limit 100
  python -m scripts.backfill_detail_fields --limit 50   # custom limit
  python -m scripts.backfill_detail_fields --portal idealista
  Or via API: POST /deals/backfill-details?limit=100
"""

import logging
import re
import sys
import os
import time
import argparse

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import or_, and_
from app.config import settings
from app.db.session import SessionLocal
from app.db.models import Deal

logger = logging.getLogger(__name__)

# Delay between Firecrawl requests (seconds)
REQUEST_DELAY = 2.0


# ---------------------------------------------------------------------------
# Detail page parsers (one per portal)
# ---------------------------------------------------------------------------

def _parse_idealista_detail(md: str) -> dict:
    """Parse condition/exterior/orientation from an Idealista detail page."""
    result = {}
    low = md.lower()

    # Condition: look for "Características básicas" section
    cb_idx = low.find("características básicas")
    if cb_idx == -1:
        cb_idx = low.find("caracteristicas basicas")
    section = md[cb_idx:cb_idx + 2000] if cb_idx != -1 else md

    from app.services.portal_scraper import _detect_condition, _detect_exterior
    result["condition"] = _detect_condition(section)
    result["exterior"] = _detect_exterior(section)

    # Orientation: look for explicit "orientación" or "Orientación norte/sur/..."
    ori_match = re.search(r'orientaci[oó]n\s*[:\-]?\s*(\w+)', low)
    if ori_match:
        result["orientation"] = ori_match.group(1).strip()

    # Exterior fallback from features line: "Planta 3ª exterior"
    if result["exterior"] is None:
        if re.search(r'planta\s+\d+[ªºa-z]*\s+exterior', low):
            result["exterior"] = True
        elif re.search(r'planta\s+\d+[ªºa-z]*\s+interior', low):
            result["exterior"] = False

    return result


def _parse_fotocasa_detail(md: str) -> dict:
    """Parse condition/exterior/orientation from a Fotocasa detail page."""
    result = {}
    low = md.lower()

    from app.services.portal_scraper import _detect_condition, _detect_exterior

    # Fotocasa detail pages have "Características" section with key-value pairs
    # Format in markdown: "Estado\n\nSegunda mano/buen estado"
    # or "Orientación\n\nSur"

    # Condition
    estado_match = re.search(r'estado\s*\n+\s*\n*\s*([^\n]+)', low)
    if estado_match:
        result["condition"] = _detect_condition(estado_match.group(1))
    if not result.get("condition"):
        result["condition"] = _detect_condition(md)

    # Orientation
    ori_match = re.search(r'orientaci[oó]n\s*\n+\s*\n*\s*([^\n]+)', low)
    if ori_match:
        val = ori_match.group(1).strip()
        if len(val) < 30:
            result["orientation"] = val

    # Exterior
    ext_match = re.search(r'(?:exterior|interior)\s*\n+\s*\n*\s*(s[ií]|no)', low)
    if ext_match:
        is_ext = "exterior" in low[ext_match.start()-20:ext_match.start()+10]
        is_yes = ext_match.group(1).lower() in ("sí", "si")
        if is_ext:
            result["exterior"] = is_yes
        else:
            result["exterior"] = not is_yes
    if result.get("exterior") is None:
        result["exterior"] = _detect_exterior(md)

    return result


def _parse_pisos_detail(md: str) -> dict:
    """Parse condition/exterior/orientation from a Pisos.com detail page."""
    result = {}
    low = md.lower()

    from app.services.portal_scraper import _detect_condition, _detect_exterior

    # Pisos.com shows "Conservación: Buen estado" or "Conservación\n\nBuen estado"
    cons_match = re.search(r'conservaci[oó]n\s*[:\n]+\s*([^\n|]+)', low)
    if cons_match:
        result["condition"] = _detect_condition(cons_match.group(1))
    if not result.get("condition"):
        # Also try "Estado"
        estado_match = re.search(r'estado\s*[:\n]+\s*([^\n|]+)', low)
        if estado_match:
            result["condition"] = _detect_condition(estado_match.group(1))
    if not result.get("condition"):
        result["condition"] = _detect_condition(md)

    # Orientation: "Orientación: Sur" or "Orientación\n\nSur"
    ori_match = re.search(r'orientaci[oó]n\s*[:\n]+\s*([^\n|]+)', low)
    if ori_match:
        val = ori_match.group(1).strip()
        if len(val) < 30:
            result["orientation"] = val

    # Exterior: "Exterior\n\nSí" or "Interior/Exterior: Exterior"
    if "exterior" in low:
        ext_match = re.search(r'(?:interior\s*/\s*exterior|exterior)\s*[:\n]+\s*([^\n|]+)', low)
        if ext_match:
            val = ext_match.group(1).strip()
            result["exterior"] = "exterior" in val
    if result.get("exterior") is None:
        result["exterior"] = _detect_exterior(md)

    return result


def _get_portal(url: str) -> str:
    if "idealista.com" in url:
        return "idealista"
    elif "fotocasa.es" in url:
        return "fotocasa"
    elif "pisos.com" in url:
        return "pisos"
    elif "redpiso.es" in url:
        return "redpiso"
    return "unknown"


PORTAL_PARSERS = {
    "idealista": _parse_idealista_detail,
    "fotocasa": _parse_fotocasa_detail,
    "pisos": _parse_pisos_detail,
}


# ---------------------------------------------------------------------------
# Main backfill
# ---------------------------------------------------------------------------

def backfill(db=None, limit=100, portal_filter=None):
    close_db = False
    if db is None:
        db = SessionLocal()
        close_db = True

    api_key = settings.FIRECRAWL_API_KEY
    if not api_key:
        print("FIRECRAWL_API_KEY not configured.")
        return {"error": "no api key"}

    from firecrawl import Firecrawl
    fc = Firecrawl(api_key=api_key)

    try:
        # Find deals missing condition OR exterior, excluding Redpiso
        query = db.query(Deal).filter(
            or_(
                Deal.condition.is_(None),
                Deal.exterior.is_(None),
            ),
            # Skip Redpiso — no detail data available
            ~Deal.url.like("%redpiso%"),
        )

        if portal_filter:
            query = query.filter(Deal.url.like(f"%{portal_filter}%"))

        deals = query.limit(limit).all()
        print(f"Found {len(deals)} deals to backfill (limit={limit})")

        stats = {
            "total": len(deals),
            "updated": 0,
            "skipped_expired": 0,
            "skipped_error": 0,
            "condition_filled": 0,
            "exterior_filled": 0,
            "orientation_filled": 0,
        }

        for i, deal in enumerate(deals):
            portal = _get_portal(deal.url)
            parser = PORTAL_PARSERS.get(portal)
            if not parser:
                stats["skipped_error"] += 1
                continue

            print(f"  [{i+1}/{len(deals)}] {portal}: {deal.url[:80]}...")

            try:
                result = fc.scrape(
                    deal.url,
                    location={"country": "ES"},
                    wait_for=5000,
                    remove_base64_images=True,
                )
                md = result.markdown or ""
            except Exception as exc:
                exc_str = str(exc).lower()
                # Expired/removed listings return 404 or redirect to search
                if "404" in exc_str or "not found" in exc_str:
                    print(f"    → Expired (404), skipping")
                    stats["skipped_expired"] += 1
                else:
                    print(f"    → Error: {exc}")
                    stats["skipped_error"] += 1
                time.sleep(REQUEST_DELAY)
                continue

            # Check if we got a real detail page or a redirect to search
            if not md or len(md) < 200:
                print(f"    → Empty response, skipping")
                stats["skipped_expired"] += 1
                time.sleep(REQUEST_DELAY)
                continue

            # Check for redirect to search page (expired listing)
            if portal == "idealista" and "/venta-viviendas/" in md[:500]:
                print(f"    → Redirected to search (expired), skipping")
                stats["skipped_expired"] += 1
                time.sleep(REQUEST_DELAY)
                continue

            # Parse the detail page
            parsed = parser(md)
            updated = False

            # Only fill fields that are currently NULL — never overwrite existing data
            if deal.condition is None and parsed.get("condition"):
                deal.condition = parsed["condition"]
                stats["condition_filled"] += 1
                updated = True

            if deal.exterior is None and parsed.get("exterior") is not None:
                deal.exterior = parsed["exterior"]
                stats["exterior_filled"] += 1
                updated = True

            if deal.orientation is None and parsed.get("orientation"):
                deal.orientation = parsed["orientation"]
                stats["orientation_filled"] += 1
                updated = True

            if updated:
                stats["updated"] += 1
                print(f"    → Filled: condition={parsed.get('condition')} exterior={parsed.get('exterior')} orientation={parsed.get('orientation')}")
            else:
                print(f"    → No new data found on detail page")

            # Commit every 10 deals to avoid losing progress
            if (i + 1) % 10 == 0:
                db.commit()

            time.sleep(REQUEST_DELAY)

        db.commit()

        # Report coverage
        total_deals = db.query(Deal).count()
        with_condition = db.query(Deal).filter(Deal.condition.isnot(None)).count()
        with_exterior = db.query(Deal).filter(Deal.exterior.isnot(None)).count()
        with_orientation = db.query(Deal).filter(Deal.orientation.isnot(None)).count()

        stats["coverage"] = {
            "condition": f"{with_condition}/{total_deals} ({100*with_condition/total_deals:.1f}%)",
            "exterior": f"{with_exterior}/{total_deals} ({100*with_exterior/total_deals:.1f}%)",
            "orientation": f"{with_orientation}/{total_deals} ({100*with_orientation/total_deals:.1f}%)",
        }

        print(f"\nDone. Updated {stats['updated']}/{stats['total']} deals.")
        print(f"  Condition filled: {stats['condition_filled']}")
        print(f"  Exterior filled: {stats['exterior_filled']}")
        print(f"  Orientation filled: {stats['orientation_filled']}")
        print(f"  Skipped expired: {stats['skipped_expired']}")
        print(f"  Skipped error: {stats['skipped_error']}")
        print(f"\nCoverage: {stats['coverage']}")

        return stats

    finally:
        if close_db:
            db.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, default=100)
    parser.add_argument("--portal", type=str, default=None, choices=["idealista", "fotocasa", "pisos"])
    args = parser.parse_args()
    backfill(limit=args.limit, portal_filter=args.portal)
