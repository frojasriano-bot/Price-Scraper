"""
Scraper for Holdur Car Rental Iceland (holdur.is).
Holdur is the Icelandic trading name for Europcar Iceland.
Uses a server-rendered HTML POST form — no API or JS required.
"""

import re
from datetime import datetime

from bs4 import BeautifulSoup

from .base import BaseScraper


# Holdur station codes and their Icelandic display names
# Format: {canonical_location: (station_code, icelandic_name)}
HOLDUR_STATIONS: dict[str, tuple[str, str] | None] = {
    "Keflavik Airport": ("KEFT01", "Keflavík flugstöð"),
    "Reykjavik":        ("REKC01", "Reykjavík Skútuvogur 8"),
    "Akureyri":         ("AEYC01", "Akureyri Tryggvabraut 12"),
    "Egilsstaðir":      ("EGSC01", "Egilsstaðir Lagarbraut 4"),
}

HOLDUR_RESULTS_URL = "https://www.holdur.is/boka/veldu-bil"

# Holdur vehicleCategoryId values (sent with POST to filter results).
# We request all three separately and tag each result accordingly.
HOLDUR_CATEGORY_PARAMS = [
    ("FO", ["Economy", "Compact"]),   # Fólksbíll = regular cars
    ("JE", ["SUV", "4x4"]),           # Jeppi = 4WD/jeeps
    ("M1", ["Minivan"]),              # Minibus/van
]

# Keyword-based category refinement within each vehicle type
_4X4_KEYWORDS     = ["4x4", "highland", "land cruiser", "defender", "sorento",
                      "santa fe", "discovery", "outlander", "mercedes gle"]
_MINIVAN_KEYWORDS = ["caravelle", "vito", "trafic", "proace", "tourneo", "caddy", "transit"]
_SUV_KEYWORDS     = ["suv", "rav4", "tucson", "sportage", "vitara", "duster", "bigster",
                      "jimny", "forester", "model y", "id.4"]
_COMPACT_KEYWORDS = ["octavia", "jogger", "sportswagon", "ceed", "model 3"]


def _refine_category(name: str, param_cats: list[str]) -> str:
    n = name.lower()
    if "JE" in str(param_cats) or any(c in ["SUV", "4x4"] for c in param_cats):
        for kw in _4X4_KEYWORDS:
            if kw in n:
                return "4x4"
        return "SUV"
    if any(c == "Minivan" for c in param_cats):
        return "Minivan"
    for kw in _COMPACT_KEYWORDS:
        if kw in n:
            return "Compact"
    return "Economy"


class HoldurScraper(BaseScraper):
    competitor_name = "Holdur"
    base_url = "https://www.holdur.is"
    FLEET = {
        "Economy": [
            {"model": "Toyota Aygo",       "price_range": (7500,  10000)},
            {"model": "Toyota Yaris",      "price_range": (8500,  11500)},
            {"model": "Suzuki Swift",      "price_range": (8500,  11500)},
            {"model": "Kia Ceed",          "price_range": (9500,  13000)},
            {"model": "Toyota Yaris Cross","canonical_name": "Toyota Yaris Cross", "price_range": (10000, 13500)},
            {"model": "BYD Dolphin",       "price_range": (9000,  12000)},
            {"model": "Kia EV3",           "price_range": (10000, 13500)},
            {"model": "VW ID.4",           "canonical_name": "VW ID.4", "price_range": (11000, 15000)},
        ],
        "Compact": [
            {"model": "Kia Ceed Sportswagon", "price_range": (10500, 14000)},
            {"model": "Dacia Jogger",          "price_range": (10000, 13500)},
            {"model": "Skoda Octavia Combi",  "canonical_name": "Skoda Octavia", "price_range": (11000, 15000)},
        ],
        "SUV": [
            {"model": "Suzuki Jimny",   "price_range": (13000, 17500)},
            {"model": "Dacia Duster",   "price_range": (13500, 18000)},
            {"model": "Dacia Bigster",  "price_range": (15000, 20000)},
            {"model": "Suzuki Vitara",  "price_range": (14000, 18500)},
            {"model": "Kia Sportage",   "price_range": (15000, 20000)},
            {"model": "Toyota RAV4",    "price_range": (17000, 23000)},
            {"model": "Tesla Model Y",  "price_range": (21000, 28000)},
        ],
        "4x4": [
            {"model": "Mitsubishi Outlander PHEV", "canonical_name": "Mitsubishi Outlander", "price_range": (20000, 27000)},
            {"model": "Kia Sorento",               "price_range": (22000, 29000)},
            {"model": "Toyota Landcruiser 150",    "canonical_name": "Toyota Land Cruiser 150", "price_range": (26000, 34000)},
            {"model": "Toyota Landcruiser 250",    "canonical_name": "Toyota Land Cruiser 250", "price_range": (31000, 41000)},
            {"model": "Mercedes GLE PHEV",         "canonical_name": "Mercedes GLE",            "price_range": (35000, 47000)},
            {"model": "Land Rover Discovery",      "price_range": (29000, 38000)},
            {"model": "Land Rover Defender",       "price_range": (31000, 42000)},
        ],
        "Minivan": [
            {"model": "VW Caddy Maxi",  "price_range": (19000, 26000)},
            {"model": "Ford Tourneo",   "price_range": (20000, 27000)},
            {"model": "Renault Trafic", "price_range": (19000, 25000)},
            {"model": "Toyota Proace",  "price_range": (22000, 29000)},
            {"model": "VW Caravelle",   "price_range": (24000, 32000)},
        ],
    }

    def _fmt_date(self, iso_date: str) -> str:
        """Convert YYYY-MM-DD → DD.MM.YYYY required by Holdur."""
        return datetime.strptime(iso_date, "%Y-%m-%d").strftime("%d.%m.%Y")

    async def _fetch_category(
        self,
        station_code: str,
        station_name: str,
        pickup_date: str,
        return_date: str,
        cat_param: str,
        param_cats: list[str],
        location: str,
        now: str,
    ) -> list[dict]:
        """POST one vehicle category request and parse the results."""
        form_data = {
            "vehicleCategoryId":  cat_param,
            "pickupStationId":    station_code,
            "returnStationId":    station_code,
            "pickupStation":      station_name,
            "sameReturnAsPickup": "1",
            "returnStation":      station_name,
            "pickupDate":         self._fmt_date(pickup_date),
            "pickupTime":         "12:00",
            "returnDate":         self._fmt_date(return_date),
            "returnTime":         "12:00",
            "driverAge":          "26",
            "driverCountry":      "IS",
            "promocode":          "",
            "vehicle":            "",
            "search":             "Leita",
            "step":               "search",
        }
        response = await self.client.post(HOLDUR_RESULTS_URL, data=form_data)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, "lxml")

        results = []
        for entry in soup.select(".vehicle__entry"):
            # Car name
            title_el = entry.select_one(".entry__title")
            car_name = title_el.get_text(strip=True) if title_el else "Unknown"

            # Price — ".price__total" contains e.g. "Samtals ISK 92.425"
            # Icelandic uses period (.) as thousands separator
            price_el = entry.select_one(".price__total")
            if not price_el:
                continue
            price_text = price_el.get_text()
            # Strip dots used as thousands separators, then grab digits
            price_clean = price_text.replace(".", "")
            digits = re.findall(r"\d+", price_clean)
            if not digits:
                continue
            price_isk = int(digits[-1])  # Last number = total ISK amount

            category = _refine_category(car_name, param_cats)

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

    async def scrape_rates(self, location: str, pickup_date: str, return_date: str) -> list[dict]:
        """
        POST to Holdur results page for each vehicle category type.
        Server-rendered HTML — no JS or API needed.
        """
        station_info = HOLDUR_STATIONS.get(location)
        if station_info is None:
            return []
        station, station_name = station_info

        now = datetime.utcnow().isoformat()
        results = []

        for cat_param, param_cats in HOLDUR_CATEGORY_PARAMS:
            try:
                batch = await self._fetch_category(
                    station, station_name, pickup_date, return_date,
                    cat_param, param_cats, location, now,
                )
                results.extend(batch)
            except Exception:
                pass  # If one category fails, continue with others

        return results
