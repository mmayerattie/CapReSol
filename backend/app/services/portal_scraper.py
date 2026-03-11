"""
Portal scraper for Idealista (Madrid).

API limits: 100 req/month, 1 req/sec.
Strategy: paginate each search fully (50 results/page) to maximise listings
per request. Dedup by URL on insert so reruns are safe.
"""

import base64
import logging
import time
from datetime import date, datetime
from typing import Optional

import requests
from bs4 import BeautifulSoup
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError

from app.config import settings
from app.db.models import Deal

logger = logging.getLogger(__name__)

IDEALISTA_TOKEN_URL = "https://api.idealista.com/oauth/token"
IDEALISTA_SEARCH_URL = "https://api.idealista.com/3.5/es/search"

# Madrid location ID used by Idealista
MADRID_LOCATION_ID = "0-EU-ES-28"

# Delay between API calls to respect 1 req/sec limit
REQUEST_DELAY = 1.1  # slightly over 1s to be safe


# ---------------------------------------------------------------------------
# Authentication
# ---------------------------------------------------------------------------

def _get_access_token(api_key: str, secret: str) -> Optional[str]:
    """Obtain a short-lived OAuth2 access token from Idealista."""
    credentials = base64.b64encode(f"{api_key}:{secret}".encode()).decode()
    try:
        resp = requests.post(
            IDEALISTA_TOKEN_URL,
            headers={
                "Authorization": f"Basic {credentials}",
                "Content-Type": "application/x-www-form-urlencoded",
            },
            data={"grant_type": "client_credentials", "scope": "read"},
            timeout=15,
        )
        resp.raise_for_status()
        return resp.json().get("access_token")
    except Exception as exc:
        logger.error("Failed to get Idealista access token: %s", exc)
        return None


# ---------------------------------------------------------------------------
# Idealista API scraper
# ---------------------------------------------------------------------------

def _parse_api_listing(item: dict) -> dict:
    """Map a single Idealista API result dict to our Deal field names."""
    detail = item.get("detailedType", {})
    return {
        "url": item.get("url") or item.get("propertyCode"),
        "address": item.get("address"),
        "district": item.get("district"),
        "zone": item.get("neighborhood"),
        "city": item.get("municipality", "Madrid"),
        "country": "Spain",
        "property_type": detail.get("typology") or item.get("propertyType"),
        "asking_price": item.get("price"),
        "currency": "EUR",
        "size_sqm": item.get("size"),
        "bedrooms": item.get("rooms"),
        "bathrooms": item.get("bathrooms"),
        "floor": _parse_floor(item.get("floor")),
        "elevator": bool(item.get("hasLift")),
        "garage": bool(item.get("parkingSpace", {}).get("hasParkingSpace") if isinstance(item.get("parkingSpace"), dict) else item.get("parkingSpace")),
        "terrace": bool(item.get("hasTerrace")),
        "storage_room": bool(item.get("hasStorageRoom")),
        "condition": item.get("status"),
        "orientation": item.get("orientation"),
        "listed_date": _parse_date(item.get("modificationDate") or item.get("date")),
        "broker_name": None,
        "broker_contact": None,
        "balcony": False,  # not returned by API directly
    }


def _parse_floor(floor_val) -> Optional[int]:
    if floor_val is None:
        return None
    try:
        return int(floor_val)
    except (ValueError, TypeError):
        return None


def _parse_date(val) -> Optional[date]:
    if not val:
        return None
    try:
        # Idealista returns epoch ms or ISO string
        if isinstance(val, (int, float)):
            return datetime.fromtimestamp(val / 1000).date()
        return datetime.fromisoformat(val[:10]).date()
    except Exception:
        return None


def scrape_idealista_api(
    operation: str = "sale",
    property_type: str = "homes",
    max_pages: int = 10,
    max_price: Optional[int] = None,
    min_price: Optional[int] = None,
    bedrooms: Optional[int] = None,
) -> list[dict]:
    """
    Query the Idealista API for Madrid listings.

    Each page costs 1 API request (returns up to 50 results).
    max_pages controls how many requests this call uses — default 10 pages = 10 req.

    Returns a list of normalised deal dicts.
    """
    api_key = settings.IDEALISTA_API_KEY
    secret = settings.IDEALISTA_SECRET

    if not api_key or not secret:
        logger.error("Idealista API credentials not configured.")
        return []

    token = _get_access_token(api_key, secret)
    if not token:
        return []

    headers = {"Authorization": f"Bearer {token}"}
    listings: list[dict] = []

    for page in range(1, max_pages + 1):
        params: dict = {
            "locationId": MADRID_LOCATION_ID,
            "operation": operation,
            "propertyType": property_type,
            "numPage": page,
            "maxItems": 50,
            "order": "publicationDate",
            "sort": "desc",
            "language": "es",
        }
        if max_price:
            params["maxPrice"] = max_price
        if min_price:
            params["minPrice"] = min_price
        if bedrooms is not None:
            params["bedrooms"] = bedrooms

        try:
            time.sleep(REQUEST_DELAY)
            resp = requests.post(
                IDEALISTA_SEARCH_URL,
                headers=headers,
                data=params,  # Idealista requires form-encoded, not JSON
                timeout=20,
            )
            resp.raise_for_status()
            data = resp.json()
        except requests.HTTPError as exc:
            logger.error("Idealista API HTTP error on page %d: %s", page, exc)
            break
        except Exception as exc:
            logger.error("Idealista API error on page %d: %s", page, exc)
            break

        items = data.get("elementList", [])
        if not items:
            logger.info("No more results at page %d — stopping.", page)
            break

        for item in items:
            listings.append(_parse_api_listing(item))

        total_pages = data.get("totalPages", 1)
        logger.info(
            "API page %d/%d — got %d listings (total so far: %d)",
            page, total_pages, len(items), len(listings),
        )
        if page >= total_pages:
            break

    return listings


# ---------------------------------------------------------------------------
# HTML fallback scraper
# ---------------------------------------------------------------------------

def scrape_idealista_html(
    operation: str = "venta",
    max_pages: int = 5,
) -> list[dict]:
    """
    Fallback HTML scraper for when API quota is exhausted.
    Scrapes Idealista Madrid search results pages.
    """
    base_url = f"https://www.idealista.com/{operation}-viviendas/madrid-madrid/"
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/120.0.0.0 Safari/537.36"
        ),
        "Accept-Language": "es-ES,es;q=0.9",
    }

    listings: list[dict] = []

    for page in range(1, max_pages + 1):
        url = base_url if page == 1 else f"{base_url}pagina-{page}.htm"
        try:
            time.sleep(REQUEST_DELAY)
            resp = requests.get(url, headers=headers, timeout=20)
            resp.raise_for_status()
        except Exception as exc:
            logger.error("HTML scrape failed on page %d: %s", page, exc)
            break

        soup = BeautifulSoup(resp.text, "html.parser")
        articles = soup.select("article.item")

        if not articles:
            logger.info("No listings found on HTML page %d — stopping.", page)
            break

        for article in articles:
            listing = _parse_html_article(article)
            if listing:
                listings.append(listing)

        logger.info("HTML page %d — got %d listings (total: %d)", page, len(articles), len(listings))

    return listings


def _parse_html_article(article) -> Optional[dict]:
    """Extract fields from an Idealista search result <article> element."""
    try:
        link_tag = article.select_one("a.item-link")
        if not link_tag:
            return None

        url = "https://www.idealista.com" + link_tag.get("href", "")
        title = link_tag.get("title", "")

        price_tag = article.select_one(".item-price")
        price_text = price_tag.get_text(strip=True).replace(".", "").replace("€", "").replace("\xa0", "").strip() if price_tag else None
        price = float(price_text) if price_text and price_text.isdigit() else None

        detail_tag = article.select_one(".item-detail-char")
        details_text = detail_tag.get_text(" ", strip=True) if detail_tag else ""

        size = _extract_number(details_text, "m²")
        rooms = _extract_number(details_text, "hab")

        location_tag = article.select_one(".item-detail .gray")
        district = location_tag.get_text(strip=True) if location_tag else None

        return {
            "url": url,
            "address": title,
            "district": district,
            "zone": None,
            "city": "Madrid",
            "country": "Spain",
            "property_type": "flat",
            "asking_price": price,
            "currency": "EUR",
            "size_sqm": size,
            "bedrooms": int(rooms) if rooms else None,
            "bathrooms": None,
            "floor": None,
            "elevator": False,
            "garage": False,
            "terrace": False,
            "balcony": False,
            "storage_room": False,
            "condition": None,
            "orientation": None,
            "listed_date": date.today(),
            "broker_name": None,
            "broker_contact": None,
        }
    except Exception as exc:
        logger.warning("Failed to parse HTML article: %s", exc)
        return None


def _extract_number(text: str, unit: str) -> Optional[float]:
    """Pull the number immediately before `unit` from a string."""
    import re
    match = re.search(r"([\d,.]+)\s*" + re.escape(unit), text)
    if match:
        try:
            return float(match.group(1).replace(",", ".").replace(".", "", text.count(".") - 1))
        except ValueError:
            return None
    return None


# ---------------------------------------------------------------------------
# DB ingestion
# ---------------------------------------------------------------------------

def ingest_listings(db: Session, listings: list[dict]) -> int:
    """
    Bulk-upsert listings into the deals table.
    Deduplicates by URL (unique constraint). Returns count of new rows inserted.
    """
    inserted = 0
    for data in listings:
        if not data.get("url"):
            continue
        deal = Deal(**{k: v for k, v in data.items() if hasattr(Deal, k)})
        db.add(deal)
        try:
            db.flush()
            inserted += 1
        except IntegrityError:
            db.rollback()  # duplicate URL — skip silently
        except Exception as exc:
            db.rollback()
            logger.error("Failed to insert deal %s: %s", data.get("url"), exc)

    db.commit()
    logger.info("Ingested %d new deals out of %d listings.", inserted, len(listings))
    return inserted
