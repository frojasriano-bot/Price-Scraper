"""
Scraper for Lava Car Rental Iceland (lavacarrental.is).
Uses the Caren booking API: GET /_plugins/carenapi/class
No authentication or JS execution required.
"""

import re
from datetime import datetime

from .base import BaseScraper


# Lava only operates at Keflavik Airport.
LAVA_LOCATION_IDS: dict[str, int | None] = {
    "Keflavik Airport": 239,
    "Reykjavik":        None,
    "Akureyri":         None,
    "Egilsstaðir":      None,
}

LAVA_API_URL = "https://www.lavacarrental.is/_plugins/carenapi/class"

# Lava group names → our canonical categories
LAVA_GROUP_CATEGORY: dict[str, str] = {
    "Economy Cars":   "Economy",
    "Economy":        "Economy",
    "Small Cars":     "Economy",
    "SUV":            "SUV",
    "SUV Cars":       "SUV",
    "4x4":            "4x4",
    "4x4 Cars":       "4x4",
    "Minivan":        "Minivan",
    "Minivans":       "Minivan",
    "Vans":           "Minivan",
    "Campervans":     "Minivan",
    "Luxury":         "4x4",
}


def _infer_category(name: str, group: str, for_highland: bool, drive: str) -> str:
    if group in LAVA_GROUP_CATEGORY:
        cat = LAVA_GROUP_CATEGORY[group]
        # Promote to 4x4 if F-road capable
        if cat == "SUV" and (for_highland or "4wd" in drive.lower() or "awd" in drive.lower()):
            return "4x4"
        return cat
    n = name.lower()
    if for_highland:
        return "4x4"
    for kw in ["land cruiser", "defender", "discovery", "sorento", "santa fe",
                "x-trail", "hilux", "highlander", "trafic"]:
        if kw in n:
            return "4x4"
    for kw in ["caravelle", "vito", "proace", "trafic", "campervan"]:
        if kw in n:
            return "Minivan"
    for kw in ["duster", "bigster", "vitara", "jimny", "qashqai", "tucson",
                "sportage", "rav4", "eclipse", "model y", "mg ehs"]:
        if kw in n:
            return "SUV"
    return "Economy"


class LavaCarRentalScraper(BaseScraper):
    competitor_name = "Lava Car Rental"
    base_url = "https://www.lavacarrental.is"
    FLEET = {
        "Economy": [
            {"model": "Toyota Aygo",          "price_range": (7000,  9500)},
            {"model": "Toyota Yaris",         "price_range": (8000,  11000)},
            {"model": "Dacia Sandero Stepway","canonical_name": "Dacia Sandero", "price_range": (8000, 10500)},
            {"model": "Dacia Jogger",         "price_range": (9000,  12000)},
            {"model": "Tesla Model 3",        "price_range": (15000, 20000)},
        ],
        "SUV": [
            {"model": "Dacia Duster",            "price_range": (13000, 17500)},
            {"model": "Dacia Bigster",           "price_range": (15000, 19500)},
            {"model": "Suzuki Vitara",           "price_range": (13500, 18000)},
            {"model": "Suzuki Jimny",            "price_range": (13000, 17000)},
            {"model": "Nissan Qashqai",          "price_range": (14000, 18500)},
            {"model": "Hyundai Tucson",          "price_range": (15000, 20000)},
            {"model": "Kia Sportage",            "price_range": (15000, 20000)},
            {"model": "Toyota RAV4",             "price_range": (17000, 23000)},
            {"model": "Mitsubishi Eclipse Cross","price_range": (14500, 19000)},
            {"model": "MG EHS",                  "price_range": (14000, 19000)},
            {"model": "Tesla Model Y",           "price_range": (20000, 27000)},
        ],
        "4x4": [
            {"model": "Nissan X-Trail",        "price_range": (20000, 26000)},
            {"model": "Kia Sorento",           "price_range": (22000, 29000)},
            {"model": "Hyundai Santa Fe",      "price_range": (22000, 28000)},
            {"model": "Toyota Land Cruiser",   "canonical_name": "Toyota Land Cruiser 150", "price_range": (25000, 33000)},
            {"model": "Toyota Land Cruiser 250","price_range": (30000, 40000)},
            {"model": "Land Rover Defender",   "price_range": (29000, 39000)},
        ],
        "Minivan": [
            {"model": "Renault Trafic", "price_range": (19000, 26000)},
        ],
    }

    async def scrape_rates(self, location: str, pickup_date: str, return_date: str) -> list[dict]:
        """
        Call the Caren API at /_plugins/carenapi/class. Returns JSON with all cars
        and ISK TotalPrice. No authentication or JS required.
        """
        loc_id = LAVA_LOCATION_IDS.get(location)
        if loc_id is None:
            return []

        params = {
            "dateFrom":          f"{pickup_date} 12:00",
            "dateTo":            f"{return_date} 12:00",
            "pickupLocationId":  str(loc_id),
            "dropoffLocationId": str(loc_id),
            "showGroupNames":    "true",
            "showImages":        "false",
            "showAll":           "true",
            "language":          "en",
        }

        response = await self.client.get(
            LAVA_API_URL,
            params=params,
            headers={**dict(self.client.headers), "Referer": f"{self.base_url}/book/cars"},
        )
        response.raise_for_status()
        data = response.json()

        now = datetime.utcnow().isoformat()
        results = []

        for car in data.get("Classes", []):
            if not car.get("Available", True):
                continue

            car_name = car.get("Name", "Unknown")
            # Strip trailing " (automatic)" / " (manual)" suffixes
            canonical = re.sub(r"\s*\((?:automatic|manual)\)\s*$", "", car_name, flags=re.IGNORECASE).strip()

            group = car.get("GroupName", "")
            for_highland = bool(car.get("ForHighland", False))
            drive = car.get("DriveName", "")

            category = _infer_category(car_name, group, for_highland, drive)

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
