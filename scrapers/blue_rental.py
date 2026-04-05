"""
Blue Car Rental (your own fleet) — scrapes live prices directly from
bluecarrental.is via the Caren rental management system API so you can
verify that the prices displayed on your website match your internal system.

Falls back to the FLEET mock data if the live request fails for any reason.
"""

from datetime import datetime
from .base import BaseScraper


# Caren location IDs for Blue Car Rental pickup / drop-off points.
# Only KEF and Reykjavik are supported; other locations fall back to mock data.
_LOCATION_IDS: dict[str, tuple[int, int]] = {
    "Keflavik Airport": (44, 418),
    "Reykjavik":        (51, 419),
}

# Map first ACRISS category letter → rental category
# Used only when a model name can't be matched to the FLEET dict.
_ACRISS_CATEGORY: dict[str, str] = {
    "M": "Economy",   # Mini
    "N": "Economy",   # Mini Elite
    "E": "Economy",   # Economy
    "H": "Economy",   # Economy Elite
    "C": "Compact",   # Compact
    "D": "Compact",   # Compact Elite
    "I": "Compact",   # Intermediate
    "J": "Compact",   # Intermediate Elite
    "S": "SUV",       # Standard
    "R": "SUV",       # Standard Elite
    "F": "SUV",       # Fullsize
    "G": "SUV",       # Fullsize Elite
    "P": "SUV",       # Premium
    "U": "SUV",       # Premium Elite
    "L": "SUV",       # Luxury
    "W": "SUV",       # Luxury Elite
    "O": "SUV",       # Oversize
    "X": "Economy",   # Special
}

# Keywords in the model name that identify minivans / large vans
_MINIVAN_KEYWORDS = ("trafic", "proace", "sprinter", "transit", "van")


class BlueCarRentalScraper(BaseScraper):
    competitor_name = "Blue Car Rental"
    base_url = "https://www.bluecarrental.is"
    FLEET = {
        "Economy": [
            {"model": "Toyota Aygo",              "price_range": (7500,  7500)},
            {"model": "Kia Rio",                  "price_range": (8000,  8000)},
            {"model": "Toyota Yaris",             "price_range": (9000,  9000)},
            {"model": "Kia Ceed",                 "price_range": (10000, 10000)},
            {"model": "Opel Corsa Electric",      "price_range": (10000, 10000)},
            {"model": "Tesla Model 3",            "price_range": (11000, 11000)},
            {"model": "BYD Dolphin",              "price_range": (9500,  9500)},
            {"model": "Kia EV3",                  "price_range": (10500, 10500)},
            {"model": "Smart #5",                 "price_range": (12000, 12000)},
        ],
        "Compact": [
            {"model": "Kia Stonic",            "price_range": (11000, 11000)},
            {"model": "Kia XCeed",             "price_range": (12000, 12000)},
            {"model": "Kia Ceed Sportswagon",  "price_range": (11500, 11500)},
            {"model": "Dacia Jogger",          "price_range": (10500, 10500)},
        ],
        "SUV": [
            {"model": "Dacia Duster",    "price_range": (14500, 14500)},
            {"model": "Dacia Bigster",   "price_range": (16000, 16000)},
            {"model": "Suzuki Vitara",   "price_range": (15000, 15000)},
            {"model": "Suzuki Jimny",    "price_range": (14000, 14000)},
            {"model": "Jeep Renegade",   "price_range": (16500, 16500)},
            {"model": "Hyundai Tucson",  "price_range": (17000, 17000)},
            {"model": "Kia Sportage",    "price_range": (17500, 17500)},
            {"model": "Toyota RAV4",     "price_range": (19000, 19000)},
            {"model": "Tesla Model Y",   "price_range": (22000, 22000)},
            {"model": "Kia EV6",         "price_range": (21000, 21000)},
            {"model": "MG ZS",           "price_range": (14000, 14000)},
        ],
        "4x4": [
            {"model": "Kia Sorento",               "price_range": (22000, 22000)},
            {"model": "Nissan X-Trail",            "price_range": (22000, 22000)},
            {"model": "Hyundai Santa Fe",          "price_range": (24000, 24000)},
            {"model": "Toyota Land Cruiser 150",   "price_range": (27000, 27000)},
            {"model": "Toyota Land Cruiser 250",   "price_range": (32000, 32000)},
            {"model": "Land Rover Discovery Sport","price_range": (25000, 25000)},
            {"model": "Land Rover Discovery",      "price_range": (30000, 30000)},
            {"model": "Land Rover Defender",       "price_range": (33000, 33000)},
            {"model": "Jeep Wrangler",             "price_range": (29000, 29000)},
            {"model": "Toyota Highlander",         "price_range": (26000, 26000)},
        ],
        "Minivan": [
            {"model": "Renault Trafic",    "price_range": (20000, 20000)},
            {"model": "Toyota Proace",     "price_range": (23000, 23000)},
            {"model": "Mercedes Sprinter", "price_range": (30000, 30000)},
        ],
    }

    # -----------------------------------------------------------------
    # Internal helpers
    # -----------------------------------------------------------------

    def _build_name_lookup(self) -> dict[str, str]:
        """
        Return a dict of {lowercase_model_name: category} built from FLEET.
        Used for fast exact-name matching against Caren API responses.
        """
        lookup: dict[str, str] = {}
        for category, cars in self.FLEET.items():
            for car in cars:
                lookup[car["model"].lower()] = category
        return lookup

    def _infer_category(
        self,
        name: str,
        acriss: str,
        for_highland: bool,
        drive_name: str,
        name_lookup: dict[str, str],
    ) -> str:
        """
        Infer rental category for a car returned by the Caren API.

        Priority order:
        1. Exact model-name match in FLEET lookup
        2. Substring match (e.g. "Toyota Land Cruiser 150" ⊇ "land cruiser")
        3. Minivan keyword in name
        4. Highland flag or 4WD drive type  →  4x4
        5. ACRISS first letter fallback
        """
        name_lower = name.lower()

        # 1. Exact match
        if name_lower in name_lookup:
            return name_lookup[name_lower]

        # 2. Substring match – check each FLEET model name against the Caren name
        for model_lower, category in name_lookup.items():
            # Match if either string is a substring of the other
            if model_lower in name_lower or name_lower in model_lower:
                return category

        # 3. Minivan keywords
        if any(kw in name_lower for kw in _MINIVAN_KEYWORDS):
            return "Minivan"

        # 4. 4x4 / Highland flag
        if for_highland or "4wd" in (drive_name or "").lower() or "awd" in (drive_name or "").lower():
            return "4x4"

        # 5. ACRISS fallback (use first letter of the code)
        if acriss:
            return _ACRISS_CATEGORY.get(acriss[0].upper(), "Economy")

        return "Economy"

    # -----------------------------------------------------------------
    # Live scraper
    # -----------------------------------------------------------------

    async def scrape_rates(self, location: str, pickup_date: str, return_date: str) -> list[dict]:
        """
        Fetch live prices from the Caren booking system at bluecarrental.is.

        Supported locations: "Keflavik Airport", "Reykjavik"
        All other locations raise NotImplementedError so the caller falls back
        to mock data for that location.

        pickup_date / return_date must be ISO-format strings: "YYYY-MM-DD"
        """
        if location not in _LOCATION_IDS:
            # Akureyri, Egilsstaðir etc. — no live data available
            raise NotImplementedError(f"No live data for location: {location}")

        pickup_id, dropoff_id = _LOCATION_IDS[location]

        # Caren expects "YYYY-MM-DD HH:MM"
        date_from = f"{pickup_date} 12:00"
        date_to   = f"{return_date} 12:00"

        params = {
            "dateFrom":          date_from,
            "dateTo":            date_to,
            "pickupLocationId":  pickup_id,
            "dropoffLocationId": dropoff_id,
            "ClassIds":          "",
            "showGroupNames":    "false",
            "showImages":        "false",
            "showAll":           "false",
            "language":          "en",
        }

        resp = await self.client.get(
            f"{self.base_url}/_carenapix/class/",
            params=params,
        )
        resp.raise_for_status()
        payload = resp.json()

        # Caren wraps the list in {"Classes": [...]}
        if isinstance(payload, dict):
            cars: list[dict] = payload.get("Classes", [])
        elif isinstance(payload, list):
            cars = payload
        else:
            raise ValueError(f"Unexpected Caren response type: {type(payload)}")

        name_lookup = self._build_name_lookup()
        now = datetime.utcnow().isoformat()
        rates: list[dict] = []

        for car in cars:
            # Skip unavailable cars
            if not car.get("Available", False):
                continue

            total_price = car.get("TotalPrice") or 0
            if total_price <= 0:
                continue

            name      = car.get("Name", "Unknown")
            acriss    = car.get("ACRISS", "") or ""
            highland  = bool(car.get("ForHighland", False))
            drive     = car.get("DriveName", "") or ""

            category = self._infer_category(name, acriss, highland, drive, name_lookup)

            rates.append({
                "competitor":      self.competitor_name,
                "location":        location,
                "pickup_date":     pickup_date,
                "return_date":     return_date,
                "car_category":    category,
                "car_model":       name,
                "canonical_name":  name,
                "price_isk":       round(total_price),
                "currency":        car.get("Currency", "ISK"),
                "scraped_at":      now,
            })

        return rates
