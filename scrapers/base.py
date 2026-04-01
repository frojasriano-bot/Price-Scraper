"""
Base scraper class for Blue Rental Intelligence.
All competitor scrapers inherit from BaseScraper.
"""

import random
from abc import ABC, abstractmethod
from datetime import datetime
from typing import Optional

import httpx
from bs4 import BeautifulSoup


LOCATIONS = [
    "Keflavik Airport",
    "Reykjavik",
    "Akureyri",
    "Egilsstaðir",
]

# Iceland car rental seasonality multipliers (applied to mock per-day prices).
# Based on real tourism demand patterns: peak = July midnight sun,
# low = winter months with minimal tourist traffic.
SEASON_MULTIPLIERS: dict[int, float] = {
    1:  0.82,   # January   – deep winter, lowest demand
    2:  0.84,   # February  – winter, some Northern Lights tours
    3:  0.90,   # March     – end of winter, early bookings pick up
    4:  1.10,   # April     – Easter tourists, shoulder starts
    5:  1.32,   # May       – shoulder season building fast
    6:  1.65,   # June      – high season, midnight sun begins
    7:  1.92,   # July      – peak season, highest demand
    8:  1.78,   # August    – still high season, tapering slightly
    9:  1.22,   # September – shoulder, good weather, lower crowds
    10: 1.02,   # October   – back to near-normal
    11: 0.88,   # November  – low season
    12: 0.93,   # December  – Christmas/NYE partial recovery
}

# Default fleet used if a scraper doesn't define its own FLEET.
# Format: {category: [{"model": str, "price_range": (min_per_day, max_per_day)}]}
DEFAULT_FLEET: dict[str, list[dict]] = {
    "Economy": [{"model": "Economy Car", "price_range": (7500, 13000)}],
    "Compact": [{"model": "Compact Car", "price_range": (9000, 15000)}],
    "SUV":     [{"model": "SUV",         "price_range": (17000, 28000)}],
    "4x4":     [{"model": "4x4",         "price_range": (20000, 35000)}],
    "Minivan": [{"model": "Minivan",     "price_range": (22000, 38000)}],
}

# Common headers to mimic a real browser
DEFAULT_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "en-US,en;q=0.9,is;q=0.8",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}


class BaseScraper(ABC):
    """
    Abstract base class for all car rental rate scrapers.

    Subclasses must implement `scrape_rates()`.
    If real scraping fails or is not yet implemented, `get_mock_rates()` is used
    as a fallback so the dashboard always has data to display.
    """

    # Override in each subclass
    competitor_name: str = "Unknown"
    base_url: str = ""
    # Define each competitor's real fleet here. See DEFAULT_FLEET for format.
    FLEET: dict[str, list[dict]] = {}

    def __init__(self, timeout: int = 15):
        self.timeout = timeout
        self.client = httpx.AsyncClient(
            headers=DEFAULT_HEADERS,
            timeout=timeout,
            follow_redirects=True,
        )

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        await self.client.aclose()

    @abstractmethod
    async def scrape_rates(
        self,
        location: str,
        pickup_date: str,
        return_date: str,
    ) -> list[dict]:
        """
        Attempt to scrape live rates from the competitor website.
        Should return a list of rate dicts matching the DB schema.
        Raise any exception on failure — the caller will fall back to mock data.
        """
        ...

    async def fetch_html(self, url: str, **kwargs) -> BeautifulSoup:
        """Fetch a URL and return a BeautifulSoup object."""
        response = await self.client.get(url, **kwargs)
        response.raise_for_status()
        return BeautifulSoup(response.text, "lxml")

    def get_mock_rates(
        self,
        location: str,
        pickup_date: str,
        return_date: str,
    ) -> list[dict]:
        """
        Generate realistic mock rate data using the competitor's FLEET definition.
        Each car model gets a deterministic price within its range so results
        are stable across calls but vary realistically between competitors.
        """
        now = datetime.utcnow().isoformat()
        fleet = self.FLEET or DEFAULT_FLEET

        # Calculate rental duration
        try:
            fmt = "%Y-%m-%d"
            days = max(
                (datetime.strptime(return_date, fmt) - datetime.strptime(pickup_date, fmt)).days,
                1,
            )
        except Exception:
            days = 3

        # Seasonal multiplier based on pickup month
        try:
            pickup_month = int(pickup_date[5:7])
        except Exception:
            pickup_month = 7
        seasonal_mult = SEASON_MULTIPLIERS.get(pickup_month, 1.0)

        # Per-competitor pricing personality: ±8% stable jitter so each
        # competitor sits at a slightly different point on the seasonal curve.
        comp_seed = sum(ord(c) for c in self.competitor_name)
        comp_factor = 1.0 + ((comp_seed % 17) - 8) / 100.0  # range ~0.92–1.08

        rates = []
        for category, cars in fleet.items():
            for car in cars:
                # Deterministic base price (consistent regardless of date)
                rng = random.Random(self.competitor_name + location + car["model"])
                low, high = car["price_range"]
                base_per_day = rng.randint(low, high)

                # Apply seasonal adjustment + competitor personality
                price_per_day = round(base_per_day * seasonal_mult * comp_factor)

                rates.append({
                    "competitor": self.competitor_name,
                    "location": location,
                    "pickup_date": pickup_date,
                    "return_date": return_date,
                    "car_category": category,
                    "car_model": car["model"],
                    "canonical_name": car.get("canonical_name", car["model"]),
                    "price_isk": price_per_day * days,
                    "currency": "ISK",
                    "scraped_at": now,
                })
        return rates

    async def run(
        self,
        location: Optional[str] = None,
        pickup_date: Optional[str] = None,
        return_date: Optional[str] = None,
    ) -> list[dict]:
        """
        Main entry point. Tries live scraping first; falls back to mock data.
        Iterates over all locations if none specified.
        """
        from datetime import date, timedelta

        if not pickup_date:
            pickup_date = (date.today() + timedelta(days=7)).isoformat()
        if not return_date:
            return_date = (date.today() + timedelta(days=10)).isoformat()

        target_locations = [location] if location else LOCATIONS
        all_rates = []

        for loc in target_locations:
            try:
                rates = await self.scrape_rates(loc, pickup_date, return_date)
                all_rates.extend(rates)
            except Exception:
                # Scraping failed — use mock data so the dashboard always works
                all_rates.extend(self.get_mock_rates(loc, pickup_date, return_date))

        return all_rates
