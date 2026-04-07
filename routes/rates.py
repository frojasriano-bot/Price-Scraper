"""
API routes for competitor rate intelligence.
"""

import asyncio
from datetime import date, timedelta
from typing import Optional

from fastapi import APIRouter, Query, HTTPException
from pydantic import BaseModel

from database import (
    DB_PATH,
    get_latest_rates,
    get_rates_history,
    get_rates_history_by_model,
    get_price_deltas,
    get_rates_matrix,
    get_car_catalog,
    get_car_mappings,
    add_car_mapping,
    delete_car_mapping,
    insert_rates,
    set_config,
    get_seasonal_cache,
    set_seasonal_cache,
    get_model_competitor_coverage,
    get_per_competitor_price_changes,
    log_scrape,
    get_scrape_log,
)
from scrapers import ALL_SCRAPERS

router = APIRouter(prefix="/api/rates", tags=["rates"])

# Module-level constants (avoid rebuilding on every request)
_RENTAL_DAYS = 7

_SEASON_MAP: dict[int, tuple[str, str]] = {
    1:  ("low",      "Low Season"),
    2:  ("low",      "Low Season"),
    3:  ("low",      "Low Season"),
    4:  ("shoulder", "Shoulder"),
    5:  ("shoulder", "Shoulder"),
    6:  ("high",     "High Season"),
    7:  ("peak",     "Peak Season"),
    8:  ("high",     "High Season"),
    9:  ("shoulder", "Shoulder"),
    10: ("shoulder", "Shoulder"),
    11: ("low",      "Low Season"),
    12: ("low",      "Low Season"),
}

_MOCK_MODELS: dict[str, list[str]] = {
    "Economy":  ["Toyota Aygo", "Toyota Yaris", "Hyundai i10", "Kia Ceed", "Suzuki Swift"],
    "Compact":  ["Skoda Octavia", "Kia Ceed Sportswagon", "Toyota Corolla", "Renault Captur"],
    "SUV":      ["Suzuki Jimny", "Dacia Duster", "Kia Sportage", "Hyundai Tucson", "Toyota RAV4", "Tesla Model Y"],
    "4x4":      ["Kia Sorento", "Toyota Land Cruiser 150", "Toyota Land Cruiser 250",
                 "Land Rover Defender", "Land Rover Discovery"],
    "Minivan":  ["VW Caravelle", "Renault Trafic", "Toyota Proace"],
}

_BASE_PRICES: dict[str, int] = {
    "Economy": 9000, "Compact": 12000, "SUV": 16000, "4x4": 28000, "Minivan": 22000,
}

# Read-only competitor names directly from class attributes — no instantiation needed
_COMPETITOR_NAMES: list[str] = [cls.competitor_name for cls in ALL_SCRAPERS]


@router.get("")
async def get_rates(
    location: Optional[str] = Query(None, description="Filter by pickup location"),
    pickup_date: Optional[str] = Query(None, description="Pickup date (YYYY-MM-DD)"),
    return_date: Optional[str] = Query(None, description="Return date (YYYY-MM-DD)"),
    car_category: Optional[str] = Query(None, description="Car category filter"),
):
    """
    Return the latest scraped rates for all competitors.
    Optionally filter by location, dates, and car category.
    If the database is empty, returns mock data on the fly.
    """
    rates = await get_latest_rates(
        location=location,
        pickup_date=pickup_date,
        return_date=return_date,
        car_category=car_category,
    )

    # If no data yet, generate mock data on the fly for immediate display
    if not rates:
        mock_pickup = pickup_date or (date.today() + timedelta(days=7)).isoformat()
        mock_return = return_date or (date.today() + timedelta(days=10)).isoformat()
        mock_location = location or "Keflavik Airport"

        mock_rates = []
        for ScraperClass in ALL_SCRAPERS:
            async with ScraperClass() as scraper:
                mock_rates.extend(
                    scraper.get_mock_rates(mock_location, mock_pickup, mock_return)
                )

        # Filter mock data by car_category if requested
        if car_category:
            mock_rates = [r for r in mock_rates if r["car_category"] == car_category]

        return {"rates": mock_rates, "source": "mock"}

    return {"rates": rates, "source": "database"}


@router.post("/scrape")
async def trigger_scrape(
    location: Optional[str] = Query(None),
    pickup_date: Optional[str] = Query(None),
    return_date: Optional[str] = Query(None),
):
    """
    Trigger a manual scrape of all competitor websites.
    Stores results in the database.
    """
    import time
    from datetime import datetime as dt

    mock_pickup = pickup_date or (date.today() + timedelta(days=7)).isoformat()
    mock_return = return_date or (date.today() + timedelta(days=10)).isoformat()

    all_results = []
    errors = []
    started_at = time.monotonic()

    async def run_scraper(ScraperClass):
        async with ScraperClass() as scraper:
            try:
                results = await scraper.run(
                    location=location,
                    pickup_date=mock_pickup,
                    return_date=mock_return,
                )
                return results, None
            except Exception as e:
                return [], str(e)

    tasks = [run_scraper(cls) for cls in ALL_SCRAPERS]
    results_list = await asyncio.gather(*tasks)

    for results, error in results_list:
        if error:
            errors.append(error)
        all_results.extend(results)

    duration = time.monotonic() - started_at

    if all_results:
        await insert_rates(all_results)
        await set_config("last_scrape_at", dt.utcnow().isoformat())

    await log_scrape(
        location=location,
        total_rates=len(all_results),
        competitors=len(ALL_SCRAPERS),
        errors=errors,
        duration_seconds=duration,
        trigger="manual",
    )

    return {
        "scraped": len(all_results),
        "competitors": len(ALL_SCRAPERS),
        "errors": errors,
        "message": f"Scraped {len(all_results)} rate records from {len(ALL_SCRAPERS)} competitors.",
    }


@router.get("/deltas")
async def get_deltas(
    location: Optional[str] = Query(None),
    category: Optional[str] = Query(None),
):
    """
    Return price delta per canonical model: latest scrape date vs the previous one.
    Empty dict if fewer than two scrape dates exist.
    """
    deltas = await get_price_deltas(location=location, category=category)
    return {"deltas": deltas, "available": bool(deltas)}


@router.get("/history")
async def get_history(
    location: Optional[str] = Query(None),
    car_category: Optional[str] = Query(None),
    competitor: Optional[str] = Query(None),
    days: int = Query(30, ge=1, le=365),
):
    """
    Return rate history for trend charting.
    """
    history = await get_rates_history(
        location=location,
        car_category=car_category,
        competitor=competitor,
        days=days,
    )

    # If no history, return synthetic history for chart demo
    if not history:
        import random

        history = []
        today = date.today()
        mock_location = location or "Keflavik Airport"
        mock_category = car_category or "Economy"
        rng = random.Random(42)

        for name in _COMPETITOR_NAMES:
            base_price = rng.randint(8000, 14000)
            for i in range(min(days, 14)):
                day = today - timedelta(days=days - i)
                price = base_price + rng.randint(-500, 500)
                history.append({
                    "competitor": name,
                    "location": mock_location,
                    "car_category": mock_category,
                    "price_isk": price,
                    "scraped_at": day.isoformat() + "T07:00:00",
                })

        if competitor:
            history = [h for h in history if h["competitor"] == competitor]

        return {"history": history, "source": "mock"}

    return {"history": history, "source": "database"}


@router.get("/history/models")
async def get_history_by_model(
    location: Optional[str] = Query(None),
    competitor: Optional[str] = Query(None),
    days: int = Query(30, ge=1, le=365),
):
    """
    Return price history grouped by category → car model → daily data points.
    Used by the Price History chart view.
    """
    data = await get_rates_history_by_model(
        location=location,
        competitor=competitor,
        days=days,
    )

    if data:
        return {"data": data, "source": "database"}

    # ── Mock fallback: synthetic 14-day price series ─────────────────────────
    import random

    rng = random.Random(99)
    today = date.today()
    mock_data: dict = {}

    points = min(days, 14)
    for cat, models in _MOCK_MODELS.items():
        mock_data[cat] = {}
        base = _BASE_PRICES.get(cat, 10000)
        for i, model in enumerate(models):
            price_base = base + i * 1500
            series = []
            price = price_base
            for j in range(points):
                day = today - timedelta(days=points - 1 - j)
                price = max(5000, price + rng.randint(-400, 400))
                series.append({
                    "date": day.isoformat(),
                    "avg_price": price,
                    "min_price": int(price * 0.92),
                    "max_price": int(price * 1.08),
                    "competitor_count": rng.randint(2, 5),
                })
            mock_data[cat][model] = series

    return {"data": mock_data, "source": "mock"}


@router.get("/history/coverage")
async def get_history_coverage(
    location: Optional[str] = Query(None),
    days: int = Query(30, ge=1, le=365),
):
    """
    Return which competitors carry each model for the selected window.
    Used by the Price History coverage grid.
    """
    data = await get_model_competitor_coverage(location=location, days=days)
    if data:
        return {"coverage": data, "source": "database"}

    # Mock fallback: assign random subsets of competitors to each model
    import random
    rng = random.Random(77)
    mock_coverage: dict = {}
    for cat, models in _MOCK_MODELS.items():
        mock_coverage[cat] = {}
        for model in models:
            k = rng.randint(1, len(_COMPETITOR_NAMES))
            mock_coverage[cat][model] = sorted(rng.sample(_COMPETITOR_NAMES, k))
    return {"coverage": mock_coverage, "source": "mock"}


@router.get("/matrix")
async def get_matrix(
    location: Optional[str] = Query(None),
    pickup_date: Optional[str] = Query(None),
    return_date: Optional[str] = Query(None),
    category: Optional[str] = Query(None),
):
    """
    Return a cross-competitor price matrix keyed by canonical car model.
    If the database is empty, generates mock data on the fly.
    """
    result = await get_rates_matrix(
        location=location,
        pickup_date=pickup_date,
        return_date=return_date,
        category=category,
    )

    if result["cars"]:
        return {**result, "source": "database"}

    # Generate mock matrix on the fly
    mock_pickup = pickup_date or (date.today() + timedelta(days=7)).isoformat()
    mock_return = return_date or (date.today() + timedelta(days=10)).isoformat()
    mock_location = location or "Keflavik Airport"

    mock_rates = []
    for ScraperClass in ALL_SCRAPERS:
        async with ScraperClass() as scraper:
            mock_rates.extend(scraper.get_mock_rates(mock_location, mock_pickup, mock_return))

    if category:
        mock_rates = [r for r in mock_rates if r["car_category"] == category]

    # Build matrix from mock rates
    from database import CATEGORY_ORDER

    matrix: dict = {}
    cat_map: dict = {}
    for r in mock_rates:
        canonical = r.get("canonical_name") or r.get("car_model") or r.get("car_category")
        if not canonical:
            continue
        if canonical not in matrix:
            matrix[canonical] = {}
            cat_map[canonical] = r["car_category"]
        comp = r["competitor"]
        if comp not in matrix[canonical] or r["price_isk"] < matrix[canonical][comp]["price_isk"]:
            matrix[canonical][comp] = {
                "price_isk": r["price_isk"],
                "car_model": r.get("car_model"),
                "scraped_at": r.get("scraped_at"),
            }

    def sort_key(name):
        cat = cat_map.get(name, "")
        idx = CATEGORY_ORDER.index(cat) if cat in CATEGORY_ORDER else 99
        return (idx, name)

    cars = []
    for canonical_name in sorted(matrix.keys(), key=sort_key):
        prices_by_comp = matrix[canonical_name]
        available_prices = [v["price_isk"] for v in prices_by_comp.values()]
        cars.append({
            "canonical_name": canonical_name,
            "category": cat_map.get(canonical_name, ""),
            "prices": {comp: prices_by_comp.get(comp) for comp in _COMPETITOR_NAMES},
            "min_price": min(available_prices) if available_prices else None,
            "max_price": max(available_prices) if available_prices else None,
            "cheapest_competitor": min(prices_by_comp, key=lambda c: prices_by_comp[c]["price_isk"]) if prices_by_comp else None,
            "available_at": len(prices_by_comp),
        })

    return {"cars": cars, "competitors": _COMPETITOR_NAMES, "source": "mock"}


@router.get("/seasonal")
async def get_seasonal_rates(
    category: Optional[str] = Query(None, description="Filter to one car category"),
    location: Optional[str] = Query(None, description="Filter to one pickup location"),
    force: bool = Query(False, description="Bypass cache and re-scrape"),
):
    """
    Sweep the next 12 months (mid-month, 7-night stay) and return per-day
    pricing for each competitor and category across the year.
    Reveals low / shoulder / high / peak season price bands.
    """
    # --- Cache check ---
    cache_key = f"seasonal:{category or 'all'}:{location or 'kef'}"
    if not force:
        cached = await get_seasonal_cache(cache_key)
        if cached:
            data, cached_at = cached
            # Preserve the original source ("live" / "mock") so the badge
            # reflects reality. Add cached_at so the UI can show the age.
            data["cached_at"] = cached_at
            return data

    from scrapers.base import LOCATIONS as ALL_LOCATIONS

    today = date.today()
    target_locs = [location] if location else ALL_LOCATIONS

    # Build 12 sample months (15th of each month from now)
    sweep_months = []
    for offset in range(12):
        total_month = today.month + offset
        year = today.year + (total_month - 1) // 12
        month = (total_month - 1) % 12 + 1
        pickup = date(year, month, 15)
        ret = pickup + timedelta(days=_RENTAL_DAYS)
        season, season_label = _SEASON_MAP[month]
        sweep_months.append({
            "month_str":    pickup.strftime("%Y-%m"),
            "month_label":  pickup.strftime("%b %Y"),
            "month_num":    month,
            "pickup":       pickup.isoformat(),
            "return":       ret.isoformat(),
            "season":       season,
            "season_label": season_label,
        })

    # --- Live scrape all months concurrently ---
    # Limit to Keflavik Airport when no location filter to keep request count manageable.
    scrape_locs = target_locs if location else ["Keflavik Airport"]
    semaphore = asyncio.Semaphore(10)

    async def _scrape(ScraperClass, loc, m_info):
        async with semaphore:
            async with ScraperClass() as scraper:
                try:
                    rates = await asyncio.wait_for(
                        scraper.scrape_rates(loc, m_info["pickup"], m_info["return"]),
                        timeout=10,
                    )
                    return rates, m_info["month_str"], "live"
                except Exception:
                    rates = scraper.get_mock_rates(loc, m_info["pickup"], m_info["return"])
                    return rates, m_info["month_str"], "mock"

    tasks = [
        _scrape(Cls, loc, m)
        for m in sweep_months
        for Cls in ALL_SCRAPERS
        for loc in scrape_locs
    ]
    # Overall 90s timeout so a hung scraper batch can't block the endpoint indefinitely
    raw_results = await asyncio.wait_for(
        asyncio.gather(*tasks, return_exceptions=True),
        timeout=90,
    )

    # Bucket all rate dicts by month_str, tracking whether any live data came through
    month_rates: dict[str, list[dict]] = {m["month_str"]: [] for m in sweep_months}
    live_months: set[str] = set()

    for item in raw_results:
        if isinstance(item, Exception):
            continue
        rates, month_str, src = item
        month_rates[month_str].extend(rates)
        if src == "live" and rates:
            live_months.add(month_str)

    # --- Aggregate per month ---
    results = []
    for m in sweep_months:
        comp_data: dict = {}
        for r in month_rates[m["month_str"]]:
            if category and r["car_category"] != category:
                continue
            comp = r["competitor"]
            cat  = r["car_category"]
            per_day = round(r["price_isk"] / _RENTAL_DAYS)
            comp_data.setdefault(comp, {}).setdefault(cat, []).append(per_day)

        competitors: dict = {
            comp: {cat: round(sum(v) / len(v)) for cat, v in cats.items()}
            for comp, cats in comp_data.items()
        }

        market_pool: dict = {}
        for cats in comp_data.values():
            for cat, v in cats.items():
                market_pool.setdefault(cat, []).extend(v)
        market_avg = {cat: round(sum(v) / len(v)) for cat, v in market_pool.items()}

        comp_overall: dict = {
            comp: round(sum(cats.values()) / len(cats))
            for comp, cats in competitors.items() if cats
        }

        results.append({
            "month":         m["month_str"],
            "month_label":   m["month_label"],
            "season":        m["season"],
            "season_label":  m["season_label"],
            "competitors":   competitors,
            "comp_overall":  comp_overall,
            "market_avg":    market_avg,
        })

    # Season summary
    season_buckets: dict = {}
    for r in results:
        s = r["season"]
        for comp, price in r["comp_overall"].items():
            season_buckets.setdefault(s, {}).setdefault(comp, []).append(price)

    season_summary: dict = {
        s: {comp: round(sum(v) / len(v)) for comp, v in comps.items()}
        for s, comps in season_buckets.items()
    }

    # Category season summary (average per-day across all competitors)
    cat_season_buckets: dict = {}
    for r in results:
        s = r["season"]
        for comp_cats in r["competitors"].values():
            for cat, price in comp_cats.items():
                cat_season_buckets.setdefault(s, {}).setdefault(cat, []).append(price)

    category_season_summary: dict = {
        s: {cat: round(sum(v) / len(v)) for cat, v in cats.items()}
        for s, cats in cat_season_buckets.items()
    }

    season_months: dict = {}
    for r in results:
        season_months.setdefault(r["season"], []).append(r["month_label"])

    source = "live" if live_months else "mock"

    # --- Store to cache ---
    result_payload = {
        "months":                  results,
        "season_summary":          season_summary,
        "category_season_summary": category_season_summary,
        "season_months":           season_months,
        "source":                  source,
        "rental_days":             _RENTAL_DAYS,
    }
    await set_seasonal_cache(cache_key, result_payload)

    return result_payload


@router.get("/price-changes")
async def get_price_changes(
    location: Optional[str] = Query(None),
    category: Optional[str] = Query(None),
):
    """
    Per-competitor price change vs previous scrape date.
    Returns a dict keyed by "{competitor}::{location}::{canonical_name}".
    Empty dict if fewer than two scrape dates exist.
    """
    changes = await get_per_competitor_price_changes(location=location, category=category)
    return {"changes": changes, "available": bool(changes)}


@router.get("/scrape-log")
async def get_scrape_log_endpoint(limit: int = Query(20, ge=1, le=100)):
    """Return the most recent scrape history log entries."""
    entries = await get_scrape_log(limit=limit)
    return {"entries": entries}


@router.get("/scraper-status")
async def get_scraper_status():
    """
    Return live-vs-mock status for each scraper by checking the DB for recent data.
    A competitor is 'live' if it has any scraped rows in the database.
    """
    import aiosqlite

    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT competitor, MAX(scraped_at) as last_scraped, COUNT(*) as row_count "
            "FROM rates GROUP BY competitor"
        ) as cursor:
            rows = await cursor.fetchall()

    live_set          = {row["competitor"] for row in rows if row["row_count"] > 0}
    last_scraped_map  = {row["competitor"]: row["last_scraped"] for row in rows if row["last_scraped"]}

    scrapers = [
        {
            "name":         name,
            "source":       "live" if name in live_set else "mock",
            "last_scraped": last_scraped_map.get(name),
        }
        for name in _COMPETITOR_NAMES
    ]
    return {"scrapers": scrapers}


@router.get("/car-catalog")
async def get_catalog():
    """Return the canonical car catalog."""
    return {"catalog": await get_car_catalog()}


@router.get("/car-mappings")
async def list_mappings():
    """Return all competitor model name → canonical name mappings."""
    return {"mappings": await get_car_mappings()}


class MappingCreate(BaseModel):
    competitor: str
    competitor_model: str
    canonical_name: str


@router.post("/car-mappings")
async def create_mapping(body: MappingCreate):
    await add_car_mapping(body.competitor, body.competitor_model, body.canonical_name)
    return {"message": "Mapping saved."}


@router.delete("/car-mappings/{mapping_id}")
async def remove_mapping(mapping_id: int):
    await delete_car_mapping(mapping_id)
    return {"message": "Mapping deleted."}
