"""
Scraper for Sixt Iceland (sixt.is).

Sixt Iceland runs on Cloudflare via a proprietary "sitegen" JS framework
(client-sitegen-rent.*.js, ~324 KB).  Extensive static analysis of the
bundle and network probing of known Sixt API patterns
(api.sixt.com, /api/v1/offers, station codes IKEF01/KEFAV/REYAV01) all
returned 404 or connection refused — the Iceland site appears to call
Sixt's internal CDN API that is not publicly accessible without a session
cookie / auth token obtained via browser-rendered JS.

Strategy:
  1. Attempt to fetch the Sixt Iceland booking page HTML and extract any
     price data rendered server-side (SSR JSON blocks, <script> tags with
     structured pricing, or visible price text).
  2. If live extraction fails (likely), fall back to mock data based on a
     researched FLEET definition.

The scraper is structured so that if Sixt's API becomes discoverable in
a future session, only `scrape_rates()` needs to be updated.

Sixt Iceland operates at:
  • Keflavik Airport (KEF)
  • Reykjavik city centre
"""

from __future__ import annotations

import json
import re
from datetime import datetime

from bs4 import BeautifulSoup

from .base import BaseScraper
from canonical import canonicalize


SIXT_BASE_URL = "https://www.sixt.is"

# Sixt Iceland location slugs used in their booking URL
SIXT_LOCATION_SLUGS: dict[str, str | None] = {
    "Keflavik Airport": "keflavik-airport",
    "Reykjavik":        "reykjavik",
}

_4X4_KW     = ["land cruiser", "defender", "discovery", "santa fe", "sorento",
               "wrangler", "hilux", "highlander", "bmw x", "volvo xc90"]
_MINIVAN_KW = ["trafic", "caravelle", "vito", "proace", "transit", "sprinter",
               "transporter"]
_SUV_KW     = ["duster", "jimny", "vitara", "qashqai", "tucson", "sportage",
               "rav4", "x-trail", "forester", "eclipse", "kodiaq", "tiguan",
               "t-roc", "ariya", "model y", "cr-v", "compass", "renegade",
               "ateca", "karoq", "mg "]
_COMPACT_KW = ["captur", "megane", "octavia", "sportswagon", "golf", "leon",
               "focus", "astra", "308", "a3", "model 3"]


def _infer_category(name: str) -> str:
    n = name.lower()
    for kw in _4X4_KW:
        if kw in n:
            return "4x4"
    for kw in _MINIVAN_KW:
        if kw in n:
            return "Minivan"
    for kw in _SUV_KW:
        if kw in n:
            return "SUV"
    for kw in _COMPACT_KW:
        if kw in n:
            return "Compact"
    return "Economy"


class SixtIsScraper(BaseScraper):
    competitor_name = "Sixt Iceland"
    base_url = SIXT_BASE_URL
    FLEET = {
        "Economy": [
            {"model": "Toyota Yaris",          "price_range": (8000,  12000)},
            {"model": "Volkswagen Polo",        "price_range": (9000,  13000)},
            {"model": "Hyundai i20",           "price_range": (8500,  12500)},
            {"model": "Kia Picanto",           "price_range": (7500,  10500)},
            {"model": "Renault Clio",          "price_range": (8500,  12500)},
        ],
        "Compact": [
            {"model": "Volkswagen Golf",       "price_range": (11000, 15500)},
            {"model": "Ford Focus",            "price_range": (11000, 15000)},
            {"model": "Audi A3",               "price_range": (13000, 18000)},
            {"model": "Seat Leon",             "price_range": (11500, 16000)},
        ],
        "SUV": [
            {"model": "Dacia Duster",          "price_range": (14000, 19000)},
            {"model": "Volkswagen T-Roc",      "price_range": (15000, 20500)},
            {"model": "Volkswagen Tiguan",     "price_range": (16000, 22000)},
            {"model": "Hyundai Tucson",        "price_range": (15500, 21000)},
            {"model": "Toyota RAV4",           "price_range": (18000, 25000)},
            {"model": "BMW X1",               "price_range": (19000, 26000)},
            {"model": "Audi Q5",              "price_range": (21000, 29000)},
        ],
        "4x4": [
            {"model": "Toyota Land Cruiser",
             "canonical_name": "Toyota Land Cruiser 150", "price_range": (27000, 37000)},
            {"model": "BMW X5",               "price_range": (29000, 40000)},
            {"model": "Volvo XC90",           "price_range": (27000, 37000)},
            {"model": "Land Rover Defender",  "price_range": (31000, 42000)},
        ],
        "Minivan": [
            {"model": "Volkswagen Caravelle",
             "canonical_name": "VW Caravelle",  "price_range": (26000, 36000)},
            {"model": "Ford Transit",           "price_range": (24000, 34000)},
        ],
    }

    async def _try_ssr_extraction(
        self,
        location_slug: str,
        pickup_date: str,
        return_date: str,
    ) -> list[dict] | None:
        """
        Attempt to extract pricing from SSR HTML or embedded JSON on the
        Sixt booking page.  Returns a list of rate dicts on success, or
        None if no usable data is found.
        """
        url = (
            f"{SIXT_BASE_URL}/en/rent-a-car/{location_slug}"
            f"?dateFrom={pickup_date}&dateTo={return_date}"
        )
        try:
            resp = await self.client.get(url, timeout=15)
            if resp.status_code != 200:
                return None
            soup = BeautifulSoup(resp.text, "lxml")

            # Look for __NEXT_DATA__ or similar JSON blobs
            for script in soup.find_all("script"):
                src = script.string or ""
                if "__NEXT_DATA__" in src or '"offers"' in src or '"vehicles"' in src:
                    # Try to pull a JSON block
                    match = re.search(r'(\{.{200,}\})', src, re.DOTALL)
                    if match:
                        try:
                            data = json.loads(match.group(1))
                            # TODO: parse Sixt-specific offer schema when discovered
                            _ = data
                        except json.JSONDecodeError:
                            pass
        except Exception:
            pass
        return None   # SSR extraction not yet working

    async def scrape_rates(self, location: str, pickup_date: str, return_date: str) -> list[dict]:
        slug = SIXT_LOCATION_SLUGS.get(location)
        if not slug:
            return []

        live = await self._try_ssr_extraction(slug, pickup_date, return_date)
        if live is not None and len(live) > 0:
            return live

        # Sixt's API is not publicly accessible — raise to trigger mock fallback
        raise RuntimeError(
            "Sixt Iceland API not accessible — no public endpoint discovered. "
            "Falling back to FLEET mock data."
        )
