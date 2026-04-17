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
    clear_seasonal_cache,
    get_seasonal_anchor_history,
    get_model_competitor_coverage,
    get_per_competitor_price_changes,
    get_horizon_rates,
    get_model_horizon,
    get_price_timeline,
    get_booking_window,
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

    # If the exact pickup_date has no data, fall back to the most recent data in the DB
    if not result["cars"] and pickup_date:
        result = await get_rates_matrix(location=location, category=category)

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
    force: bool = Query(False, description="Bypass response cache and re-read from DB"),
):
    """
    Return seasonal price analysis across the next 12 months (15th of each month,
    7-night stay). Reads from the rates DB first — only live-scrapes months that
    have no stored anchor data. Response is cached for 30 minutes.
    """
    cache_key = f"seasonal:{category or 'all'}:{location or 'kef'}"
    if not force:
        cached = await get_seasonal_cache(cache_key, max_age_hours=0.5)
        if cached:
            data, cached_at = cached
            data["cached_at"] = cached_at
            return data

    today = date.today()
    scrape_loc = location or "Keflavik Airport"

    # Build 12 anchor months
    sweep_months = []
    for offset in range(12):
        total_month = today.month + offset
        year  = today.year + (total_month - 1) // 12
        month = (total_month - 1) % 12 + 1
        pickup = date(year, month, 15)
        ret    = pickup + timedelta(days=_RENTAL_DAYS)
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

    # --- DB-first: check stored rates for each anchor month ---
    month_rates: dict[str, list[dict]] = {}
    months_needing_scrape: list[dict]  = []

    for m in sweep_months:
        stored = await get_latest_rates(
            location=scrape_loc,
            pickup_date=m["pickup"],
            return_date=m["return"],
        )
        if stored:
            month_rates[m["month_str"]] = stored
        else:
            month_rates[m["month_str"]] = []
            months_needing_scrape.append(m)

    # --- Live-scrape only months with no stored data ---
    live_months: set[str] = set()
    db_months:   set[str] = set(month_rates) - set(m["month_str"] for m in months_needing_scrape)

    if months_needing_scrape:
        semaphore = asyncio.Semaphore(10)

        async def _scrape(ScraperClass, m_info):
            async with semaphore:
                async with ScraperClass() as scraper:
                    try:
                        rates = await asyncio.wait_for(
                            scraper.scrape_rates(scrape_loc, m_info["pickup"], m_info["return"]),
                            timeout=10,
                        )
                        return rates, m_info["month_str"], "live"
                    except Exception:
                        rates = scraper.get_mock_rates(scrape_loc, m_info["pickup"], m_info["return"])
                        return rates, m_info["month_str"], "mock"

        tasks = [
            _scrape(Cls, m)
            for m in months_needing_scrape
            for Cls in ALL_SCRAPERS
        ]
        raw_results = await asyncio.wait_for(
            asyncio.gather(*tasks, return_exceptions=True),
            timeout=90,
        )

        newly_scraped: list[dict] = []
        for item in raw_results:
            if isinstance(item, Exception):
                continue
            rates, month_str, src = item
            month_rates[month_str].extend(rates)
            if src == "live" and rates:
                live_months.add(month_str)
                newly_scraped.extend(rates)

        # Persist only live-scraped data so it's available on future requests
        if newly_scraped:
            await insert_rates(newly_scraped)

    # --- Aggregate per month (unchanged logic) ---
    results = []
    for m in sweep_months:
        comp_data: dict = {}
        for r in month_rates[m["month_str"]]:
            if category and r["car_category"] != category:
                continue
            comp    = r["competitor"]
            cat     = r["car_category"]
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
            "month":        m["month_str"],
            "month_label":  m["month_label"],
            "season":       m["season"],
            "season_label": m["season_label"],
            "competitors":  competitors,
            "comp_overall": comp_overall,
            "market_avg":   market_avg,
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

    # Source label: database if all from DB, live if any newly scraped, mock if nothing live
    if db_months and not live_months:
        source = "database"
    elif live_months:
        source = "live"
    else:
        source = "mock"

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


@router.post("/scrape-seasonal")
async def scrape_seasonal_anchors(
    location: Optional[str] = Query(None, description="Location to scrape (default: Keflavik Airport)"),
):
    """
    Scrape the 15th of each of the next 12 months and persist in the rates table.
    Only stores data from successful live scrapes — mock fallbacks are discarded.
    Called by the weekly cron job and the manual 'Scrape All Months' button.
    """
    import time
    from datetime import datetime as dt

    scrape_loc  = location or "Keflavik Airport"
    today       = date.today()
    started_at  = time.monotonic()
    total_rates = 0
    all_errors: list[str] = []
    month_log:  list[dict] = []

    semaphore = asyncio.Semaphore(10)

    async def _scrape_one(ScraperClass, pickup_iso: str, ret_iso: str):
        async with semaphore:
            async with ScraperClass() as scraper:
                try:
                    rates = await asyncio.wait_for(
                        scraper.scrape_rates(scrape_loc, pickup_iso, ret_iso),
                        timeout=15,
                    )
                    return rates, None
                except Exception as e:
                    return [], f"{ScraperClass.competitor_name}: {e}"

    for offset in range(12):
        total_month = today.month + offset
        year  = today.year + (total_month - 1) // 12
        month = (total_month - 1) % 12 + 1
        pickup_d = date(year, month, 15)
        ret_d    = pickup_d + timedelta(days=_RENTAL_DAYS)
        pickup   = pickup_d.isoformat()
        ret      = ret_d.isoformat()

        tasks   = [_scrape_one(Cls, pickup, ret) for Cls in ALL_SCRAPERS]
        results = await asyncio.gather(*tasks)

        month_rates: list[dict] = []
        month_errors: list[str] = []
        for rates, err in results:
            if err:
                month_errors.append(err)
            else:
                month_rates.extend(rates)

        if month_rates:
            await insert_rates(month_rates)
            total_rates += len(month_rates)

        all_errors.extend(month_errors)
        month_log.append({
            "month":  pickup_d.strftime("%Y-%m"),
            "pickup": pickup,
            "rates":  len(month_rates),
            "errors": month_errors,
        })

    duration = time.monotonic() - started_at

    # Invalidate the 30-min response cache so the next GET reflects fresh data
    await clear_seasonal_cache()

    await log_scrape(
        location=scrape_loc,
        total_rates=total_rates,
        competitors=len(ALL_SCRAPERS),
        errors=all_errors[:20],
        duration_seconds=duration,
        trigger="seasonal",
    )

    return {
        "scraped":          total_rates,
        "months_scraped":   len(month_log),
        "duration_seconds": round(duration, 1),
        "months":           month_log,
        "errors":           all_errors[:20],
    }


@router.get("/seasonal/history")
async def get_seasonal_history(
    pickup_date: str = Query(..., description="Anchor pickup date YYYY-MM-DD, e.g. 2026-07-15"),
    category:    Optional[str] = Query(None, description="Filter to one car category"),
    location:    Optional[str] = Query(None),
):
    """
    Return a time series showing how prices for a specific anchor month evolved
    across successive scrape dates. Used by the 'Price Evolution' history chart.
    """
    ret_date  = (date.fromisoformat(pickup_date) + timedelta(days=_RENTAL_DAYS)).isoformat()
    scrape_loc = location or "Keflavik Airport"

    rows = await get_seasonal_anchor_history(
        pickup_date=pickup_date,
        return_date=ret_date,
        location=scrape_loc,
        category=category,
    )

    if not rows:
        return {
            "series":      {},
            "pickup_date": pickup_date,
            "return_date": ret_date,
            "source":      "none",
        }

    # Pivot to {competitor: [{date, avg_per_day, car_count}, ...]}
    # If category filter active: one series per competitor
    # If no filter: average across categories per competitor per date
    series: dict[str, list] = {}
    for row in rows:
        comp = row["competitor"]
        if comp not in series:
            series[comp] = []
        series[comp].append({
            "date":       row["scrape_date"],
            "avg_per_day": int(row["avg_per_day"]),
            "car_count":  row["car_count"],
            "category":   row["car_category"],
        })

    return {
        "series":      series,
        "pickup_date": pickup_date,
        "return_date": ret_date,
        "source":      "database",
    }


@router.get("/seasonal/gap-by-model")
async def get_seasonal_gap_by_model(
    category: str = Query(..., description="Car category (required, e.g. 'Economy')"),
    location: Optional[str] = Query(None, description="Pickup location"),
):
    """
    Per-model Blue-vs-market price gap for one category, across the 12 anchor
    months used by the Seasonal view. Reads from the stored rates only — scrape
    via /seasonal first to populate.

    Response:
      {
        "category": "Economy",
        "months":   [{month_str, month_label, season}, ...],
        "models":   [
          {
            "canonical_name": "Toyota Yaris",
            "gaps": [
              {"blue_price": 7200, "market_avg": 8100, "gap_pct": -11, "blue_n": 1, "comp_n": 4},
              null,  // no data for this month
              ...
            ]
          },
          ...
        ],
        "source":   "database" | "none"
      }
    """
    today      = date.today()
    scrape_loc = location or "Keflavik Airport"

    # Build the same 12 anchor months as /seasonal
    sweep_months = []
    for offset in range(12):
        total_month = today.month + offset
        year  = today.year + (total_month - 1) // 12
        month = (total_month - 1) % 12 + 1
        pickup = date(year, month, 15)
        ret    = pickup + timedelta(days=_RENTAL_DAYS)
        season, _ = _SEASON_MAP[month]
        sweep_months.append({
            "month_str":   pickup.strftime("%Y-%m"),
            "month_label": pickup.strftime("%b %Y"),
            "pickup":      pickup.isoformat(),
            "return":      ret.isoformat(),
            "season":      season,
        })

    # Collect per-model, per-month prices from stored rates
    # Structure: { canonical_name: { month_str: {"blue": [...], "comp": [...]} } }
    per_model: dict[str, dict[str, dict[str, list[int]]]] = {}
    any_data = False

    for m in sweep_months:
        rates = await get_latest_rates(
            location=scrape_loc,
            pickup_date=m["pickup"],
            return_date=m["return"],
            car_category=category,
        )
        if rates:
            any_data = True
        for r in rates:
            name    = r.get("canonical_name") or r["car_model"]
            per_day = round(r["price_isk"] / _RENTAL_DAYS)
            bucket  = per_model.setdefault(name, {}).setdefault(
                m["month_str"], {"blue": [], "comp": []}
            )
            if r["competitor"] == "Blue Car Rental":
                bucket["blue"].append(per_day)
            else:
                bucket["comp"].append(per_day)

    # Build response — one row per model, 12 monthly gap entries
    models = []
    for name in sorted(per_model.keys()):
        gaps = []
        has_any = False
        for m in sweep_months:
            bucket = per_model[name].get(m["month_str"])
            if not bucket or (not bucket["blue"] and not bucket["comp"]):
                gaps.append(None)
                continue
            blue_avg = round(sum(bucket["blue"]) / len(bucket["blue"])) if bucket["blue"] else None
            mkt_avg  = round(sum(bucket["comp"]) / len(bucket["comp"])) if bucket["comp"] else None
            gap_pct  = (
                round((blue_avg / mkt_avg - 1) * 100)
                if blue_avg is not None and mkt_avg not in (None, 0)
                else None
            )
            gaps.append({
                "blue_price": blue_avg,
                "market_avg": mkt_avg,
                "gap_pct":    gap_pct,
                "blue_n":     len(bucket["blue"]),
                "comp_n":     len(bucket["comp"]),
            })
            if gap_pct is not None:
                has_any = True
        if has_any:
            models.append({"canonical_name": name, "gaps": gaps})

    return {
        "category": category,
        "months":   [
            {"month_str": m["month_str"], "month_label": m["month_label"], "season": m["season"]}
            for m in sweep_months
        ],
        "models":   models,
        "source":   "database" if any_data else "none",
    }


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


@router.get("/horizon")
async def get_horizon(
    location: Optional[str] = Query(None),
    category: Optional[str] = Query(None),
    weeks: int = Query(26, ge=4, le=52),
):
    """
    Return forward-looking rate horizon: next N weeks of per-day pricing per competitor.
    Shows only real scraped data — weeks with no data are returned empty.
    """
    import random

    horizon = await get_horizon_rates(location=location, category=category, weeks=weeks)
    has_any = any(w["has_data"] for w in horizon)
    source = "database" if has_any else "none"
    return {"weeks": horizon, "source": source}


@router.post("/scrape-horizon")
async def scrape_horizon(
    location: Optional[str] = Query(None),
    weeks: int = Query(26, ge=4, le=52),
):
    """
    Scrape prices for each of the next N weeks (7-night rental window) and store in DB.
    """
    import time
    from datetime import datetime as dt

    scrape_loc = location or "Keflavik Airport"
    today = date.today()
    started_at = time.monotonic()
    total_rates = 0
    all_errors: list[str] = []
    week_log: list[dict] = []

    semaphore = asyncio.Semaphore(10)

    async def _scrape_one(ScraperClass, pickup_iso: str, ret_iso: str):
        async with semaphore:
            async with ScraperClass() as scraper:
                try:
                    rates = await asyncio.wait_for(
                        scraper.scrape_rates(scrape_loc, pickup_iso, ret_iso),
                        timeout=15,
                    )
                    return rates, None
                except Exception as e:
                    return [], f"{ScraperClass.competitor_name}: {e}"

    for w in range(1, weeks + 1):
        pickup_d = today + timedelta(weeks=w)
        ret_d    = pickup_d + timedelta(days=7)
        pickup   = pickup_d.isoformat()
        ret      = ret_d.isoformat()

        tasks   = [_scrape_one(Cls, pickup, ret) for Cls in ALL_SCRAPERS]
        results = await asyncio.gather(*tasks)

        week_rates:  list[dict] = []
        week_errors: list[str]  = []
        for rates, err in results:
            if err:
                week_errors.append(err)
            else:
                week_rates.extend(rates)

        if week_rates:
            await insert_rates(week_rates)
            total_rates += len(week_rates)

        all_errors.extend(week_errors)
        week_log.append({"week": w, "pickup": pickup, "rates": len(week_rates), "errors": week_errors})

    duration = time.monotonic() - started_at

    await log_scrape(
        location=scrape_loc,
        total_rates=total_rates,
        competitors=len(ALL_SCRAPERS),
        errors=all_errors[:20],
        duration_seconds=duration,
        trigger="horizon",
    )

    return {
        "scraped":          total_rates,
        "weeks_scraped":    len(week_log),
        "duration_seconds": round(duration, 1),
        "weeks":            week_log,
        "errors":           all_errors[:20],
    }


@router.get("/model-horizon")
async def get_model_horizon_endpoint(
    model:    str            = Query(..., description="Canonical model name, e.g. Toyota RAV4"),
    location: Optional[str] = Query(None),
):
    """
    Return all future scraped per-day prices for a specific canonical model across competitors.
    Combines weekly horizon anchors and monthly seasonal anchors into a single time series.
    """
    series = await get_model_horizon(canonical_name=model, location=location)
    return {
        "model":  model,
        "series": series,
        "source": "database" if series else "none",
    }


@router.get("/price-timeline")
async def get_price_timeline_endpoint(
    days:           int            = Query(30,  ge=1,   le=365),
    min_change_pct: float          = Query(5.0, ge=0.5, le=50.0),
    category:       Optional[str]  = Query(None),
    location:       Optional[str]  = Query(None),
    model:          Optional[str]  = Query(None),
):
    """
    Return all meaningful per-day price changes across competitors within the lookback window.
    Compares consecutive scrape snapshots per competitor × model.
    """
    events = await get_price_timeline(
        days=days,
        min_change_pct=min_change_pct,
        category=category,
        location=location,
        model=model,
    )
    return {"events": events, "count": len(events)}


@router.get("/booking-window")
async def get_booking_window_endpoint(
    pickup_date: str           = Query(..., description="YYYY-MM-DD — the future pickup date to analyse"),
    category:    Optional[str] = Query(None),
    location:    Optional[str] = Query(None),
    model:       Optional[str] = Query(None),
):
    """
    For a specific future pickup date, return how competitor prices have changed
    across successive weekly scrapes — reveals lead-time pricing behaviour.
    """
    data = await get_booking_window(
        pickup_date=pickup_date,
        category=category,
        location=location,
        model=model,
    )
    return data
