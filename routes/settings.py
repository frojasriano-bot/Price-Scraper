"""
API routes for application settings.
"""

import json
from datetime import datetime

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional, List

from database import get_config, set_config, get_category_audit

router = APIRouter(prefix="/api/settings", tags=["settings"])


class Location(BaseModel):
    name: str
    address: str


class SettingsUpdate(BaseModel):
    serpapi_key: Optional[str] = None
    scrape_schedule: Optional[str] = None
    locations: Optional[List[Location]] = None


@router.get("")
async def get_settings():
    """Return current application settings."""
    serpapi_key = await get_config("serpapi_key", "")
    scrape_schedule = await get_config("scrape_schedule", "daily")
    locations_raw = await get_config("locations", "[]")

    try:
        locations = json.loads(locations_raw)
    except (json.JSONDecodeError, TypeError):
        locations = []

    return {
        "serpapi_key": serpapi_key,
        "scrape_schedule": scrape_schedule,
        "locations": locations,
        # Mask the key for display — only show if it exists
        "serpapi_key_set": bool(serpapi_key and serpapi_key.strip()),
    }


@router.post("")
async def update_settings(payload: SettingsUpdate):
    """Update application settings."""
    updated = []

    if payload.serpapi_key is not None:
        await set_config("serpapi_key", payload.serpapi_key.strip())
        updated.append("serpapi_key")

    if payload.scrape_schedule is not None:
        valid_schedules = ["hourly", "daily", "weekly"]
        if payload.scrape_schedule not in valid_schedules:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid schedule. Must be one of: {valid_schedules}",
            )
        await set_config("scrape_schedule", payload.scrape_schedule)
        updated.append("scrape_schedule")

    if payload.locations is not None:
        locations_data = [loc.dict() for loc in payload.locations]
        await set_config("locations", json.dumps(locations_data))
        updated.append("locations")

    return {
        "message": "Settings updated successfully.",
        "updated_fields": updated,
    }


@router.get("/category-audit")
async def category_audit():
    """
    Return category audit data showing every canonical car name, its DB
    category, the correct canonical category, and whether they match.
    """
    rows = await get_category_audit()

    # Build summary stats
    total_models = len(set(r["canonical_name"] for r in rows))
    mapped = len(set(r["canonical_name"] for r in rows if r["is_mapped"]))
    unmapped = total_models - mapped
    conflicts = len(set(r["canonical_name"] for r in rows if not r["is_correct"]))

    return {
        "summary": {
            "total_models": total_models,
            "mapped": mapped,
            "unmapped": unmapped,
            "conflicts": conflicts,
        },
        "rows": rows,
    }
