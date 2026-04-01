"""
API routes for local SEO rank tracking.
"""

import json
import asyncio
from datetime import date, datetime, timedelta
from typing import Optional

import httpx
from fastapi import APIRouter, Query, HTTPException

from database import (
    get_config,
    set_config,
    insert_rankings,
    get_latest_rankings,
    get_rankings_history,
    get_previous_rankings,
    delete_rankings_for_keywords,
)

router = APIRouter(prefix="/api/seo", tags=["seo"])

# Pre-loaded Iceland car rental keywords (used as fallback only)
DEFAULT_KEYWORDS = [
    "car rental reykjavik",
    "bílaleiga reykjavík",
    "cheap car hire iceland",
    "rent a car keflavik airport",
    "leigubíll ísland",
]

# Default search location
DEFAULT_LOCATION = "Reykjavik, Iceland"


async def get_stored_keywords() -> list[str]:
    """Load keywords from DB config, falling back to DEFAULT_KEYWORDS."""
    raw = await get_config("seo_keywords", "")
    if raw:
        try:
            parsed = json.loads(raw)
            if isinstance(parsed, list) and parsed:
                return parsed
        except (json.JSONDecodeError, TypeError):
            pass
    return list(DEFAULT_KEYWORDS)


async def _check_keyword_rank(
    client: httpx.AsyncClient,
    api_key: str,
    keyword: str,
    location: str,
    target_domain: str = "bluecarrental.is",
) -> dict:
    """
    Query SerpAPI for a keyword and find the rank of the target domain.
    Returns a ranking dict ready for DB insertion.
    """
    params = {
        "engine": "google",
        "q": keyword,
        "location": location,
        "api_key": api_key,
        "num": 100,
        "gl": "is",
        "hl": "en",
    }

    response = await client.get("https://serpapi.com/search", params=params, timeout=30)
    response.raise_for_status()
    data = response.json()

    organic = data.get("organic_results", [])
    rank = None
    url = None

    for i, result in enumerate(organic, start=1):
        result_url = result.get("link", "")
        if target_domain.lower() in result_url.lower():
            rank = i
            url = result_url
            break

    now = datetime.utcnow().isoformat()
    return {
        "keyword": keyword,
        "location": location,
        "rank": rank,
        "url": url,
        "serp_date": date.today().isoformat(),
        "created_at": now,
    }


def _generate_mock_rankings(keywords: list[str], location: str) -> list[dict]:
    """
    Generate realistic mock rankings for demo purposes when no SerpAPI key is set.
    """
    import random
    rng = random.Random("blue-seo-mock")
    now = datetime.utcnow().isoformat()
    today = date.today().isoformat()

    rankings = []
    for keyword in keywords:
        rank = rng.randint(3, 25)
        rankings.append({
            "keyword": keyword,
            "location": location,
            "rank": rank,
            "url": "https://www.bluecarrental.is/",
            "serp_date": today,
            "created_at": now,
        })
    return rankings


@router.get("/rankings")
async def get_rankings(
    keyword: Optional[str] = Query(None),
    location: Optional[str] = Query(None),
):
    """
    Return the current (most recent) keyword rankings with change vs. previous check.
    """
    stored_kws = await get_stored_keywords()
    rankings = await get_latest_rankings(keyword=keyword, location=location)
    previous = await get_previous_rankings()

    api_key = await get_config("serpapi_key", "")
    has_api_key = bool(api_key and api_key.strip())

    # Filter to only currently tracked keywords (removes stale DB records)
    if rankings:
        filter_set = {keyword.lower()} if keyword else {k.lower() for k in stored_kws}
        rankings = [r for r in rankings if r["keyword"].lower() in filter_set]

    # If no data yet, return mock rankings so the dashboard is populated
    if not rankings:
        mock_location = location or DEFAULT_LOCATION
        mock_keywords = [keyword] if keyword else stored_kws
        rankings = _generate_mock_rankings(mock_keywords, mock_location)
        source = "mock"
    else:
        source = "database"

    # Attach change info
    enriched = []
    for r in rankings:
        prev = previous.get(r["keyword"])
        change = None
        if prev is not None and r["rank"] is not None:
            change = prev - r["rank"]  # positive = moved up (better rank)
        enriched.append({**r, "previous_rank": prev, "change": change})

    return {
        "rankings": enriched,
        "has_api_key": has_api_key,
        "source": source,
    }


@router.post("/check")
async def check_rankings(
    location: Optional[str] = Query(None),
):
    """
    Trigger a live rank check via SerpAPI for all configured keywords.
    Requires SERPAPI_KEY to be set in config or .env.
    """
    api_key = await get_config("serpapi_key", "")

    # Also check env var as fallback
    if not api_key or not api_key.strip():
        import os
        api_key = os.getenv("SERPAPI_KEY", "")

    if not api_key or not api_key.strip():
        raise HTTPException(
            status_code=400,
            detail="SerpAPI key not configured. Add SERPAPI_KEY to your .env file or configure it in Settings.",
        )

    check_location = location or DEFAULT_LOCATION
    keywords = await get_stored_keywords()

    async with httpx.AsyncClient() as client:
        tasks = [
            _check_keyword_rank(client, api_key, kw, check_location)
            for kw in keywords
        ]
        results = await asyncio.gather(*tasks, return_exceptions=True)

    successful = []
    errors = []
    for kw, result in zip(keywords, results):
        if isinstance(result, Exception):
            errors.append({"keyword": kw, "error": str(result)})
        else:
            successful.append(result)

    if successful:
        await insert_rankings(successful)

    return {
        "checked": len(successful),
        "keywords": keywords,
        "errors": errors,
        "message": f"Checked {len(successful)}/{len(keywords)} keywords in {check_location}.",
    }


@router.get("/history")
async def get_history(
    keyword: Optional[str] = Query(None),
    location: Optional[str] = Query(None),
    days: int = Query(30, ge=1, le=365),
):
    """
    Return ranking history for trend charts.
    """
    history = await get_rankings_history(keyword=keyword, location=location, days=days)

    if not history:
        # Generate synthetic history for the chart demo
        import random
        rng = random.Random("seo-history")
        today = date.today()
        mock_location = location or DEFAULT_LOCATION

        stored_kws = await get_stored_keywords()
        mock_keywords = [keyword] if keyword else stored_kws
        history = []
        for kw in mock_keywords:
            base_rank = rng.randint(5, 20)
            for i in range(min(days, 14)):
                day = today - timedelta(days=days - i)
                # Slight rank variation day to day
                rank = max(1, base_rank + rng.randint(-2, 2))
                history.append({
                    "keyword": kw,
                    "location": mock_location,
                    "rank": rank,
                    "url": "https://www.bluecarrental.is/",
                    "serp_date": day.isoformat(),
                    "created_at": day.isoformat() + "T08:00:00",
                })

        return {"history": history, "source": "mock"}

    return {"history": history, "source": "database"}


@router.post("/cleanup")
async def cleanup_stale_rankings():
    """Delete DB ranking records for keywords no longer in the tracked list."""
    from database import aiosqlite, DB_PATH
    stored = await get_stored_keywords()
    stored_set = {k.lower() for k in stored}

    # Find all keywords currently in the DB
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT DISTINCT keyword FROM rankings") as cursor:
            db_keywords = [row["keyword"] for row in await cursor.fetchall()]

    stale = [k for k in db_keywords if k.lower() not in stored_set]
    deleted = await delete_rankings_for_keywords(stale) if stale else 0

    return {
        "stale_keywords": stale,
        "rows_deleted": deleted,
        "message": f"Removed {deleted} records for {len(stale)} stale keyword(s).",
    }


@router.get("/keywords")
async def get_keywords():
    """Return the list of tracked keywords."""
    return {"keywords": await get_stored_keywords()}


@router.post("/keywords")
async def add_keyword(keyword: str = Query(...)):
    """Add a keyword to the tracked list."""
    kw = keyword.strip().lower()
    if not kw:
        raise HTTPException(400, "Keyword cannot be empty")
    keywords = await get_stored_keywords()
    if kw in keywords:
        raise HTTPException(409, "Keyword already tracked")
    if len(keywords) >= 20:
        raise HTTPException(400, "Maximum 20 keywords allowed")
    keywords.append(kw)
    await set_config("seo_keywords", json.dumps(keywords))
    return {"keywords": keywords, "message": f"Added: {kw}"}


@router.delete("/keywords/{keyword:path}")
async def remove_keyword(keyword: str):
    """Remove a keyword from the tracked list."""
    kw = keyword.strip().lower()
    keywords = await get_stored_keywords()
    if kw not in keywords:
        raise HTTPException(404, "Keyword not found")
    if len(keywords) <= 1:
        raise HTTPException(400, "Must keep at least one keyword")
    keywords.remove(kw)
    await set_config("seo_keywords", json.dumps(keywords))
    await delete_rankings_for_keywords([kw])  # purge stale DB records
    return {"keywords": keywords, "message": f"Removed: {kw}"}
