"""
Scraper for Enterprise Iceland (enterprise.is).

Current status: UNREACHABLE
─────────────────────────────
All connection attempts to enterprise.is (93.95.224.165) result in
ECONNREFUSED. The server actively refuses TCP connections on port 80/443.
Possible causes: geo-blocking, server maintenance, or the Iceland site
may be defunct / redirecting to a regional hub.

The scraper is implemented as a clean stub so that:
  1. Enterprise Iceland appears in the dashboard with realistic mock data.
  2. The scraper can be fully activated once the site becomes reachable —
     only `scrape_rates()` needs to be updated.

Enterprise Iceland operates at:
  • Keflavik Airport (KEF) — confirmed via web references
  • Reykjavik city centre — confirmed via Google Maps listing

When the site becomes reachable the recommended approach is:
  • Check for Enterprise's standard EHI API (ecars.enterprise.com/api/…)
    or the XMLRPC booking interface used by European Enterprise branches.
  • Try fetching https://www.enterprise.is/en/car-rental/locations/ to
    discover location codes, then probe /en/car-rental/reservation/select-vehicle/
    which sometimes embeds availability JSON in __NEXT_DATA__.
"""

from __future__ import annotations

from .base import BaseScraper


ENTERPRISE_BASE_URL = "https://www.enterprise.is"

ENTERPRISE_LOCATIONS: dict[str, bool] = {
    "Keflavik Airport": True,
    "Reykjavik":        True,
}


class EnterpriseIsScraper(BaseScraper):
    competitor_name = "Enterprise Iceland"
    base_url = ENTERPRISE_BASE_URL
    FLEET = {
        "Economy": [
            {"model": "Volkswagen Polo",       "price_range": (8000,  12000)},
            {"model": "Hyundai i20",          "price_range": (8500,  12500)},
            {"model": "Toyota Yaris",         "price_range": (8500,  12000)},
            {"model": "Kia Picanto",          "price_range": (7500,  11000)},
        ],
        "Compact": [
            {"model": "Volkswagen Golf",      "price_range": (11000, 16000)},
            {"model": "Seat Leon",            "price_range": (11000, 15500)},
            {"model": "Toyota Corolla",       "price_range": (11500, 16000)},
            {"model": "Renault Megane",       "price_range": (10500, 15000)},
        ],
        "SUV": [
            {"model": "Dacia Duster",         "price_range": (13000, 18500)},
            {"model": "Hyundai Tucson",       "price_range": (15000, 21000)},
            {"model": "Volkswagen Tiguan",    "price_range": (16000, 22000)},
            {"model": "Toyota RAV4",          "price_range": (18000, 25000)},
            {"model": "Nissan Qashqai",       "price_range": (14000, 20000)},
        ],
        "4x4": [
            {"model": "Hyundai Santa Fe",             "price_range": (22000, 30000)},
            {"model": "Kia Sorento",                  "price_range": (22000, 30000)},
            {"model": "Toyota Land Cruiser",
             "canonical_name": "Toyota Land Cruiser 150", "price_range": (26000, 36000)},
            {"model": "Land Rover Discovery",         "price_range": (28000, 38000)},
        ],
        "Minivan": [
            {"model": "Volkswagen Caravelle",
             "canonical_name": "VW Caravelle",  "price_range": (25000, 35000)},
            {"model": "Ford Tourneo",            "price_range": (22000, 32000)},
        ],
    }

    async def scrape_rates(self, location: str, pickup_date: str, return_date: str) -> list[dict]:
        """
        Enterprise Iceland is currently unreachable (ECONNREFUSED on all ports).
        This method raises immediately so BaseScraper falls back to mock data.

        To activate live scraping when the site is back online:
          1. Probe https://www.enterprise.is/ to confirm connectivity.
          2. Inspect network requests on the booking flow to identify the
             vehicle availability API (EHI API or XMLRPC).
          3. Implement the API call here and return a list of rate dicts.
        """
        raise ConnectionError(
            "enterprise.is is unreachable (ECONNREFUSED). "
            "Using FLEET mock data until the site is accessible."
        )
