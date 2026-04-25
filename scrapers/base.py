"""
Base scraper class for Blue Rental Intelligence.
All competitor scrapers inherit from BaseScraper.
"""

import asyncio
import logging
import random
from abc import ABC, abstractmethod
from datetime import datetime
from typing import Optional

import httpx
from bs4 import BeautifulSoup

from canonical import canonicalize

logger = logging.getLogger("blue_rental.scrapers")

LOCATIONS = [
    "Keflavik Airport",
    "Reykjavik",
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

# Full browser-grade headers.  The Sec-Ch-Ua / Sec-Fetch-* family is what most
# Cloudflare / bot-detection checks look for beyond the User-Agent string.
DEFAULT_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": (
        "text/html,application/xhtml+xml,application/xml;"
        "q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,"
        "application/signed-exchange;v=b3;q=0.7"
    ),
    "Accept-Language":          "en-GB,en;q=0.9,is;q=0.8",
    # Accept-Encoding is intentionally omitted — httpx adds it automatically
    # and handles decompression.  Manually setting it breaks decompression on
    # some Caren/Cloudflare endpoints that return Brotli-encoded JSON.
    "Cache-Control":            "max-age=0",
    "Upgrade-Insecure-Requests": "1",
    "Sec-Ch-Ua":                '"Chromium";v="124", "Google Chrome";v="124", "Not-A.Brand";v="99"',
    "Sec-Ch-Ua-Mobile":         "?0",
    "Sec-Ch-Ua-Platform":       '"Windows"',
    "Sec-Fetch-Dest":           "document",
    "Sec-Fetch-Mode":           "navigate",
    "Sec-Fetch-Site":           "none",
    "Sec-Fetch-User":           "?1",
}

# How many times to retry a transient HTTP error before giving up
_MAX_RETRIES = 3
# Base delay in seconds (doubles on each retry: 1s, 2s, 4s)
_RETRY_BASE_DELAY = 1.0
# HTTP status codes that are worth retrying
_RETRYABLE_STATUS = {429, 500, 502, 503, 504}


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

    def __init__(self, timeout: int = 30):
        self.timeout = timeout
        self.client = httpx.AsyncClient(
            headers=DEFAULT_HEADERS,
            timeout=timeout,
            follow_redirects=True,
            # Maintain a cookie jar across requests in the same session
            # (important for WordPress nonce-based flows like Hertz)
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

    async def get_with_retry(self, url: str, **kwargs) -> httpx.Response:
        """
        GET with automatic retry on transient errors.
        Retries up to _MAX_RETRIES times with exponential backoff.
        Raises the last exception if all retries fail.
        """
        last_exc: Exception | None = None
        for attempt in range(_MAX_RETRIES):
            try:
                resp = await self.client.get(url, **kwargs)
                if resp.status_code in _RETRYABLE_STATUS:
                    raise httpx.HTTPStatusError(
                        f"HTTP {resp.status_code}", request=resp.request, response=resp
                    )
                return resp
            except (httpx.TimeoutException, httpx.ConnectError, httpx.HTTPStatusError) as exc:
                last_exc = exc
                if attempt < _MAX_RETRIES - 1:
                    delay = _RETRY_BASE_DELAY * (2 ** attempt) + random.uniform(0, 0.5)
                    logger.debug(
                        "%s: retry %d/%d after %.1fs — %s",
                        self.competitor_name, attempt + 1, _MAX_RETRIES, delay, exc,
                    )
                    await asyncio.sleep(delay)
        raise last_exc  # type: ignore[misc]

    async def post_with_retry(self, url: str, **kwargs) -> httpx.Response:
        """
        POST with automatic retry on transient errors.
        Same backoff strategy as get_with_retry.
        """
        last_exc: Exception | None = None
        for attempt in range(_MAX_RETRIES):
            try:
                resp = await self.client.post(url, **kwargs)
                if resp.status_code in _RETRYABLE_STATUS:
                    raise httpx.HTTPStatusError(
                        f"HTTP {resp.status_code}", request=resp.request, response=resp
                    )
                return resp
            except (httpx.TimeoutException, httpx.ConnectError, httpx.HTTPStatusError) as exc:
                last_exc = exc
                if attempt < _MAX_RETRIES - 1:
                    delay = _RETRY_BASE_DELAY * (2 ** attempt) + random.uniform(0, 0.5)
                    logger.debug(
                        "%s: POST retry %d/%d after %.1fs — %s",
                        self.competitor_name, attempt + 1, _MAX_RETRIES, delay, exc,
                    )
                    await asyncio.sleep(delay)
        raise last_exc  # type: ignore[misc]

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
                    "canonical_name": canonicalize(car.get("canonical_name", car["model"])),
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
            except Exception as exc:
                logger.warning("%s scrape failed for %s: %s — falling back to mock data", self.competitor_name, loc, exc)
                all_rates.extend(self.get_mock_rates(loc, pickup_date, return_date))

        return all_rates
