"""
Scraper for Lotus Car Rental Iceland (lotuscarrental.is).
Uses the Caren booking platform JSON API — direct GET, no auth required.
"""

import re
from datetime import datetime

from .base import BaseScraper


# Lotus only operates at Keflavik Airport.
LOTUS_LOCATION_IDS: dict[str, tuple[int, int] | None] = {
    "Keflavik Airport": (486, 487),
    "Reykjavik":        None,
    "Akureyri":         None,
    "Egilsstaðir":      None,
}

LOTUS_API_URL = "https://www.lotuscarrental.is/_carenapix/class/"

# Lotus group names → our canonical categories
LOTUS_GROUP_CATEGORY: dict[str, str] = {
    "Small":          "Economy",
    "Medium":         "Compact",
    "Large":          "SUV",
    "4x4":            "4x4",
    "Luxury and Vans": "Minivan",
    "Campers":        "Minivan",
}

# Keyword fallback (same logic as Go Car Rental)
_4X4_KEYWORDS     = ["4x4", "highland", "land cruiser", "defender", "sorento",
                      "santa fe", "discovery", "hilux", "highlander", "cr-v", "honda cr"]
_MINIVAN_KEYWORDS = ["van", "caravelle", "vito", "camper", "proace", "trafic"]
_SUV_KEYWORDS     = ["suv", "rav4", "tucson", "sportage", "vitara", "duster",
                      "jimny", "forester", "renegade", "compass", "yaris cross",
                      "lexus", "model y"]
_ECONOMY_KEYWORDS = ["aygo", "yaris", "i10", "sandero", "polo", "swift"]


def _infer_category(name: str, group: str, for_highland: bool, drive: str) -> str:
    if group in LOTUS_GROUP_CATEGORY:
        # Use drive/highland to distinguish SUV from 4x4 within group "Large"
        cat = LOTUS_GROUP_CATEGORY[group]
        if cat == "SUV" and (for_highland or "4wd" in drive.lower() or "awd" in drive.lower()):
            return "4x4"
        return cat
    n = name.lower()
    if for_highland:
        return "4x4"
    for kw in _4X4_KEYWORDS:
        if kw in n:
            return "4x4"
    for kw in _MINIVAN_KEYWORDS:
        if kw in n:
            return "Minivan"
    for kw in _SUV_KEYWORDS:
        if kw in n:
            return "SUV"
    for kw in _ECONOMY_KEYWORDS:
        if kw in n:
            return "Economy"
    return "Compact"


class LotusCarRentalScraper(BaseScraper):
    competitor_name = "Lotus Car Rental"
    base_url = "https://www.lotuscarrental.is"
    FLEET = {
        "Economy": [
            {"model": "Toyota Aygo",  "price_range": (7000,  9500)},
            {"model": "Toyota Yaris", "price_range": (8000,  11000)},
        ],
        "Compact": [
            {"model": "Kia XCeed",        "canonical_name": "Kia XCeed",            "price_range": (10000, 13500)},
            {"model": "Kia Ceed Wagon",   "canonical_name": "Kia Ceed Sportswagon", "price_range": (10500, 14000)},
            {"model": "Tesla Model 3 Long Range 4x4", "canonical_name": "Tesla Model 3", "price_range": (15000, 20000)},
        ],
        "SUV": [
            {"model": "Dacia Duster 4x4",     "canonical_name": "Dacia Duster",    "price_range": (13000, 17000)},
            {"model": "Suzuki Vitara 4x4",    "canonical_name": "Suzuki Vitara",   "price_range": (14000, 18500)},
            {"model": "Suzuki Jimny",                                               "price_range": (13500, 17000)},
            {"model": "Toyota Yaris Cross 4x4","canonical_name": "Toyota Yaris Cross", "price_range": (12000, 16000)},
            {"model": "Jeep Renegade 4x4",    "canonical_name": "Jeep Renegade",   "price_range": (15000, 19500)},
            {"model": "Jeep Compass 4x4",     "canonical_name": "Jeep Compass",    "price_range": (15500, 20000)},
            {"model": "Kia Sportage 4x4",     "canonical_name": "Kia Sportage",    "price_range": (15500, 20000)},
            {"model": "Toyota RAV4 4x4",      "canonical_name": "Toyota RAV4",     "price_range": (17000, 22000)},
            {"model": "Subaru Forester 4x4",  "canonical_name": "Subaru Forester", "price_range": (16000, 21000)},
            {"model": "Lexus UX250H 4x4",     "canonical_name": "Lexus UX",        "price_range": (18000, 24000)},
            {"model": "Tesla Model Y",                                              "price_range": (20000, 26000)},
        ],
        "4x4": [
            {"model": "Honda CR-V 4x4",             "canonical_name": "Honda CR-V",             "price_range": (20000, 26000)},
            {"model": "Kia Sorento 4x4",            "canonical_name": "Kia Sorento",            "price_range": (22000, 29000)},
            {"model": "Toyota Highlander GX 4x4",   "canonical_name": "Toyota Highlander",      "price_range": (24000, 31000)},
            {"model": "Toyota Hilux 4x4",           "canonical_name": "Toyota Hilux",           "price_range": (24000, 32000)},
            {"model": "Toyota Land Cruiser 150 4x4","canonical_name": "Toyota Land Cruiser 150","price_range": (26000, 34000)},
            {"model": "Toyota Land Cruiser 250 4x4","canonical_name": "Toyota Land Cruiser 250","price_range": (31000, 40000)},
            {"model": "Land Rover Discovery",                                                    "price_range": (28000, 37000)},
            {"model": "Land Rover Defender",                                                     "price_range": (30000, 40000)},
        ],
        "Minivan": [
            {"model": "Volkswagen Caravelle 4x4", "canonical_name": "VW Caravelle",  "price_range": (24000, 33000)},
            {"model": "Mercedes Benz Vito",       "canonical_name": "Mercedes Vito", "price_range": (26000, 35000)},
        ],
    }

    async def scrape_rates(self, location: str, pickup_date: str, return_date: str) -> list[dict]:
        """
        Call the Caren API directly. Returns JSON with all cars and ISK prices.
        No authentication or JS execution required.
        """
        loc = LOTUS_LOCATION_IDS.get(location)
        if loc is None:
            return []

        pickup_id, dropoff_id = loc

        params = {
            "dateFrom":         f"{pickup_date} 12:00",
            "dateTo":           f"{return_date} 12:00",
            "pickupLocationId": str(pickup_id),
            "dropoffLocationId": str(dropoff_id),
            "showGroupNames":   "true",
            "showImages":       "false",
            "showAll":          "true",
            "language":         "en",
            "couponCode":       "",
        }

        response = await self.client.get(LOTUS_API_URL, params=params)
        response.raise_for_status()
        data = response.json()

        now = datetime.utcnow().isoformat()
        results = []

        for car in data.get("Classes", []):
            if not car.get("Available", True):
                continue

            car_name = car.get("Name", "Unknown")
            # Strip trailing " (automatic)" / " (manual)" suffixes for canonical name
            canonical = re.sub(r"\s*\((?:automatic|manual)\)\s*$", "", car_name, flags=re.IGNORECASE).strip()

            group = car.get("GroupName", "")
            for_highland = bool(car.get("ForHighland", False))
            drive = car.get("DriveName", "")

            category = _infer_category(car_name, group, for_highland, drive)

            # TotalPrice is the base rental total in ISK (before optional insurance)
            price_isk = car.get("TotalPrice") or car.get("UnitPrice")
            if not price_isk:
                continue

            results.append({
                "competitor":    self.competitor_name,
                "location":      location,
                "pickup_date":   pickup_date,
                "return_date":   return_date,
                "car_category":  category,
                "car_model":     car_name,
                "canonical_name": canonical,
                "price_isk":     int(price_isk),
                "currency":      "ISK",
                "scraped_at":    now,
            })

        return results
