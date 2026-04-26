"""
Scraper for Go Iceland car rental (goiceland.com).

Uses a Cloudflare Workers REST API discovered via static bundle analysis:
  Base: https://goiceland-backend.orn-d86.workers.dev

Single-step flow
────────────────
GET /vehicles?pickupDate=YYYY-MM-DD HH:MM&pickupLocation=4&dropoffDate=...&dropoffLocation=4

The response is a list of vehicle objects that already contain full trip
pricing in the `totalPrice` field — no second API call is needed.

Confirmed in live testing (2026-04-21): 32 vehicles returned, prices in ISK.

Location IDs (from JS bundle):
  4 = Keflavik Airport

Go Iceland operates from Keflavik Airport only. Reykjavik is not supported.
"""

from __future__ import annotations

import re
from datetime import datetime

from .base import BaseScraper
from canonical import canonicalize


GOICELAND_API_BASE = "https://goiceland-backend.orn-d86.workers.dev"

GOICELAND_LOCATION_IDS: dict[str, int | None] = {
    "Keflavik Airport": 4,
}

# ACRISS first letter → category (same mapping as blue_rental.py)
_ACRISS_CATEGORY: dict[str, str] = {
    "M": "Economy",   "N": "Economy",   "E": "Economy",   "H": "Economy",
    "C": "Compact",   "D": "Compact",   "I": "Compact",   "J": "Compact",
    "S": "SUV",       "R": "SUV",       "F": "SUV",       "G": "SUV",
    "P": "SUV",       "U": "SUV",       "L": "SUV",       "W": "SUV",
    "X": "Economy",   "O": "SUV",
}

_4X4_KW     = ["santa fe", "sorento", "discovery", "land cruiser", "defender",
               "wrangler", "jeep", "highlander", "hilux", "bmw x"]
_MINIVAN_KW = ["trafic", "caravelle", "vito", "proace", "tourneo", "transit",
               "transporter", "sprinter", "california", "camper", "motorhome",
               "crosscamp", "doblo", "kangoo", "caddy", "campervan", "bus"]
_SUV_KW     = ["duster", "jimny", "vitara", "s-cross", "s cross", "qashqai",
               "tucson", "sportage", "rav4", "x-trail", "forester", "eclipse",
               "kodiaq", "ariya", "model y", "cr-v", "honda cr", "subaru xv",
               "bigster", "compass", "renegade", "mg ", "tiguan", "t-roc",
               "yaris cross", "cx-30", "cx30", "hyundai ix"]
_COMPACT_KW = ["captur", "megane", "octavia", "ceed wagon", "sportswagon",
               "jogger", "model 3", "corolla", "golf", "leon", "focus",
               "mondeo", "a3", "308", "i20", "clio", "polo"]


def _infer_category(name: str, acriss: str = "", group: str = "", for_highland: bool = False) -> str:
    n = name.lower()

    # 4x4 keyword is highest priority — even within an Economy/Compact ACRISS code
    for kw in _4X4_KW:
        if kw in n:
            return "4x4"
    for kw in _MINIVAN_KW:
        if kw in n:
            return "Minivan"
    # forHighland flag is a good 4x4/SUV signal
    if for_highland:
        for kw in _SUV_KW:
            if kw in n:
                return "4x4"
    for kw in _SUV_KW:
        if kw in n:
            return "SUV"
    for kw in _COMPACT_KW:
        if kw in n:
            return "Compact"
    # Fall back to ACRISS code
    if acriss:
        return _ACRISS_CATEGORY.get(acriss[0].upper(), "Economy")
    return "Economy"


class GoIcelandScraper(BaseScraper):
    competitor_name = "Go Iceland"
    base_url = "https://www.goiceland.com"
    FLEET = {
        "Economy": [
            {"model": "Hyundai i10",       "price_range": (7000,  9500)},
            {"model": "Toyota Yaris",      "price_range": (7500,  11000)},
            {"model": "Renault Clio",      "price_range": (7500,  10500)},
            {"model": "Kia Picanto",       "price_range": (7000,  9000)},
        ],
        "Compact": [
            {"model": "Renault Captur",    "price_range": (9000,  13000)},
            {"model": "Toyota Corolla",    "price_range": (9500,  13000)},
            {"model": "VW Golf",           "price_range": (10000, 14000)},
        ],
        "SUV": [
            {"model": "Dacia Duster",      "price_range": (13000, 18000)},
            {"model": "Suzuki Jimny",      "price_range": (13000, 17500)},
            {"model": "Suzuki Vitara",     "price_range": (14000, 19000)},
            {"model": "Nissan Qashqai",    "price_range": (14000, 19000)},
            {"model": "Hyundai Tucson",    "price_range": (15000, 20000)},
            {"model": "Kia Sportage",      "price_range": (15000, 20500)},
            {"model": "Toyota RAV4",       "price_range": (17000, 23000)},
        ],
        "4x4": [
            {"model": "Kia Sorento",                "price_range": (21000, 28000)},
            {"model": "Hyundai Santa Fe",           "price_range": (21000, 28000)},
            {"model": "Toyota Land Cruiser",
             "canonical_name": "Toyota Land Cruiser 150", "price_range": (25000, 34000)},
            {"model": "Land Rover Defender",        "price_range": (28000, 38000)},
        ],
        "Minivan": [
            {"model": "Renault Trafic",             "price_range": (19000, 27000)},
            {"model": "VW Caravelle",               "price_range": (24000, 33000)},
        ],
    }

    async def scrape_rates(self, location: str, pickup_date: str, return_date: str) -> list[dict]:
        loc_id = GOICELAND_LOCATION_IDS.get(location)
        if loc_id is None:
            return []

        params = {
            "pickupDate":     f"{pickup_date} 12:00",
            "pickupLocation": str(loc_id),
            "dropoffDate":    f"{return_date} 12:00",
            "dropoffLocation": str(loc_id),
        }

        resp = await self.get_with_retry(
            f"{GOICELAND_API_BASE}/vehicles",
            params=params,
            headers={
                **dict(self.client.headers),
                "Origin":  self.base_url,
                "Referer": f"{self.base_url}/",
            },
        )
        resp.raise_for_status()
        vehicles = resp.json()

        now = datetime.utcnow().isoformat()
        results = []

        for v in (vehicles if isinstance(vehicles, list) else []):
            if not v.get("available", True):
                continue

            # totalPrice is already the full trip price in ISK
            price_isk = v.get("totalPrice") or v.get("unitPrice")
            if not price_isk:
                continue

            # Strip "(Manual)" / "(Automatic)" from name
            raw_name = v.get("name") or v.get("title") or ""
            car_name = re.sub(
                r"\s*\((?:manual|automatic|auto)\)\s*$", "", raw_name, flags=re.IGNORECASE
            ).strip()
            if not car_name:
                continue

            acriss = v.get("ACRISS") or ""
            group  = v.get("groupName") or ""
            for_highland = bool(v.get("forHighland", False))
            category = _infer_category(car_name, acriss, group, for_highland)

            results.append({
                "competitor":     self.competitor_name,
                "location":       location,
                "pickup_date":    pickup_date,
                "return_date":    return_date,
                "car_category":   category,
                "car_model":      car_name,
                "canonical_name": canonicalize(car_name),
                "price_isk":      int(price_isk),
                "currency":       "ISK",
                "scraped_at":     now,
            })

        return results
