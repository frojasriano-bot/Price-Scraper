"""
Scraper for Enterprise Iceland (www.enterpriserentacar.is).

Booking platform: PartnerBookingKit (EHI — Enterprise Holdings International)
─────────────────────────────────────────────────────────────────────────────
The site (Vercel / Next.js) embeds the PartnerBookingKit widget:
  JS bundle: https://widget-cdn.partnerbookingkit.com/bundles/8beb76d6139f5/widget.js
  API:       https://pbk.partnerbookingkit.com  (session-auth required)

The widget calls `https://pbk.partnerbookingkit.com` for availability and
pricing, but all endpoints return 404 without a valid browser-generated
session (the widget performs a browser-driven OAuth-style flow against the
EHI API before querying rates).

The site itself IS live and returns HTTP 200:
  https://www.enterpriserentacar.is/

Activation path when/if the API becomes accessible:
  1. Capture a network trace of the PartnerBookingKit widget in a browser.
  2. Identify the `Authorization` header and bearer token format.
  3. Implement a token exchange flow against `pbk.partnerbookingkit.com`.
  4. Replace the `raise ConnectionError(...)` below with the actual API call.

Enterprise Iceland operates at:
  • Keflavik Airport (KEF)
  • Reykjavik city centre
"""

from __future__ import annotations

from .base import BaseScraper


ENTERPRISE_BASE_URL = "https://www.enterpriserentacar.is"

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
        Enterprise Iceland uses the PartnerBookingKit (EHI) widget which requires
        a browser-initiated OAuth session to access pricing data.

        The site is reachable at https://www.enterpriserentacar.is/ (HTTP 200, Vercel).
        The booking widget bundle is:
          https://widget-cdn.partnerbookingkit.com/bundles/8beb76d6139f5/widget.js

        To activate live scraping, implement the EHI API auth flow and replace
        this raise with the actual API call.
        """
        raise ConnectionError(
            "Enterprise Iceland uses PartnerBookingKit (EHI API) which requires "
            "browser auth. Using FLEET mock data."
        )
