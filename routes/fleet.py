"""
API routes for fleet pressure monitoring.
Covers Caren-based competitors (Blue, Lotus, Lava) + Go Car Rental.
"""

from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Query

from database import (
    get_fleet_pressure,
    get_fleet_pressure_latest,
    insert_fleet_pressure,
    insert_fleet_sold_out_models,
    get_fleet_sold_out_models,
    insert_fleet_calendar,
    get_fleet_calendar,
    get_fleet_absence,
    get_competitor_catalog,
    insert_fleet_absence,
)
from scrapers.fleet_pressure import poll_fleet_pressure, poll_fleet_calendar, detect_fleet_absence

router = APIRouter(prefix="/api/fleet", tags=["fleet"])


@router.get("/pressure")
async def fleet_pressure_history(
    location:     Optional[str] = Query(None),
    days:         int           = Query(30, ge=1, le=90),
    window_label: Optional[str] = Query(None, description="1w | 2w | 4w"),
):
    """Time-series of fleet availability for Caren-based competitors + Go Car."""
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
    result = await poll_fleet_pressure()
    if result["aggregate"]:
        await insert_fleet_pressure(result["aggregate"])
    if result["models"]:
        await insert_fleet_sold_out_models(result["models"])
    n_agg = len(result["aggregate"])
    n_mod = len(result["models"])
    return {
        "polled":  n_agg,
        "models":  n_mod,
        "message": f"Fleet pressure updated: {n_agg} windows, {n_mod} model records.",
    }


@router.get("/sold-out")
async def fleet_sold_out_models(
    competitor:   Optional[str] = Query(None),
    location:     Optional[str] = Query(None),
    window_label: Optional[str] = Query(None, description="1w | 2w | 4w"),
):
    """Latest per-model availability snapshot — shows which specific models are sold out."""
    records = await get_fleet_sold_out_models(
        competitor=competitor,
        location=location,
        window_label=window_label,
    )
    return {"records": records}


@router.get("/calendar")
async def fleet_availability_calendar(
    location: Optional[str] = Query(None),
):
    """
    12-month availability calendar for Caren + Go Car.
    Each row: competitor × anchor_month with availability_pct + sold_out_models list.
    """
    calendar = await get_fleet_calendar(location=location)
    sold_out  = await get_fleet_sold_out_models(location=location)

    # Build lookup: (competitor, anchor_month) → [sold-out car names]
    so_map: dict[str, list[str]] = {}
    for r in sold_out:
        if not r["is_available"]:
            key = f"{r['competitor']}|{r['window_label']}"
            so_map.setdefault(key, []).append(r["car_name"])

    for row in calendar:
        key = f"{row['competitor']}|{row['anchor_month']}"
        row["sold_out_models"] = sorted(so_map.get(key, []))

    return {"records": calendar}


@router.post("/calendar/poll")
async def poll_fleet_calendar_now():
    """
    Manually trigger the full 12-month fleet intelligence sweep:
      1. Caren + Go Car availability calendar
      2. Absence detection for Hertz, Avis, Holdur
    """
    # Step 1: Caren + Go Car calendar sweep
    result = await poll_fleet_calendar()
    if result["calendar"]:
        await insert_fleet_calendar(result["calendar"])
    if result["models"]:
        await insert_fleet_sold_out_models(result["models"])

    # Step 2: Absence detection for Hertz / Avis / Holdur
    absence_competitors = {"Hertz Iceland", "Avis Iceland", "Holdur"}
    catalog_entries = await get_competitor_catalog()
    catalog: dict[str, list[str]] = {}
    for entry in catalog_entries:
        if entry["competitor"] in absence_competitors:
            catalog.setdefault(entry["competitor"], []).append(entry["car_name"])

    n_abs = 0
    if catalog:
        absences = await detect_fleet_absence(catalog)
        if absences:
            await insert_fleet_absence(absences)
            n_abs = len(absences)

    n_cal = len(result["calendar"])
    n_mod = len(result["models"])
    return {
        "calendar": n_cal,
        "models":   n_mod,
        "absences": n_abs,
        "message":  f"Calendar: {n_cal} month snapshots · {n_mod} model records · {n_abs} absence signals.",
    }


@router.get("/absence")
async def fleet_absence_alerts(
    competitor: Optional[str] = Query(None),
    location:   Optional[str] = Query(None),
    days:       int           = Query(90, ge=1, le=365),
):
    """
    Absence-inferred sold-out events for Hertz, Avis, Holdur.
    These are weaker signals — a model missing from scrape results for a given month.
    """
    records = await get_fleet_absence(
        competitor=competitor,
        location=location,
        days=days,
    )
    return {"records": records, "count": len(records)}
