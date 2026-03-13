"""
Portal scraper for Idealista, Redpiso, and Fotocasa (Madrid).

Idealista: OAuth2 API — 100 req/month, 1 req/sec.
Redpiso: JSON API — no auth, no quota.
Fotocasa: HTML via Firecrawl — JS-rendered, geo-proxied to Spain.

Strategy: paginate each search fully, dedup by URL on insert (upsert).
"""

import base64
import logging
import random
import re
import time
from datetime import date, datetime
from typing import Optional

import requests
from firecrawl import Firecrawl
from sqlalchemy import func
from sqlalchemy.orm import Session
from sqlalchemy.dialects.postgresql import insert as pg_insert

from app.config import settings
from app.db.models import Deal

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Madrid district normalisation
# ---------------------------------------------------------------------------
# Madrid has 21 official districts. Scrapers return a mix of district names,
# barrio (neighbourhood) names, and variant spellings. This mapping normalises
# everything to the canonical district name.

# Reverse lookup: lowercase keyword → canonical district name
_BARRIO_TO_DISTRICT: dict[str, str] = {}

_DISTRICT_ALIASES: dict[str, list[str]] = {
    "Centro": [
        "centro", "sol", "palacio", "embajadores", "lavapiés", "lavapies",
        "cortes", "huertas", "justicia", "chueca", "universidad", "malasaña",
        "malasana",
    ],
    "Arganzuela": [
        "arganzuela", "acacias", "legazpi", "delicias", "palos de moguer",
        "palos de la frontera", "chopera", "imperial",
    ],
    "Retiro": [
        "retiro", "jerónimos", "jeronimos", "niño jesús", "nino jesus",
        "pacífico", "pacifico", "adelfas", "estrella", "ibiza",
    ],
    "Salamanca": [
        "salamanca", "barrio de salamanca", "recoletos", "goya", "lista",
        "castellana", "el viso", "fuente del berro", "guindalera",
    ],
    "Chamartín": [
        "chamartín", "chamartin", "hispanoamérica", "hispanoamerica",
        "nueva españa", "nueva espana", "prosperidad", "ciudad jardín",
        "ciudad jardin", "bernabéu", "bernabeu", "el viso",
    ],
    "Tetuán": [
        "tetuán", "tetuan", "valdeacederas", "berruguete", "cuatro caminos",
        "azca", "almenara", "bellas vistas", "castillejos",
    ],
    "Chamberí": [
        "chamberí", "chamberi", "gaztambide", "arapiles", "trafalgar",
        "ríos rosas", "rios rosas", "vallehermoso", "almagro",
        "nuevos ministerios",
    ],
    "Fuencarral-El Pardo": [
        "fuencarral-el pardo", "fuencarral - el pardo", "fuencarral",
        "el pardo", "peñagrande", "penagrande", "mirasierra",
        "fuentelarreina", "tres olivos", "valverde", "montecarmelo",
        "la paz", "pilar",
    ],
    "Moncloa-Aravaca": [
        "moncloa-aravaca", "moncloa - aravaca", "moncloa", "aravaca",
        "argüelles", "arguelles", "ciudad universitaria", "valdemarín",
        "valdemarin", "casa de campo",
    ],
    "Latina": [
        "latina", "lucero", "aluche", "los cármenes", "los carmenes",
        "campamento", "águilas", "aguilas", "cuatro vientos",
        "puerta del ángel", "puerta del angel",
    ],
    "Carabanchel": [
        "carabanchel", "opañel", "opanel", "san isidro", "vista alegre",
        "buenavista", "buena vista", "abrantes", "comillas",
        "puerta bonita", "pau de carabanchel",
    ],
    "Usera": [
        "usera", "almendrales", "moscardó", "moscardo", "orcasitas",
        "pradolongo", "zofío", "zofio",
    ],
    "Puente de Vallecas": [
        "puente de vallecas", "vallecas", "san diego", "palomeras",
        "palomeras sureste", "portazgo", "numancia", "entrevías",
        "entrevias",
    ],
    "Moratalaz": [
        "moratalaz", "fontarrón", "fontarron", "vinateros", "pavones",
        "horcajo", "marroquina",
    ],
    "Ciudad Lineal": [
        "ciudad lineal", "ventas", "pueblo nuevo", "quintana",
        "concepción", "concepcion", "san juan bautista", "san pascual",
        "colina", "atalaya",
    ],
    "Hortaleza": [
        "hortaleza", "pinar del rey", "canillas", "piovera", "palomas",
        "valdefuentes", "apóstol santiago", "apostol santiago",
        "virgen del cortijo",
    ],
    "Villaverde": [
        "villaverde", "villaverde alto", "villaverde bajo", "butarque",
        "san cristóbal", "san cristobal", "los rosales", "los ángeles",
        "los angeles",
    ],
    "Villa de Vallecas": [
        "villa de vallecas", "santa eugenia", "ensanche de vallecas",
        "casco histórico de vallecas",
    ],
    "Vicálvaro": [
        "vicálvaro", "vicalvaro", "valdebernardo", "valderribas", "ambroz",
        "el cañaveral",
    ],
    "San Blas-Canillejas": [
        "san blas-canillejas", "san blas", "canillejas", "simancas",
        "hellín", "hellin", "amposta", "arcos", "rosas", "rejas",
    ],
    "Barajas": [
        "barajas", "casco histórico de barajas", "aeropuerto",
        "alameda de osuna", "corralejos", "timón", "timon",
    ],
}

# Build the reverse lookup
for _canon, _aliases in _DISTRICT_ALIASES.items():
    for _alias in _aliases:
        _BARRIO_TO_DISTRICT[_alias] = _canon

# Names to discard (not real districts)
_DISTRICT_BLACKLIST = {"distrito único", "distrito unico"}


def normalize_district(raw: str | None) -> str | None:
    """
    Map a scraped district/barrio name to one of Madrid's 21 canonical districts.

    Returns the canonical name if matched, None if blacklisted or unknown
    (non-Madrid municipality names pass through unchanged).
    """
    if not raw:
        return None
    cleaned = raw.strip()
    lower = cleaned.lower()

    if lower in _DISTRICT_BLACKLIST:
        return None

    # Direct lookup
    if lower in _BARRIO_TO_DISTRICT:
        return _BARRIO_TO_DISTRICT[lower]

    # Partial match: check if any alias is contained in the raw string
    # e.g. "Casco Histórico de Barajas" contains "barajas"
    # Sort by length descending so longer matches win
    for alias in sorted(_BARRIO_TO_DISTRICT, key=len, reverse=True):
        if alias in lower:
            return _BARRIO_TO_DISTRICT[alias]

    # Not a known Madrid district/barrio — return None (skip suburban municipalities)
    return None


# Set of canonical names for quick membership checks
CANONICAL_DISTRICTS = set(_DISTRICT_ALIASES.keys())


IDEALISTA_TOKEN_URL = "https://api.idealista.com/oauth/token"
IDEALISTA_SEARCH_URL = "https://api.idealista.com/3.5/es/search"

# Madrid location ID used by Idealista
MADRID_LOCATION_ID = "0-EU-ES-28"

# Delay between API calls to respect 1 req/sec limit
REQUEST_DELAY = 1.1  # slightly over 1s to be safe

# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------

USER_AGENTS = [
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.3 Safari/605.1.15",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:122.0) Gecko/20100101 Firefox/122.0",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
]


def _html_headers(referer: Optional[str] = None) -> dict:
    """Return browser-like headers with a random User-Agent."""
    h = {
        "User-Agent": random.choice(USER_AGENTS),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
        "Accept-Language": "es-ES,es;q=0.9,en;q=0.8",
        "Accept-Encoding": "gzip, deflate, br",
        "Connection": "keep-alive",
        "Upgrade-Insecure-Requests": "1",
    }
    if referer:
        h["Referer"] = referer
    return h


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
# Idealista HTML scraper (via Firecrawl)
# Bypasses DataDome bot protection via Firecrawl's JS rendering.
# ~15,374 Madrid sale listings, 30 per page. No API quota cost.
# ---------------------------------------------------------------------------

IDEALISTA_HTML_BASE = "https://www.idealista.com"
IDEALISTA_HTML_SEARCH_TPL = "{base}/venta-viviendas/madrid-madrid/pagina-{page}.htm"

# Listing link: [Piso en Calle X, Barrio, Madrid](https://www.idealista.com/inmueble/12345/ "title")
_RE_IDEALISTA_TITLE = re.compile(
    r'\[(.+?)\]\((https://www\.idealista\.com/inmueble/\d+/)(?:\s+"[^"]*")?\)'
)
# Price: 2.780.000€  or  845.000€  (no space before €)
_RE_IDEALISTA_PRICE = re.compile(r'([\d.]+)\s*€')
# Features line: "4 hab.241 m²Planta 2ª exterior con ascensor"
_RE_IDEALISTA_HAB = re.compile(r'(\d+)\s*hab', re.IGNORECASE)
_RE_IDEALISTA_SQM = re.compile(r'([\d]+(?:[.,]\d+)?)\s*m²', re.IGNORECASE)
_RE_IDEALISTA_BANOS = re.compile(r'(\d+)\s*baño', re.IGNORECASE)
_RE_IDEALISTA_FLOOR = re.compile(r'[Pp]lanta\s*(\d+)', re.IGNORECASE)


def _parse_idealista_html_listings(markdown: str) -> list[dict]:
    """Extract property listings from Firecrawl markdown of an Idealista page."""
    listings: list[dict] = []

    for title_match in _RE_IDEALISTA_TITLE.finditer(markdown):
        title_text = title_match.group(1).strip()
        url = title_match.group(2).strip()

        # Get context after the title link (price + features)
        end = title_match.end()
        context_after = markdown[end:end + 1500]

        # Price: first €-amount after the title
        price_match = _RE_IDEALISTA_PRICE.search(context_after)
        asking_price = None
        if price_match:
            price_str = price_match.group(1).replace('.', '')
            try:
                asking_price = float(price_str)
            except ValueError:
                pass

        # Prefer features from "Características básicas" section if present
        cb_idx = context_after.lower().find("características básicas")
        if cb_idx == -1:
            cb_idx = context_after.lower().find("caracteristicas basicas")
        features_ctx = context_after[cb_idx:cb_idx + 800] if cb_idx != -1 else context_after

        # Features
        hab = _RE_IDEALISTA_HAB.search(features_ctx)
        sqm = _RE_IDEALISTA_SQM.search(features_ctx)
        banos = _RE_IDEALISTA_BANOS.search(features_ctx)
        floor = _RE_IDEALISTA_FLOOR.search(features_ctx)

        # Parse title: "Piso en Calle X, Barrio, Madrid"
        # → address = full title minus property type prefix
        # → district from the penultimate comma-separated part (barrio name)
        address = title_text
        for prefix in ("Piso en ", "Casa o chalet en ", "Ático en ", "Estudio en ",
                        "Dúplex en ", "Chalet en ", "Casa en ", "Loft en "):
            if title_text.startswith(prefix):
                address = title_text[len(prefix):]
                break

        parts = [p.strip() for p in address.split(',')]
        # Last part is usually "Madrid", penultimate is barrio/zone
        district = parts[-2] if len(parts) >= 2 else None
        # Remove "Madrid" from address if it's the last part
        if len(parts) >= 2 and parts[-1].lower() == "madrid":
            address = ", ".join(parts[:-1])

        # Property type
        prop_type = "piso"
        tl = title_text.lower()
        if "casa" in tl or "chalet" in tl:
            prop_type = "casa"
        elif "ático" in tl or "atico" in tl:
            prop_type = "ático"
        elif "estudio" in tl:
            prop_type = "estudio"
        elif "dúplex" in tl or "duplex" in tl:
            prop_type = "dúplex"
        elif "loft" in tl:
            prop_type = "loft"

        # Amenities from context
        ctx_lower = context_after.lower()

        # Condition detection (check features_ctx first for precision, fallback to full ctx)
        feat_lower = features_ctx.lower()
        if "a reformar" in feat_lower or "para reformar" in feat_lower or "para restaurar" in feat_lower:
            condition = "renew"
        elif ("obra nueva" in feat_lower or "nueva construcción" in feat_lower
              or "nueva construccion" in feat_lower or "de obra nueva" in feat_lower):
            condition = "newdevelopment"
        elif ("buen estado" in feat_lower or "bien conservado" in feat_lower
              or "muy buen estado" in feat_lower or "segunda mano" in feat_lower):
            condition = "good"
        else:
            condition = None

        # Orientation: parse "Orientación sur, oeste" from features section
        ori_match = re.search(r'[Oo]rientaci[oó]n\s*:?\s*([^\n,\*]+)', features_ctx)
        if ori_match:
            orientation = ori_match.group(1).strip()
        elif "exterior" in ctx_lower:
            orientation = "exterior"
        else:
            orientation = None

        listing = {
            "url": url,
            "address": address,
            "district": district,
            "zone": None,
            "city": "Madrid",
            "country": "Spain",
            "property_type": prop_type,
            "asking_price": asking_price,
            "currency": "EUR",
            "size_sqm": float(sqm.group(1).replace(',', '.')) if sqm else None,
            "bedrooms": int(hab.group(1)) if hab else None,
            "bathrooms": int(banos.group(1)) if banos else None,
            "floor": int(floor.group(1)) if floor else None,
            "elevator": "ascensor" in ctx_lower,
            "garage": "garaje" in ctx_lower or "parking" in ctx_lower or "plaza de garaje" in ctx_lower,
            "terrace": "terraza" in ctx_lower,
            "balcony": "balcón" in ctx_lower or "balcon" in ctx_lower,
            "storage_room": "trastero" in ctx_lower,
            "condition": condition,
            "orientation": orientation,
            "listed_date": date.today(),
            "broker_name": None,
            "broker_contact": None,
        }
        listings.append(listing)

    return listings


def scrape_idealista_html(
    max_pages: int = 3,
    page_from: int = 1,
) -> list[dict]:
    """
    Scrape Idealista Madrid listings via Firecrawl (HTML).

    Bypasses DataDome bot protection. ~15,374 listings, 30 per page.
    No API quota cost (unlike the OAuth2 API).

    Returns a list of normalised deal dicts.
    """
    api_key = settings.FIRECRAWL_API_KEY
    if not api_key:
        logger.error("FIRECRAWL_API_KEY not configured.")
        return []

    fc = Firecrawl(api_key=api_key)
    listings: list[dict] = []

    for page in range(page_from, page_from + max_pages):
        if page == 1:
            url = f"{IDEALISTA_HTML_BASE}/venta-viviendas/madrid-madrid/"
        else:
            url = IDEALISTA_HTML_SEARCH_TPL.format(
                base=IDEALISTA_HTML_BASE, page=page,
            )
        logger.info("Idealista HTML: scraping page %d — %s", page, url)

        try:
            result = fc.scrape(
                url,
                location={"country": "ES"},
                wait_for=5000,
                remove_base64_images=True,
            )
            md = result.markdown or ""
        except Exception as exc:
            logger.error("Idealista HTML Firecrawl error on page %d: %s", page, exc)
            break

        if not md or len(md) < 500:
            logger.warning("Idealista HTML: empty/blocked page %d (%d chars).", page, len(md))
            break

        page_listings = _parse_idealista_html_listings(md)
        listings.extend(page_listings)
        logger.info(
            "Idealista HTML page %d — %d listings (total: %d)",
            page, len(page_listings), len(listings),
        )

        if not page_listings:
            logger.info("Idealista HTML: no listings on page %d — stopping.", page)
            break

        time.sleep(1.5 + random.uniform(0, 0.5))

    return listings


# ---------------------------------------------------------------------------
# Redpiso JSON API scraper
# API endpoint: https://www.redpiso.es/api/properties (no auth required)
# Returns 1,284+ Madrid listings, 50 per page.
# ---------------------------------------------------------------------------

REDPISO_BASE = "https://www.redpiso.es"
REDPISO_API = f"{REDPISO_BASE}/api/properties"
REDPISO_PAGE_SIZE = 50


def scrape_redpiso_html(
    operation: str = "venta",
    page_from: int = 1,
    max_pages: int = 5,
) -> list[dict]:
    """
    Scrape Redpiso Madrid listings via their internal JSON API.

    Endpoint: GET /api/properties?page=N&pageSize=50&type=sale&...
    No authentication required. Returns clean JSON with full listing data
    including broker phone, district, size, bedrooms, and bathrooms.

    page_from: first page to fetch (1-based). Used for chunked scraping to
    avoid long-running requests timing out the Next.js proxy (30s limit).
    """
    op_type = "sale" if operation == "venta" else "rent"
    listings: list[dict] = []

    for page in range(page_from, page_from + max_pages):
        params = {
            "page": page,
            "pageSize": REDPISO_PAGE_SIZE,
            "type": op_type,
            "statuses[]": ["ongoing", "pending_signature"],
            "sort": "recent",
            "province_slug": "madrid",
            "property_group_slug": "viviendas",
        }
        try:
            time.sleep(REQUEST_DELAY + random.uniform(0, 0.5))
            resp = requests.get(
                REDPISO_API,
                params=params,
                headers=_html_headers(referer=f"{REDPISO_BASE}/venta-viviendas/madrid"),
                timeout=20,
            )
            resp.raise_for_status()
            data = resp.json()
        except Exception as exc:
            logger.error("Redpiso API error on page %d: %s", page, exc)
            break

        items = data.get("items", [])
        if not items:
            logger.info("Redpiso: no items on page %d — stopping.", page)
            break

        for item in items:
            listing = _map_redpiso_listing(item)
            if listing:
                listings.append(listing)

        total = data.get("total", 0)
        logger.info(
            "Redpiso API page %d — %d listings (total so far: %d / %d available)",
            page, len(items), len(listings), total,
        )

        # Stop if we've fetched all available pages
        if page * REDPISO_PAGE_SIZE >= total:
            break

    return listings


def _map_redpiso_listing(item: dict) -> Optional[dict]:
    """Map a Redpiso API response item to our Deal field names."""
    try:
        slug = item.get("slug") or item.get("code")
        if not slug:
            return None
        url = f"{REDPISO_BASE}/inmueble/{slug}"

        cadastre = item.get("cadastre_property_summary") or {}
        prop_type_obj = cadastre.get("property_type") or {}
        location = item.get("location") or {}
        district_obj = location.get("district") or {}
        quarter_obj = location.get("quarter") or {}
        office = item.get("office") or {}

        # Build human-readable address from display_location
        address = item.get("display_location") or item.get("short_description") or ""

        return {
            "url": url,
            "address": address,
            "district": district_obj.get("name"),
            "zone": quarter_obj.get("name"),
            "city": "Madrid",
            "country": "Spain",
            "property_type": prop_type_obj.get("name") or "flat",
            "asking_price": float(item["price"]) if item.get("price") else None,
            "currency": "EUR",
            "size_sqm": next((float(cadastre[k]) for k in ("usable_meters", "meters", "property_meters") if cadastre.get(k)), None),
            "bedrooms": int(cadastre["bedrooms"]) if cadastre.get("bedrooms") else None,
            "bathrooms": int(cadastre["bathrooms"]) if cadastre.get("bathrooms") else None,
            "floor": None,
            "elevator": False,
            "garage": False,
            "terrace": False,
            "balcony": False,
            "storage_room": False,
            "condition": None,
            "orientation": None,
            "listed_date": date.today(),
            "broker_name": office.get("name"),
            "broker_contact": office.get("phone"),
        }
    except Exception as exc:
        logger.warning("Redpiso: failed to map listing: %s", exc)
        return None


# ---------------------------------------------------------------------------
# Fotocasa scraper (via Firecrawl)
# Firecrawl handles JS rendering + anti-bot bypass.
# Requires location={'country': 'ES'} because Fotocasa geo-blocks non-Spain.
# ---------------------------------------------------------------------------

FOTOCASA_BASE = "https://www.fotocasa.es"
FOTOCASA_SEARCH_TPL = (
    "{base}/es/{operation}/viviendas/madrid-capital/todas-las-zonas/l/{page}"
)

# Regex patterns for parsing Fotocasa markdown listing blocks
_RE_TITLE = re.compile(
    r'###\s+\[\*\*(.+?)\*\*\s+(?:con\s+.+?\s+)?en\s+(.+?)\]\((.+?)\)',
)
_RE_PRICE = re.compile(r'([\d.]+)\s*€')
_RE_HABS = re.compile(r'(\d+)\s*habs?')
_RE_BANOS = re.compile(r'(\d+)\s*baños?')
_RE_SQM = re.compile(r'(\d+)\s*m²')
_RE_FLOOR = re.compile(r'(\d+)ª?\s*[Pp]lanta')


def _parse_fotocasa_listings(markdown: str) -> list[dict]:
    """Extract property listings from Firecrawl markdown of a Fotocasa page."""
    listings: list[dict] = []

    # Split on ### headings (each is a listing title)
    blocks = re.split(r'(?=###\s+\[)', markdown)

    for block in blocks:
        title_match = _RE_TITLE.search(block)
        if not title_match:
            continue

        property_type_raw = title_match.group(1).strip()
        address_raw = title_match.group(2).strip()
        url = title_match.group(3).strip()

        # Clean URL — remove query params
        if '?' in url:
            url = url.split('?')[0]

        # Skip non-fotocasa URLs
        if 'fotocasa.es' not in url:
            continue

        # Extract price — look before the title in the original markdown.
        # Price line format: "2.490.000 €210.000 €Ha bajado 210.000 €"
        # The first price is the actual asking price; subsequent ones are discounts.
        # Search a narrow window just before the title (skip previous listing's text).
        title_pos = markdown.find(block[:80])
        # Find the price line: narrow window to avoid grabbing previous listing's price
        context_before = markdown[max(0, title_pos - 600):title_pos] if title_pos > 0 else ""
        # Look for the price line — it's a standalone line with €
        price_line_match = re.search(r'(?:^|\n)([\d.]+\s*€.*€?[^\n]*)', context_before)
        if price_line_match:
            # First price on that line is the actual asking price
            price_match = _RE_PRICE.search(price_line_match.group(1))
        else:
            price_match = _RE_PRICE.search(context_before)
        if not price_match:
            price_match = _RE_PRICE.search(block[:200])
        asking_price = None
        if price_match:
            price_str = price_match.group(1).replace('.', '')
            try:
                asking_price = float(price_str)
            except ValueError:
                pass

        # Extract features from the bullet list (early part of block)
        features_text = block[:600]  # features appear early in the block
        habs = _RE_HABS.search(features_text)
        banos = _RE_BANOS.search(features_text)
        sqm = _RE_SQM.search(features_text)
        floor_m = _RE_FLOOR.search(features_text)

        # Parse district from address (last part after comma)
        parts = [p.strip() for p in address_raw.split(',')]
        district = parts[-1] if len(parts) > 1 else None
        address = address_raw

        # Amenities/condition/orientation from the full block and Características section
        features_lower = features_text.lower()
        block_lower = block.lower()

        # Look for structured "Características" section (key\n\nvalue format from Fotocasa)
        caract_idx = block_lower.find("características")
        caract_ctx = block[caract_idx:caract_idx + 1000] if caract_idx != -1 else ""

        condition = None
        orientation = None
        floor_val = int(floor_m.group(1)) if floor_m else None
        elevator = "ascensor" in features_lower

        if caract_ctx:
            # Estado → condition  (format: "Estado\n\nBien" or "**Estado**\n\nBien")
            estado_m = re.search(
                r'\bEstado\b[^\n]*\n+\s*\**\s*([A-Za-záéíóúüñÁÉÍÓÚÜÑ/ ]+)',
                caract_ctx,
            )
            if estado_m:
                est_val = estado_m.group(1).strip().lower()
                if "bien" in est_val or "buen" in est_val:
                    condition = "good"
                elif "reformar" in est_val or "restaurar" in est_val:
                    condition = "renew"
                elif "nuevo" in est_val or "nueva" in est_val or "obra" in est_val:
                    condition = "newdevelopment"

            # Planta → floor (only if not already found in features_text)
            if floor_val is None:
                planta_m = re.search(r'\bPlanta\b[^\n]*\n+\s*(\d+)', caract_ctx)
                if planta_m:
                    floor_val = int(planta_m.group(1))

            # Ascensor → elevator  (format: "Ascensor\n\nSí" or "Ascensor\n\nNo")
            asc_m = re.search(
                r'\bAscensor\b[^\n]*\n+\s*\**\s*(Sí|Si|sí|si|No|no)\b',
                caract_ctx,
            )
            if asc_m:
                elevator = asc_m.group(1).lower() in ("sí", "si")

            # Orientación → orientation
            ori_m = re.search(
                r'\bOrientaci[oó]n\b[^\n]*\n+\s*\**\s*([^\n\*\[]+)',
                caract_ctx,
            )
            if ori_m:
                orientation = ori_m.group(1).strip()

        listing = {
            "url": url,
            "address": address,
            "district": district,
            "zone": None,
            "city": "Madrid",
            "country": "Spain",
            "property_type": property_type_raw.lower(),
            "asking_price": asking_price,
            "currency": "EUR",
            "size_sqm": float(sqm.group(1)) if sqm else None,
            "bedrooms": int(habs.group(1)) if habs else None,
            "bathrooms": int(banos.group(1)) if banos else None,
            "floor": floor_val,
            "elevator": elevator,
            "garage": "garaje" in block_lower or "parking" in block_lower,
            "terrace": "terraza" in block_lower,
            "balcony": "balcón" in block_lower or "balcon" in block_lower,
            "storage_room": "trastero" in block_lower,
            "condition": condition,
            "orientation": orientation,
            "listed_date": date.today(),
            "broker_name": None,
            "broker_contact": None,
        }
        listings.append(listing)

    return listings


def scrape_fotocasa_firecrawl(
    operation: str = "comprar",
    max_pages: int = 3,
    page_from: int = 1,
) -> list[dict]:
    """
    Scrape Fotocasa Madrid listings via Firecrawl.

    Firecrawl renders the JS-heavy page and returns markdown.
    Requires location={'country': 'ES'} to bypass Fotocasa geo-block.

    Returns a list of normalised deal dicts.
    """
    api_key = settings.FIRECRAWL_API_KEY
    if not api_key:
        logger.error("FIRECRAWL_API_KEY not configured.")
        return []

    fc = Firecrawl(api_key=api_key)
    listings: list[dict] = []

    for page in range(page_from, page_from + max_pages):
        url = FOTOCASA_SEARCH_TPL.format(
            base=FOTOCASA_BASE, operation=operation, page=page,
        )
        logger.info("Fotocasa: scraping page %d — %s", page, url)

        try:
            result = fc.scrape(
                url,
                location={"country": "ES"},
                wait_for=5000,
                remove_base64_images=True,
            )
            md = result.markdown or ""
        except Exception as exc:
            logger.error("Firecrawl error on page %d: %s", page, exc)
            break

        if not md or len(md) < 500:
            logger.warning("Fotocasa: empty/blocked page %d (%d chars).", page, len(md))
            break

        page_listings = _parse_fotocasa_listings(md)
        listings.extend(page_listings)
        logger.info(
            "Fotocasa page %d — %d listings (total: %d)",
            page, len(page_listings), len(listings),
        )

        if not page_listings:
            logger.info("Fotocasa: no listings found on page %d — stopping.", page)
            break

        time.sleep(1.5 + random.uniform(0, 0.5))

    return listings


# ---------------------------------------------------------------------------
# Pisos.com scraper (via Firecrawl)
# ~10,500 Madrid sale listings, 30 per page.
# No geo-block — works without location param, but we add it for consistency.
# ---------------------------------------------------------------------------

PISOS_BASE = "https://www.pisos.com"
PISOS_SEARCH_TPL = "{base}/{operation}/pisos-madrid/{page}/"

# Regex: title link like [Piso en calle Gaztambide](https://www.pisos.com/comprar/...)
_RE_PISOS_TITLE = re.compile(
    r'\[(.+?)\]\((https://www\.pisos\.com/comprar/.+?/)\)'
)
# District line: "Gaztambide (Distrito Chamberí. Madrid Capital)"
_RE_PISOS_DISTRICT = re.compile(
    r'^(.+?)\s*\(Distrito\s+(.+?)\.\s*Madrid\s+Capital\)',
    re.MULTILINE,
)
_RE_PISOS_HABS = re.compile(r'(\d+)\s*habs?\.?')
_RE_PISOS_BANOS = re.compile(r'(\d+)\s*baños?')
_RE_PISOS_SQM = re.compile(r'(\d+)\s*m²')
_RE_PISOS_FLOOR = re.compile(r'(\d+)ª?\s*planta')


def _parse_pisos_listings(markdown: str) -> list[dict]:
    """Extract property listings from Firecrawl markdown of a Pisos.com page."""
    listings: list[dict] = []

    # Find all title links to pisos.com/comprar/
    for title_match in _RE_PISOS_TITLE.finditer(markdown):
        title_text = title_match.group(1).strip()
        url = title_match.group(2).strip()

        # Skip non-listing links (images etc. also have pisos.com URLs)
        if '/comprar/' not in url:
            continue

        # Get context: 200 chars before (for price) and 400 chars after (for features)
        start = title_match.start()
        end = title_match.end()
        context_before = markdown[max(0, start - 200):start]
        context_after = markdown[end:end + 400]

        # Price: look for N.NNN.NNN € in the lines before the title
        price_match = _RE_PRICE.search(context_before)
        asking_price = None
        if price_match:
            price_str = price_match.group(1).replace('.', '')
            try:
                asking_price = float(price_str)
            except ValueError:
                pass

        # District: first line after the title link
        district_match = _RE_PISOS_DISTRICT.search(context_after)
        zone = district_match.group(1).strip() if district_match else None
        district = district_match.group(2).strip() if district_match else None

        # Features from the lines after the title
        habs = _RE_PISOS_HABS.search(context_after)
        banos = _RE_PISOS_BANOS.search(context_after)
        sqm = _RE_PISOS_SQM.search(context_after)
        floor = _RE_PISOS_FLOOR.search(context_after)

        # Property type from the title text ("Piso en ...", "Casa en ...", "Ático en ...")
        prop_type = "piso"
        title_lower = title_text.lower()
        if "casa" in title_lower or "chalet" in title_lower:
            prop_type = "casa"
        elif "ático" in title_lower or "atico" in title_lower:
            prop_type = "ático"
        elif "estudio" in title_lower:
            prop_type = "estudio"
        elif "dúplex" in title_lower or "duplex" in title_lower:
            prop_type = "dúplex"

        # Address from the title: "Piso en calle Gaztambide" → "calle Gaztambide"
        address = title_text
        for prefix in ("Piso en ", "Casa en ", "Ático en ", "Estudio en ", "Dúplex en ", "Chalet en "):
            if title_text.startswith(prefix):
                address = title_text[len(prefix):]
                break

        listing = {
            "url": url,
            "address": address,
            "district": district,
            "zone": zone,
            "city": "Madrid",
            "country": "Spain",
            "property_type": prop_type,
            "asking_price": asking_price,
            "currency": "EUR",
            "size_sqm": float(sqm.group(1)) if sqm else None,
            "bedrooms": int(habs.group(1)) if habs else None,
            "bathrooms": int(banos.group(1)) if banos else None,
            "floor": int(floor.group(1)) if floor else None,
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
        listings.append(listing)

    return listings


def scrape_pisos_firecrawl(
    operation: str = "venta",
    max_pages: int = 3,
    page_from: int = 1,
) -> list[dict]:
    """
    Scrape Pisos.com Madrid listings via Firecrawl.

    ~10,500 listings available, 30 per page.
    Pagination: https://www.pisos.com/venta/pisos-madrid/{page}/

    Returns a list of normalised deal dicts.
    """
    api_key = settings.FIRECRAWL_API_KEY
    if not api_key:
        logger.error("FIRECRAWL_API_KEY not configured.")
        return []

    fc = Firecrawl(api_key=api_key)
    listings: list[dict] = []

    for page in range(page_from, page_from + max_pages):
        # Page 1 has no number in URL
        if page == 1:
            url = f"{PISOS_BASE}/{operation}/pisos-madrid/"
        else:
            url = PISOS_SEARCH_TPL.format(
                base=PISOS_BASE, operation=operation, page=page,
            )
        logger.info("Pisos.com: scraping page %d — %s", page, url)

        try:
            result = fc.scrape(
                url,
                location={"country": "ES"},
                wait_for=5000,
                remove_base64_images=True,
            )
            md = result.markdown or ""
        except Exception as exc:
            logger.error("Pisos.com Firecrawl error on page %d: %s", page, exc)
            break

        if not md or len(md) < 500:
            logger.warning("Pisos.com: empty/blocked page %d (%d chars).", page, len(md))
            break

        page_listings = _parse_pisos_listings(md)
        listings.extend(page_listings)
        logger.info(
            "Pisos.com page %d — %d listings (total: %d)",
            page, len(page_listings), len(listings),
        )

        if not page_listings:
            logger.info("Pisos.com: no listings found on page %d — stopping.", page)
            break

        time.sleep(1.5 + random.uniform(0, 0.5))

    return listings

# ---------------------------------------------------------------------------
# DB ingestion
# ---------------------------------------------------------------------------

def ingest_listings(db: Session, listings: list[dict]) -> int:
    """
    Upsert listings into the deals table by URL.

    On conflict (same URL already exists):
      - Fields that might have been null due to data quality issues
        (size_sqm, bedrooms, bathrooms, etc.) use COALESCE — the new
        non-null value wins, but an existing good value is never overwritten
        by a new null.
      - asking_price is always overwritten with the latest scraped price.

    Returns the count of genuinely new rows inserted (not updates).
    """
    # Fields where we prefer the new value but never overwrite existing with null
    COALESCE_FIELDS = [
        "size_sqm", "bedrooms", "bathrooms", "floor",
        "district", "zone", "address", "condition", "orientation",
        "broker_name", "broker_contact", "listed_date", "property_type",
    ]
    # Fields always overwritten with the latest scraped value
    OVERWRITE_FIELDS = [
        "asking_price", "storage_room", "terrace", "balcony",
        "elevator", "garage",
    ]

    # Normalise district names to Madrid's 21 canonical districts
    for d in listings:
        d["district"] = normalize_district(d.get("district"))

    # Filter: require URL, asking_price, size_sqm, and a canonical Madrid district
    valid = [
        d for d in listings
        if d.get("url")
        and d.get("asking_price")
        and d.get("size_sqm")
        and d.get("district") in CANONICAL_DISTRICTS
    ]
    skipped = len(listings) - len(valid)
    if skipped:
        logger.info(
            "Skipped %d listings (missing url/price/size or outside Madrid city).",
            skipped,
        )

    # Check which URLs already exist so we can count true inserts
    all_urls = [d["url"] for d in valid]
    existing_urls = {
        row[0]
        for row in db.query(Deal.url).filter(Deal.url.in_(all_urls)).all()
    }

    for data in valid:
        row = {k: v for k, v in data.items() if hasattr(Deal, k)}
        stmt = pg_insert(Deal).values(**row)

        update_set = {}
        for f in COALESCE_FIELDS:
            if f in row:
                update_set[f] = func.coalesce(getattr(stmt.excluded, f), getattr(Deal, f))
        for f in OVERWRITE_FIELDS:
            if f in row:
                update_set[f] = getattr(stmt.excluded, f)

        stmt = stmt.on_conflict_do_update(index_elements=["url"], set_=update_set)
        try:
            db.execute(stmt)
        except Exception as exc:
            db.rollback()
            logger.error("Failed to upsert deal %s: %s", data.get("url"), exc)

    db.commit()

    inserted = sum(1 for d in valid if d["url"] not in existing_urls)
    updated = len(valid) - inserted
    logger.info(
        "Upserted %d listings: %d new, %d updated.",
        len(valid), inserted, updated,
    )
    return inserted
