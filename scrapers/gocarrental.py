"""
Scraper for Go Car Rental Iceland (gocarrental.is).
Uses the GoRentals JSON API: POST https://api.gorentals.is/functions/v1/public/classes
Returns total-trip prices by class ID. Car names come from the SSR page HTML.
"""

from __future__ import annotations

import re
from datetime import datetime

from bs4 import BeautifulSoup

from .base import BaseScraper
from canonical import canonicalize


# Go Car Rental only operates in the Reykjavik/KEF area.
GOCAR_LOCATION_IDS: dict[str, tuple[int, int] | None] = {
    # (pickupLocationId, dropoffLocationId)
    "Keflavik Airport": (10, 11),
    "Reykjavik":        (614, 614),
}

GOCAR_API_URL = "https://api.gorentals.is/functions/v1/public/classes"
GOCAR_SANITY_URL = "https://a4mln02c.api.sanity.io/v2022-03-07/data/query/production"
GOCAR_SANITY_QUERY = (
    '*[_type == "carenVehicleBase" && defined(model)]{'
    'id, model, "brand": brand->title[_key=="en"][0].value,'
    '"category": primaryCategory->title[_key=="en"][0].value}'
)

# Keyword-based category inference from car model name
_ECONOMY_KEYWORDS = ["aygo", "yaris", "swift", "i10", "clio", "ceed"]
_COMPACT_KEYWORDS = ["captur", "megane", "octavia", "sportswagon", "ceed wagon",
                     "jogger", "model 3"]
_SUV_KEYWORDS     = ["duster", "jimny", "vitara", "qashqai", "tucson", "sportage",
                     "rav4", "x-trail", "forester", "eclipse", "kodiaq", "ariya",
                     "subaru xv", "model y", "cr-v", "honda cr", "mg ehs", "mg "]
_4X4_KEYWORDS     = ["santa fe", "sorento", "discovery", "bmw x", "land cruiser",
                     "defender", "wrangler", "jeep"]
_MINIVAN_KEYWORDS = ["trafic", "caravelle", "vito", "proace", "tourneo", "transit"]


def _infer_category(name: str) -> str:
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
    for kw in _ECONOMY_KEYWORDS:
        if kw in n:
            return "Economy"
    return "Economy"


class GoCarRentalScraper(BaseScraper):
    competitor_name = "Go Car Rental"
    base_url = "https://www.gocarrental.is"
    FLEET = {
        "Economy": [
            {"model": "Hyundai i10",    "price_range": (7000,  9500)},
            {"model": "Renault Clio",   "price_range": (7500,  10000)},
            {"model": "Toyota Yaris",   "price_range": (8000,  11000)},
            {"model": "Suzuki Swift",   "price_range": (8000,  11000)},
            {"model": "Kia Ceed",       "price_range": (8500,  11500)},
        ],
        "Compact": [
            {"model": "Renault Captur",       "price_range": (9000,  12500)},
            {"model": "Kia Ceed Wagon",       "canonical_name": "Kia Ceed Sportswagon", "price_range": (10000, 13500)},
            {"model": "Renault Megane Wagon", "canonical_name": "Renault Megane",        "price_range": (10000, 13500)},
            {"model": "Skoda Octavia Wagon",  "canonical_name": "Skoda Octavia Wagon",   "price_range": (11000, 15000)},
        ],
        "SUV": [
            {"model": "Dacia Duster",          "price_range": (12000, 16000)},
            {"model": "Suzuki Jimny",          "price_range": (12500, 16500)},
            {"model": "Subaru XV",             "price_range": (13000, 17000)},
            {"model": "Nissan Qashqai",        "price_range": (13500, 17500)},
            {"model": "Suzuki Vitara",         "price_range": (13500, 18000)},
            {"model": "Mitsubishi Eclipse Cross", "price_range": (13500, 17500)},
            {"model": "Kia Sportage",          "price_range": (14000, 18500)},
            {"model": "Hyundai Tucson",        "price_range": (14500, 19000)},
            {"model": "Skoda Kodiaq",          "price_range": (15000, 20000)},
            {"model": "Toyota RAV4",           "price_range": (16000, 21000)},
            {"model": "Nissan X-Trail",        "price_range": (15500, 20000)},
            {"model": "Nissan Ariya",          "price_range": (18000, 23000)},
            {"model": "Subaru Forester",       "price_range": (15000, 20000)},
        ],
        "4x4": [
            {"model": "Hyundai Santa Fe",         "price_range": (20000, 27000)},
            {"model": "Kia Sorento",              "price_range": (21000, 28000)},
            {"model": "Land Rover Discovery Sport","price_range": (24000, 32000)},
            {"model": "BMW X3",                   "price_range": (24000, 32000)},
            {"model": "Toyota Land Cruiser",      "canonical_name": "Toyota Land Cruiser 150", "price_range": (25000, 34000)},
            {"model": "Jeep Wrangler Rubicon",    "canonical_name": "Jeep Wrangler",           "price_range": (28000, 37000)},
            {"model": "Land Rover Defender",      "price_range": (30000, 40000)},
        ],
        "Minivan": [
            {"model": "Dacia Jogger",         "price_range": (11000, 15000)},
            {"model": "Renault Trafic",       "price_range": (20000, 27000)},
            {"model": "Volkswagen Caravelle", "canonical_name": "VW Caravelle", "price_range": (24000, 33000)},
        ],
    }

    async def _get_class_info(self) -> dict[int, tuple[str, str]]:
        """
        Query the public Sanity CMS to build class-ID → (car name, category) mapping.
        Sanity stores carenVehicleBase records with the Caren class ID and brand/model.
        """
        resp = await self.get_with_retry(GOCAR_SANITY_URL, params={"query": GOCAR_SANITY_QUERY})
        resp.raise_for_status()
        items = resp.json().get("result", [])

        mapping: dict[int, tuple[str, str]] = {}
        for item in items:
            id_ = item.get("id")
            brand = item.get("brand") or ""
            model = item.get("model") or ""
            name = f"{brand} {model}".strip()
            if not id_ or not name:
                continue
            sanity_cat = item.get("category") or ""
            # Derive category — use keyword inference for "Large SUV" (could be SUV or 4x4)
            if sanity_cat == "4x4 / F-Road":
                cat = "4x4"
            elif sanity_cat == "Minivan":
                cat = "Minivan"
            elif sanity_cat in ("Small",):
                cat = "Economy"
            elif sanity_cat in ("Family", "Compact"):
                cat = "Compact"
            else:
                cat = _infer_category(name)
            # Prefer entries that have a defined category
            if id_ not in mapping or sanity_cat:
                mapping[id_] = (name, cat)
        return mapping

    async def scrape_rates(self, location: str, pickup_date: str, return_date: str) -> list[dict]:
        """
        Call the GoRentals JSON API and return pricing for all available vehicle classes.
        """
        loc = GOCAR_LOCATION_IDS.get(location)
        if loc is None:
            return []  # Location not served

        pickup_id, dropoff_id = loc

        # Format dates: "YYYY-MM-DD HH:MM"
        pickup_str = f"{pickup_date} 12:00"
        return_str = f"{return_date} 12:00"

        payload = {
            "rentalId":         7,
            "tenant":           "gocarrental",
            "ref":              "",
            "currency":         "ISK",
            "language":         "en",
            "dateFrom":         pickup_str,
            "dateTo":           return_str,
            "pickupLocationId": pickup_id,
            "dropoffLocationId": dropoff_id,
            "couponCode":       "",
        }

        response = await self.post_with_retry(
            GOCAR_API_URL,
            json=payload,
            headers={**dict(self.client.headers), "Content-Type": "application/json"},
        )
        response.raise_for_status()
        classes = response.json()

        # Get class ID → (car name, category) from Sanity CMS
        try:
            class_info = await self._get_class_info()
        except Exception:
            class_info = {}

        now = datetime.utcnow().isoformat()
        results = []

        for cls in classes:
            if not cls.get("available", True):
                continue
            class_id = cls.get("id")
            price_data = cls.get("price", {})
            price_isk = price_data.get("regular") or price_data.get("discount")
            if not price_isk:
                continue

            name, category = class_info.get(class_id, (f"Class {class_id}", "Economy"))

            results.append({
                "competitor":    self.competitor_name,
                "location":      location,
                "pickup_date":   pickup_date,
                "return_date":   return_date,
                "car_category":  category,
                "car_model":     name,
                "canonical_name": canonicalize(name),
                "price_isk":     int(price_isk),
                "currency":      "ISK",
                "scraped_at":    now,
            })

        return results
