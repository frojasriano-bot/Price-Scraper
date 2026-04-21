"""
Scraper for MyCar Iceland (mycar.is).

MyCar uses the Caren rental management platform (confirmed via Content Security
Policy analysis: img-src includes booking.caren.is, and the path
booking.caren.is/mycar/ resolves with a valid 302 redirect).

Two Caren API flavours exist across Iceland operators:
  • /_carenapix/class/   (used by Lotus, Blue)
  • /_plugins/carenapi/class  (used by Lava)

We try the /_carenapix/class/ endpoint first (newer flavour), then fall back
to /_plugins/carenapi/class.  If neither responds with valid JSON the scraper
raises so BaseScraper falls back to mock data.

MyCar only operates at Keflavik Airport (KEF).
Location IDs will be auto-discovered from the API response; if not, we use
showAll=true to get all classes regardless.
"""

from __future__ import annotations

import re
from datetime import datetime

from .base import BaseScraper
from canonical import canonicalize


MYCAR_BASE_URL = "https://www.mycar.is"
MYCAR_API_CANDIDATES = [
    "https://www.mycar.is/_carenapix/class/",
    "https://www.mycar.is/_plugins/carenapi/class",
]

# MyCar only operates at KEF
MYCAR_LOCATIONS: dict[str, bool] = {
    "Keflavik Airport": True,
    "Reykjavik":        False,
}

# Group-name → category (conservative; keyword inference handles the rest)
_GROUP_CATEGORY: dict[str, str] = {
    "Economy":         "Economy",
    "Economy Cars":    "Economy",
    "Small":           "Economy",
    "Small Cars":      "Economy",
    "Compact":         "Compact",
    "Compact Cars":    "Compact",
    "Family":          "Compact",
    "SUV":             "SUV",
    "SUV Cars":        "SUV",
    "4x4":             "4x4",
    "4x4 Cars":        "4x4",
    "Minivan":         "Minivan",
    "Minivans":        "Minivan",
    "Vans":            "Minivan",
    "Large":           "4x4",
    "Luxury":          "4x4",
    "Luxury and Vans": "Minivan",
}

_4X4_KW     = ["land cruiser", "defender", "discovery", "santa fe", "sorento",
               "wrangler", "hilux", "highlander", "bmw x", "amarok"]
_MINIVAN_KW = ["trafic", "caravelle", "vito", "proace", "tourneo", "transit",
               "transporter", "sprinter"]
_SUV_KW     = ["duster", "bigster", "jimny", "vitara", "qashqai", "tucson",
               "sportage", "rav4", "x-trail", "forester", "eclipse", "kodiaq",
               "ariya", "model y", "cr-v", "renegade", "compass", "mg "]
_COMPACT_KW = ["captur", "megane", "octavia", "sportswagon", "jogger", "model 3"]


def _infer_category(name: str, group: str = "") -> str:
    n = name.lower()
    for kw in _4X4_KW:
        if kw in n:
            return "4x4"
    for kw in _MINIVAN_KW:
        if kw in n:
            return "Minivan"
    if group in _GROUP_CATEGORY:
        return _GROUP_CATEGORY[group]
    for kw in _SUV_KW:
        if kw in n:
            return "SUV"
    for kw in _COMPACT_KW:
        if kw in n:
            return "Compact"
    return "Economy"


class MyCarIsScraper(BaseScraper):
    competitor_name = "MyCar"
    base_url = MYCAR_BASE_URL
    FLEET = {
        "Economy": [
            {"model": "Toyota Yaris",        "price_range": (8000,  11500)},
            {"model": "Hyundai i10",         "price_range": (7500,  10000)},
            {"model": "Kia Picanto",         "price_range": (7000,  9500)},
            {"model": "Renault Clio",        "price_range": (8000,  11000)},
            {"model": "Volkswagen Polo",     "price_range": (9000,  12000)},
        ],
        "Compact": [
            {"model": "Renault Captur",      "price_range": (10000, 14000)},
            {"model": "Kia Ceed",            "price_range": (10000, 13500)},
            {"model": "Toyota Corolla",      "price_range": (10500, 14000)},
            {"model": "Dacia Jogger",        "price_range": (9500,  13000)},
        ],
        "SUV": [
            {"model": "Dacia Duster",        "price_range": (13000, 18000)},
            {"model": "Suzuki Jimny",        "price_range": (13500, 18000)},
            {"model": "Suzuki Vitara",       "price_range": (14000, 19000)},
            {"model": "Nissan Qashqai",      "price_range": (14000, 19500)},
            {"model": "Hyundai Tucson",      "price_range": (15000, 20000)},
            {"model": "Kia Sportage",        "price_range": (15500, 21000)},
            {"model": "Toyota RAV4",         "price_range": (17000, 23000)},
        ],
        "4x4": [
            {"model": "Kia Sorento",                    "price_range": (21000, 29000)},
            {"model": "Hyundai Santa Fe",               "price_range": (22000, 30000)},
            {"model": "Toyota Land Cruiser",
             "canonical_name": "Toyota Land Cruiser 150", "price_range": (26000, 35000)},
            {"model": "Land Rover Defender",            "price_range": (29000, 40000)},
        ],
        "Minivan": [
            {"model": "Renault Trafic",                 "price_range": (20000, 28000)},
            {"model": "Volkswagen Caravelle",
             "canonical_name": "VW Caravelle",          "price_range": (25000, 35000)},
        ],
    }

    async def _try_caren_endpoint(
        self,
        api_url: str,
        pickup_date: str,
        return_date: str,
    ) -> list | None:
        """
        Attempt a GET against a candidate Caren API URL.
        Returns the Classes list on success, None on failure.
        Caren showAll=true returns classes even without a locationId filter.
        """
        params = {
            "dateFrom":       f"{pickup_date} 12:00",
            "dateTo":         f"{return_date} 12:00",
            "showGroupNames": "true",
            "showImages":     "false",
            "showAll":        "true",
            "language":       "en",
        }
        try:
            resp = await self.client.get(
                api_url,
                params=params,
                headers={
                    **dict(self.client.headers),
                    "Referer": f"{MYCAR_BASE_URL}/book/",
                    "Accept":  "application/json, text/plain, */*",
                },
                timeout=12,
            )
            if resp.status_code != 200:
                return None
            data = resp.json()
            classes = data.get("Classes") or data.get("classes") or []
            return classes if isinstance(classes, list) else None
        except Exception:
            return None

    async def scrape_rates(self, location: str, pickup_date: str, return_date: str) -> list[dict]:
        if not MYCAR_LOCATIONS.get(location, False):
            return []   # MyCar only operates at KEF

        classes: list | None = None
        for api_url in MYCAR_API_CANDIDATES:
            classes = await self._try_caren_endpoint(api_url, pickup_date, return_date)
            if classes is not None:
                break

        if classes is None:
            raise RuntimeError("MyCar Caren API not reachable — falling back to mock")

        now = datetime.utcnow().isoformat()
        results = []

        for car in classes:
            if not car.get("Available", True):
                continue

            car_name = car.get("Name") or car.get("name") or "Unknown"
            # Strip "(automatic)" / "(manual)" suffixes
            clean_name = re.sub(
                r"\s*\((?:automatic|manual)\)\s*$", "", car_name, flags=re.IGNORECASE
            ).strip()

            group = car.get("GroupName") or car.get("groupName") or ""
            category = _infer_category(car_name, group)

            price_isk = car.get("TotalPrice") or car.get("totalPrice") or car.get("UnitPrice")
            if not price_isk:
                continue

            results.append({
                "competitor":     self.competitor_name,
                "location":       location,
                "pickup_date":    pickup_date,
                "return_date":    return_date,
                "car_category":   category,
                "car_model":      car_name,
                "canonical_name": canonicalize(clean_name),
                "price_isk":      int(price_isk),
                "currency":       "ISK",
                "scraped_at":     now,
            })

        return results
