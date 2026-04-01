"""
Scraper for Hertz Iceland (hertz.is).
Uses WordPress/CarCloud theme.
Flow: GET homepage → extract nonce → POST to wp-admin/admin-ajax.php (ccw_search)
      → GET /?step=search-results → parse server-rendered HTML.
"""

import re
from datetime import datetime

from bs4 import BeautifulSoup

from .base import BaseScraper


# Hertz depot IDs for each canonical location
HERTZ_DEPOT_IDS: dict[str, int | None] = {
    "Keflavik Airport": 926,
    "Reykjavik":        956,   # Reykjavik Downtown
    "Akureyri":         969,   # Akureyri Airport (AEY)
    "Egilsstaðir":      970,   # Egilsstaðir Airport (EGS)
}

# Hertz CSS category classes → our canonical categories
HERTZ_CLASS_CATEGORY: dict[str, str] = {
    "economy":          "Economy",
    "compact":          "Compact",
    "intermediate":     "Compact",
    "suv":              "SUV",
    "luxury":           "4x4",
    "special-vehicles": "4x4",
    "passengervans":    "Minivan",
    "green-collection": "Economy",
}


class HertzIsScraper(BaseScraper):
    competitor_name = "Hertz Iceland"
    base_url = "https://www.hertz.is"
    FLEET = {
        "Economy": [
            {"model": "Toyota Aygo",   "price_range": (8000,  11000)},
            {"model": "Toyota Yaris",  "price_range": (9000,  12500)},
            {"model": "Hyundai i10",   "price_range": (8500,  11500)},
            {"model": "Tesla Model 3", "canonical_name": "Tesla Model 3", "price_range": (14000, 19000)},
        ],
        "Compact": [
            {"model": "Toyota Corolla",      "price_range": (11500, 15500)},
            {"model": "Hyundai i30 Wagon",   "canonical_name": "Hyundai i30",    "price_range": (11000, 15000)},
            {"model": "Toyota Corolla Wagon","canonical_name": "Toyota Corolla",  "price_range": (12000, 16000)},
            {"model": "Skoda Octavia Wagon", "canonical_name": "Skoda Octavia",   "price_range": (11500, 15500)},
            {"model": "Mazda CX-30",         "price_range": (12000, 16000)},
            {"model": "Renault Captur",      "price_range": (11000, 15000)},
        ],
        "SUV": [
            {"model": "Dacia Bigster",   "price_range": (16000, 21000)},
            {"model": "Hyundai Tucson",  "price_range": (17000, 23000)},
            {"model": "Tesla Model Y",   "price_range": (21000, 28000)},
            {"model": "Nissan Ariya",    "price_range": (22000, 29000)},
        ],
        "4x4": [
            {"model": "Kia Sorento",              "price_range": (23000, 30000)},
            {"model": "Toyota Land Cruiser 250",  "price_range": (30000, 40000)},
            {"model": "Land Rover Discovery Sport","price_range": (26000, 35000)},
            {"model": "Land Rover Defender",      "price_range": (32000, 43000)},
            {"model": "BMW X3",                   "price_range": (28000, 37000)},
            {"model": "BMW X5",                   "price_range": (35000, 46000)},
            {"model": "Range Rover Sport",        "price_range": (40000, 55000)},
            {"model": "Mercedes GLE",             "canonical_name": "Mercedes GLE", "price_range": (38000, 50000)},
        ],
        "Minivan": [
            {"model": "VW Caravelle", "price_range": (24000, 33000)},
        ],
    }

    async def _get_nonce(self) -> str:
        """Fetch the homepage and extract the nonce from wp_ccw JS object."""
        resp = await self.client.get(self.base_url + "/")
        resp.raise_for_status()
        m = re.search(r'"nonce"\s*:\s*"([a-f0-9]+)"', resp.text)
        return m.group(1) if m else ""

    def _get_category(self, mix_el) -> str:
        """Derive our category from the CSS classes on the .mix element."""
        for cls in mix_el.get("class", []):
            if cls in HERTZ_CLASS_CATEGORY:
                return HERTZ_CLASS_CATEGORY[cls]
        return "Economy"

    async def scrape_rates(self, location: str, pickup_date: str, return_date: str) -> list[dict]:
        """
        1. GET homepage → extract nonce
        2. POST to admin-ajax.php with ccw_search action (sets session)
        3. GET /?step=search-results → parse 40+ server-rendered vehicle cards
        """
        depot_id = HERTZ_DEPOT_IDS.get(location)
        if depot_id is None:
            return []

        nonce = await self._get_nonce()

        # Hertz date format: YYYYMMDD + HHMM concatenated (e.g. "202607151200")
        pickup_dt = datetime.strptime(pickup_date, "%Y-%m-%d")
        return_dt = datetime.strptime(return_date, "%Y-%m-%d")
        pickup_str = pickup_dt.strftime("%Y%m%d") + "1200"
        return_str = return_dt.strftime("%Y%m%d") + "1200"

        ajax_data = {
            "action":                "ccw_search",
            "nonce":                 nonce,
            "pickupDepotId":         str(depot_id),
            "returnDepotId":         str(depot_id),
            "driverAge":             "25",
            "pickupDate":            pickup_str,
            "returnDate":            return_str,
            "vehicleType":           "passenger",
            "promoCode":             "",
            "promoPin":              "",
            "partner":               "",
            "otherMembershipId":     "",
            "otherMembershipProgram": "",
            "purchaseOrderNumber":   "",
            "audience":              "",
            "duration":              "",
        }

        ajax_resp = await self.client.post(
            f"{self.base_url}/wp-admin/admin-ajax.php",
            data=ajax_data,
            headers={"Referer": self.base_url + "/"},
        )
        ajax_resp.raise_for_status()
        ajax_json = ajax_resp.json()
        if not ajax_json.get("success"):
            raise RuntimeError(f"Hertz ajax failed: {ajax_json.get('message','')}")

        # Fetch the results page (session now has search state)
        results_resp = await self.client.get(
            f"{self.base_url}/?step=search-results",
            headers={"Referer": self.base_url + "/"},
        )
        results_resp.raise_for_status()
        soup = BeautifulSoup(results_resp.text, "lxml")

        now = datetime.utcnow().isoformat()
        results = []

        for mix in soup.select(".mix[data-price]"):
            price_attr = mix.get("data-price")
            try:
                price_isk = int(price_attr)
            except (ValueError, TypeError):
                continue
            if price_isk <= 0:
                continue

            name_el = (
                mix.select_one(".vehicle__p strong")
                or mix.select_one("strong")
            )
            raw_name = name_el.get_text(strip=True) if name_el else "Unknown"
            # Strip "or similar| Manual | 4×4" suffix
            car_name = re.split(r"\s*\||\s+or similar", raw_name)[0].strip()

            category = self._get_category(mix)

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
