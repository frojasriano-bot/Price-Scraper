"""
Scraper for Avis Iceland (avis.is / secure.avis.is).
Uses the ABG (Avis Budget Group) global booking platform.
Server-rendered HTML via POST — no JS or API key required.
"""

import re
from datetime import datetime

from bs4 import BeautifulSoup

from .base import BaseScraper


# Avis Iceland location codes (IATA-style 3-char codes)
AVIS_LOCATION_CODES: dict[str, str | None] = {
    "Keflavik Airport": "KEF",
    "Reykjavik":        "RKV",   # Reykjavik Domestic Airport
    "Akureyri":         "AEY",
    "Egilsstaðir":      "EGS",
}

AVIS_RESULTS_URL = "https://secure.avis.is/car-results"

# Avis Iceland category name mapping (Icelandic → English)
# Keyword inference on car model name (more reliable than Icelandic category labels)
_4X4_KEYWORDS     = ["land cruiser", "landcruiser", "defender", "discovery", "4wd",
                      "hilux", "highlander", "sorento", "santa fe", "wrangler"]
_MINIVAN_KEYWORDS = ["transporter", "sprinter", "caravelle", "vito", "trafic",
                     "proace", "tourneo", "transit", "van"]
_SUV_KEYWORDS     = ["jimny", "vitara", "sportage", "tucson", "qashqai", "rav4",
                     "duster", "bigster", "ariya", "model y", "kodiaq", "x-trail",
                     "forester", "cr-v", "renegade", "compass"]
_COMPACT_KEYWORDS = ["golf", "octavia", "i30", "ceed", "megane", "captur", "jogger",
                     "model 3", "leaf", "polo"]


def _infer_category_from_name(name: str) -> str:
    """Classify Avis car from model name — Icelandic category labels are too coarse."""
    n = name.lower()
    for kw in _4X4_KEYWORDS:
        if kw in n:
            return "4x4"
    for kw in _MINIVAN_KEYWORDS:
        if kw in n:
            return "Minivan"
    for kw in _SUV_KEYWORDS:
        if kw in n:
            return "SUV"
    for kw in _COMPACT_KEYWORDS:
        if kw in n:
            return "Compact"
    return "Economy"


def _parse_isk_price(text: str) -> int | None:
    """Parse Icelandic ISK price strings like 'ISK 112.123,00' → 112123.
    Iceland uses '.' as thousands separator and ',' as decimal separator.
    """
    clean = re.sub(r"[Ii][Ss][Kk]|\xa0|\s", "", text)   # strip ISK, nbsp, spaces
    # Remove decimal part (,XX at the end)
    clean = re.sub(r",\d+$", "", clean)
    # Remove thousands dots
    clean = clean.replace(".", "")
    digits = re.findall(r"\d+", clean)
    if digits:
        return int(digits[-1])
    return None


def _classify_category(category_text: str) -> str:
    """Map Avis category label to our canonical category."""
    lower = category_text.lower().strip()
    for key, cat in AVIS_CAT_MAP.items():
        if key in lower:
            return cat
    return "Economy"


class AvisIsScraper(BaseScraper):
    competitor_name = "Avis Iceland"
    base_url = "https://www.avis.is"
    FLEET = {
        "Economy": [
            {"model": "Hyundai i10",  "price_range": (8000,  11000)},
            {"model": "Hyundai i20",  "price_range": (9000,  12000)},
            {"model": "VW Polo",      "price_range": (9000,  12500)},
        ],
        "Compact": [
            {"model": "VW Golf",       "price_range": (11000, 15000)},
            {"model": "Hyundai i30",   "price_range": (11000, 14500)},
            {"model": "Kia Ceed",      "price_range": (10500, 14000)},
            {"model": "Skoda Octavia", "price_range": (12000, 16000)},
        ],
        "SUV": [
            {"model": "Suzuki Vitara",  "price_range": (14000, 19000)},
            {"model": "Kia Sportage",   "price_range": (15500, 21000)},
            {"model": "Hyundai Tucson", "price_range": (16000, 22000)},
        ],
        "4x4": [
            {"model": "Land Rover Discovery Sport", "price_range": (27000, 36000)},
            {"model": "Toyota Land Cruiser",        "canonical_name": "Toyota Land Cruiser 150", "price_range": (28000, 37000)},
            {"model": "Land Rover Discovery",       "price_range": (30000, 40000)},
            {"model": "Land Rover Defender",        "price_range": (33000, 44000)},
        ],
        "Minivan": [
            {"model": "Renault Zoe",   "canonical_name": "Renault Zoe",  "price_range": (10000, 13000)},
            {"model": "Tesla Model Y",                                    "price_range": (21000, 28000)},
        ],
    }

    def _fmt_date(self, iso_date: str) -> str:
        """Convert YYYY-MM-DD → DD/MM/YYYY for Avis form."""
        return datetime.strptime(iso_date, "%Y-%m-%d").strftime("%d/%m/%Y")

    async def scrape_rates(self, location: str, pickup_date: str, return_date: str) -> list[dict]:
        """
        POST to secure.avis.is/car-results and parse server-rendered HTML.
        All ~18 car cards with ISK prices are in the HTML response.
        """
        loc_code = AVIS_LOCATION_CODES.get(location)
        if loc_code is None:
            return []

        pickup_fmt = self._fmt_date(pickup_date)
        return_fmt = self._fmt_date(return_date)

        form_data = {
            "hire-location":      loc_code,
            "hire-search":        location,
            "return-location":    loc_code,
            "return-search":      location,
            "date-from":          pickup_fmt,
            "date-from-display":  pickup_fmt,
            "date-to":            return_fmt,
            "date-to-display":    return_fmt,
            "time-from":          "1200",
            "time-to":            "1200",
            "yds-applicable":     "on",
            "awdcode":            "",
            "vehicleCategory":    "default",
            "templateName":       "AvisBookingFlow:pages/homePageAbg",
        }

        response = await self.client.post(AVIS_RESULTS_URL, data=form_data)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, "lxml")

        now = datetime.utcnow().isoformat()
        results = []

        for vehicle in soup.select(".vehicle"):
            # Category name (Icelandic label like "Lítill")
            cat_el = vehicle.select_one(".vehicle__category")
            # Example model (e.g. "Til dæmis Hyundai i10")
            model_el = vehicle.select_one(".vehicle__note")
            cat_text = cat_el.get_text(strip=True) if cat_el else ""
            model_raw = model_el.get_text(strip=True) if model_el else cat_text
            # Strip Icelandic "Til dæmis" prefix ("For example")
            car_name = re.sub(r"^[Tt]il\s+dæmis\s*", "", model_raw).strip()
            if not car_name:
                car_name = cat_text or "Unknown"

            category = _infer_category_from_name(car_name)

            # Price — take first .vehicle__prices-price (Pay on pickup / higher price)
            price_el = vehicle.select_one(".vehicle__prices-price")
            if not price_el:
                continue
            price_isk = _parse_isk_price(price_el.get_text())
            if not price_isk:
                continue

            results.append({
                "competitor":    self.competitor_name,
                "location":      location,
                "pickup_date":   pickup_date,
                "return_date":   return_date,
                "car_category":  category,
                "car_model":     car_name,
                "canonical_name": car_name,
                "price_isk":     price_isk,
                "currency":      "ISK",
                "scraped_at":    now,
            })

        return results
