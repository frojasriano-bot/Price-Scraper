"""
API routes for fleet pressure monitoring.
Covers Caren-based competitors: Blue Car Rental, Lotus, Lava.
"""

from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Query

from database import (
    get_fleet_pressure,
    get_fleet_pressure_latest,
    insert_fleet_pressure,
)
from scrapers.fleet_pressure import poll_fleet_pressure

router = APIRouter(prefix="/api/fleet", tags=["fleet"])


@router.get("/pressure")
async def fleet_pressure_history(
    location:     Optional[str] = Query(None),
    days:         int           = Query(30, ge=1, le=90),
    window_label: Optional[str] = Query(None, description="1w | 2w | 4w"),
):
    """
    Time-series of fleet availability for Caren-based competitors.
    Each record: scraped_at, competitor, location, window_label,
                 total_classes, available_classes, availability_pct.
    """
    records = await get_fleet_pressure(
        location=location,
        days=days,
        window_label=window_label,
    )
    return {"records": records, "count": len(records)}


@router.get("/pressure/latest")
async def fleet_pressure_snapshot(
    location: Optional[str] = Query(None),
):
    """Most-recent availability snapshot per competitor × location × window."""
    records = await get_fleet_pressure_latest(location=location)
    return {"records": records}


@router.post("/poll")
async def poll_fleet_now():
    """Manually trigger a fleet pressure poll and persist results."""
    records = await poll_fleet_pressure()
    if records:
        await insert_fleet_pressure(records)
    return {
        "polled":  len(records),
        "message": f"Fleet pressure updated: {len(records)} records collected.",
    }
