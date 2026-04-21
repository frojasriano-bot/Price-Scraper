"""
Scraper for Sixt Iceland (sixt.is).

Architecture discovered via deep static analysis (2026-04-21)
──────────────────────────────────────────────────────────────
Sixt.is is a Cloudflare Workers SPA (sitegen framework, React + Module Federation).
The booking funnel is a micro-frontend called ZenFunnelContainer which lazy-loads
the rent-offer-list MFE.

Vehicle search API: gRPC-Web (binary protobuf)
  Endpoint: https://grpc-prod.orange.sixt.com
  Service:  api_v1_ecommerce_data  (EcommerceData service)
  Method:   ListOffers
  Params:   pickupStationId, returnStationId, pickupDate, returnDate, ...

Metadata REST API (not sufficient for pricing):
  https://web-api.orange.sixt.com
  GET /v2/apps/fleet/country  → confirms Iceland (IS) is in the fleet
  GET /v2/apps/regions/{code}/branches → returns [] for IS

The gRPC endpoint returns HTTP 464 for non-gRPC requests. Constructing valid
gRPC-Web protobuf frames requires the .proto definitions which are not publicly
available. The API is NOT accessible via REST or JSON-over-HTTP2.

Activation path:
  Option A: Capture a complete browser network trace with the binary gRPC frames
            and use grpcurl + .proto extraction to build valid requests.
  Option B: Monitor Sixt for a REST fallback API (they have one for subscription
            services; the rent search may eventually get one too).

Sixt Iceland operates at:
  • Keflavik Airport (KEF)
  • Reykjavik city centre
"""

from __future__ import annotations

from .base import BaseScraper


SIXT_BASE_URL = "https://www.sixt.is"

SIXT_LOCATIONS: dict[str, bool] = {
    "Keflavik Airport": True,
    "Reykjavik":        True,
}


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

    async def scrape_rates(self, location: str, pickup_date: str, return_date: str) -> list[dict]:
        """
        Sixt Iceland vehicle search uses a gRPC-Web binary API at:
          https://grpc-prod.orange.sixt.com  (service: api_v1_ecommerce_data)

        The binary protobuf protocol requires .proto definitions which are not
        publicly available.  Raising here triggers the FLEET mock data fallback.

        To activate live scraping:
          1. Run: npm install -g grpc-tools
          2. Capture a browser network trace and extract the binary gRPC frames
          3. Use buf.build or protoc to decode/reconstruct the .proto schema
          4. Build a grpc.io/grpc-web client here using those proto definitions
        """
        raise NotImplementedError(
            "Sixt Iceland uses gRPC-Web binary API (grpc-prod.orange.sixt.com). "
            "Not accessible without .proto definitions. Using FLEET mock data."
        )
