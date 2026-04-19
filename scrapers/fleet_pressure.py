"""
Fleet pressure poller — Caren competitors (Blue/Lotus/Lava) + Go Car Rental.

Caren API (showAll=true): returns Available: true/false + full Name per class.
Go Car Rental: POST API returns available: true/false per class; names via Sanity CMS.

Public entry points:
  poll_fleet_pressure() → {"aggregate": [...], "models": [...]}
      Covers 1w / 2w / 4w forward windows across all locations.

  poll_fleet_calendar() → {"calendar": [...], "models": [...]}
      Sweeps the 15th of each of the next 12 months (Keflavik Airport).
"""

from __future__ import annotations

import asyncio
import logging
from datetime import date, timedelta

import httpx

logger = logging.getLogger("blue_rental.fleet_pressure")

# ── Caren competitor definitions ──────────────────────────────────────────────

_CAREN_COMPETITORS: list[dict] = [
    {
        "name": "Blue Car Rental",
        "url":  "https://www.bluecarrental.is/_carenapix/class/",
        "locations": {
            "Keflavik Airport": (44, 418),
            "Reykjavik":        (51, 419),
        },
        "response_key": "Classes",
        "extra_params": {
            "ClassIds":       "",
            "showGroupNames": "false",
            "couponCode":     "",
        },
    },
    {
        "name": "Lotus Car Rental",
        "url":  "https://www.lotuscarrental.is/_carenapix/class/",
        "locations": {
            "Keflavik Airport": (486, 487),
        },
        "response_key": "Classes",
        "extra_params": {
            "showGroupNames": "true",
            "couponCode":     "",
        },
    },
    {
        "name": "Lava Car Rental",
        "url":  "https://www.lavacarrental.is/_plugins/carenapi/class",
        "locations": {
            "Keflavik Airport": (239, 239),
        },
        "response_key": "Classes",
        "extra_params": {
            "showGroupNames": "true",
        },
        "extra_headers": {
            "Referer": "https://www.lavacarrental.is/book/cars",
        },
    },
]

# ── Go Car Rental ─────────────────────────────────────────────────────────────

_GOCAR_API_URL    = "https://api.gorentals.is/functions/v1/public/classes"
_GOCAR_SANITY_URL = "https://a4mln02c.api.sanity.io/v2022-03-07/data/query/production"
_GOCAR_SANITY_Q   = (
    '*[_type == "carenVehicleBase" && defined(model)]{'
    'id, model, "brand": brand->title[_key=="en"][0].value}'
)
_GOCAR_LOCATIONS: dict[str, tuple[int, int]] = {
    "Keflavik Airport": (10, 11),
}

# ── Booking windows ───────────────────────────────────────────────────────────

_WINDOWS: list[tuple[str, int]] = [
    ("1w",  7),
    ("2w", 14),
    ("4w", 28),
]
_DURATION_DAYS = 7


# ── Helpers ───────────────────────────────────────────────────────────────────

async def _get_gocar_class_info(client: httpx.AsyncClient) -> dict[int, str]:
    """Return {class_id: car_name} from Go Car's Sanity CMS."""
    try:
        resp = await client.get(
            _GOCAR_SANITY_URL,
            params={"query": _GOCAR_SANITY_Q},
            timeout=15,
        )
        resp.raise_for_status()
        items = resp.json().get("result", [])
        mapping: dict[int, str] = {}
        for item in items:
            id_   = item.get("id")
            brand = item.get("brand") or ""
            model = item.get("model") or ""
            name  = f"{brand} {model}".strip()
            if id_ and name:
                mapping[id_] = name
        return mapping
    except Exception as exc:
        logger.warning("Go Car Sanity lookup failed: %s", exc)
        return {}


async def _poll_caren_one(
    client:       httpx.AsyncClient,
    comp:         dict,
    location:     str,
    pickup_id:    int,
    dropoff_id:   int,
    pickup_date:  str,
    return_date:  str,
    window_label: str,
) -> dict | None:
    """Poll one Caren competitor for one window. Returns aggregate + model list."""
    params = {
        "dateFrom":          f"{pickup_date} 12:00",
        "dateTo":            f"{return_date} 12:00",
        "pickupLocationId":  str(pickup_id),
        "dropoffLocationId": str(dropoff_id),
        "showAll":           "true",
        "showImages":        "false",
        "language":          "en",
        **comp.get("extra_params", {}),
    }
    headers = dict(comp.get("extra_headers", {}))

    try:
        resp = await client.get(comp["url"], params=params, headers=headers, timeout=20)
        resp.raise_for_status()
        payload = resp.json()

        classes: list[dict] = (
            payload.get(comp["response_key"], []) if isinstance(payload, dict) else payload
        )
        if not classes:
            return None

        total     = len(classes)
        available = sum(1 for c in classes if c.get("Available", False))

        models = [
            {
                "competitor":   comp["name"],
                "location":     location,
                "pickup_date":  pickup_date,
                "return_date":  return_date,
                "window_label": window_label,
                "car_name":     (
                    c.get("Name") or c.get("name") or f"Class {c.get('Id', '?')}"
                ),
                "class_id":     str(c.get("Id", "")),
                "is_available": bool(c.get("Available", False)),
            }
            for c in classes
        ]

        return {
            "aggregate": {
                "competitor":           comp["name"],
                "location":             location,
                "pickup_date":          pickup_date,
                "return_date":          return_date,
                "window_label":         window_label,
                "total_classes":        total,
                "available_classes":    available,
                "unavailable_classes":  total - available,
                "availability_pct":     round(available / total * 100, 1),
            },
            "models": models,
        }
    except Exception as exc:
        logger.warning(
            "Caren fleet poll failed — %s @ %s (%s→%s): %s",
            comp["name"], location, pickup_date, return_date, exc,
        )
        return None


async def _poll_gocar_one(
    client:       httpx.AsyncClient,
    class_info:   dict[int, str],
    location:     str,
    pickup_id:    int,
    dropoff_id:   int,
    pickup_date:  str,
    return_date:  str,
    window_label: str,
) -> dict | None:
    """Poll Go Car Rental for one window. Returns aggregate + model list."""
    payload = {
        "rentalId":          7,
        "tenant":            "gocarrental",
        "ref":               "",
        "currency":          "ISK",
        "language":          "en",
        "dateFrom":          f"{pickup_date} 12:00",
        "dateTo":            f"{return_date} 12:00",
        "pickupLocationId":  pickup_id,
        "dropoffLocationId": dropoff_id,
        "couponCode":        "",
    }
    try:
        resp = await client.post(_GOCAR_API_URL, json=payload, timeout=20)
        resp.raise_for_status()
        classes = resp.json()
        if not isinstance(classes, list) or not classes:
            return None

        total     = len(classes)
        available = sum(1 for c in classes if c.get("available", True))

        models = []
        for c in classes:
            class_id = c.get("id")
            name = class_info.get(class_id, f"Class {class_id}")
            models.append({
                "competitor":   "Go Car Rental",
                "location":     location,
                "pickup_date":  pickup_date,
                "return_date":  return_date,
                "window_label": window_label,
                "car_name":     name,
                "class_id":     str(class_id) if class_id is not None else None,
                "is_available": bool(c.get("available", True)),
            })

        return {
            "aggregate": {
                "competitor":           "Go Car Rental",
                "location":             location,
                "pickup_date":          pickup_date,
                "return_date":          return_date,
                "window_label":         window_label,
                "total_classes":        total,
                "available_classes":    available,
                "unavailable_classes":  total - available,
                "availability_pct":     round(available / total * 100, 1),
            },
            "models": models,
        }
    except Exception as exc:
        logger.warning(
            "Go Car fleet poll failed @ %s (%s→%s): %s",
            location, pickup_date, return_date, exc,
        )
        return None


# ── Public entry points ───────────────────────────────────────────────────────

async def poll_fleet_pressure() -> dict:
    """
    Poll all Caren competitors + Go Car Rental across all locations and forward windows.
    Returns {"aggregate": [...], "models": [...]} ready for DB insertion.
    """
    today = date.today()
    aggregate_records: list[dict] = []
    model_records:     list[dict] = []

    async with httpx.AsyncClient(timeout=20, follow_redirects=True) as client:
        gocar_class_info = await _get_gocar_class_info(client)

        coros = []

        # Caren competitors
        for comp in _CAREN_COMPETITORS:
            for loc_name, (pickup_id, dropoff_id) in comp["locations"].items():
                for window_label, days_out in _WINDOWS:
                    pickup = today + timedelta(days=days_out)
                    ret    = pickup + timedelta(days=_DURATION_DAYS)
                    coros.append(_poll_caren_one(
                        client, comp, loc_name,
                        pickup_id, dropoff_id,
                        pickup.isoformat(), ret.isoformat(),
                        window_label,
                    ))

        # Go Car Rental
        for loc_name, (pickup_id, dropoff_id) in _GOCAR_LOCATIONS.items():
            for window_label, days_out in _WINDOWS:
                pickup = today + timedelta(days=days_out)
                ret    = pickup + timedelta(days=_DURATION_DAYS)
                coros.append(_poll_gocar_one(
                    client, gocar_class_info, loc_name,
                    pickup_id, dropoff_id,
                    pickup.isoformat(), ret.isoformat(),
                    window_label,
                ))

        results = await asyncio.gather(*coros, return_exceptions=True)

    for r in results:
        if isinstance(r, dict):
            if r.get("aggregate"):
                aggregate_records.append(r["aggregate"])
            model_records.extend(r.get("models", []))
        elif isinstance(r, Exception):
            logger.warning("Fleet poll task raised: %s", r)

    logger.info(
        "Fleet pressure poll complete: %d aggregate, %d model records.",
        len(aggregate_records), len(model_records),
    )
    return {"aggregate": aggregate_records, "models": model_records}


async def detect_fleet_absence(
    catalog: dict[str, list[str]],
    location: str = "Keflavik Airport",
) -> list[dict]:
    """
    For each of the next 12 anchor months (15th), scrape Hertz/Avis/Holdur and
    return absence records for catalog models not found in that month's results.

    Args:
        catalog: {competitor_name: [known_car_names]} — built from competitor_catalog table.
        location: Location to scrape (default Keflavik Airport).

    Returns:
        List of absence dicts ready for insert_fleet_absence().
    """
    from scrapers.hertz_is import HertzIsScraper
    from scrapers.avis_is import AvisIsScraper
    from scrapers.holdur import HoldurScraper

    absence_scrapers = [HertzIsScraper, AvisIsScraper, HoldurScraper]
    today = date.today()

    anchors: list[tuple[str, str]] = []
    for offset in range(12):
        total_month = today.month + offset
        year        = today.year + (total_month - 1) // 12
        month       = (total_month - 1) % 12 + 1
        pickup_d    = date(year, month, 15)
        ret_d       = pickup_d + timedelta(days=_DURATION_DAYS)
        anchors.append((pickup_d.isoformat(), ret_d.isoformat()))

    # Only sweep anchor dates that are at least 2 days in the future
    # (past dates return nothing → false all-absent for that month)
    min_date = (today + timedelta(days=2)).isoformat()
    anchors  = [(p, r) for p, r in anchors if p >= min_date]

    absences: list[dict] = []

    for pickup, ret in anchors:
        async def _scrape(Cls, p=pickup, r=ret):
            try:
                async with Cls() as scraper:
                    return await asyncio.wait_for(
                        scraper.scrape_rates(location, p, r), timeout=20
                    )
            except Exception as exc:
                logger.warning("Absence scrape failed — %s %s: %s", Cls.__name__, p, exc)
                return []

        rate_lists = await asyncio.gather(*[_scrape(Cls) for Cls in absence_scrapers])

        seen_by_comp: dict[str, set[str]] = {}
        for rate_list in rate_lists:
            for rate in rate_list:
                comp = rate.get("competitor", "")
                name = rate.get("car_model") or rate.get("canonical_name", "")
                if comp and name:
                    seen_by_comp.setdefault(comp, set()).add(name)

        for comp, known_models in catalog.items():
            seen = seen_by_comp.get(comp, set())
            for model in known_models:
                if model not in seen:
                    absences.append({
                        "competitor":    comp,
                        "location":      location,
                        "pickup_date":   pickup,
                        "return_date":   ret,
                        "car_name":      model,
                        "canonical_name": None,
                    })

    logger.info("Absence detection complete: %d inferred absences across 12 months.", len(absences))
    return absences


async def poll_fleet_calendar() -> dict:
    """
    Sweep the 15th of each of the next 12 months for Caren + Go Car (Keflavik Airport).
    Returns {"calendar": [...], "models": [...]} ready for DB insertion.
    """
    today    = date.today()
    location = "Keflavik Airport"

    # Build 12 anchor months
    anchors: list[tuple[str, str, str]] = []
    for offset in range(12):
        total_month = today.month + offset
        year        = today.year + (total_month - 1) // 12
        month       = (total_month - 1) % 12 + 1
        pickup_d    = date(year, month, 15)
        ret_d       = pickup_d + timedelta(days=_DURATION_DAYS)
        anchor_month = f"{year}-{month:02d}"
        anchors.append((anchor_month, pickup_d.isoformat(), ret_d.isoformat()))

    # Skip anchor dates already in the past (return nothing → empty rows)
    min_date = (today + timedelta(days=2)).isoformat()
    anchors  = [(m, p, r) for m, p, r in anchors if p >= min_date]

    calendar_records: list[dict] = []
    model_records:    list[dict] = []

    async with httpx.AsyncClient(timeout=20, follow_redirects=True) as client:
        gocar_class_info = await _get_gocar_class_info(client)

        # Build (anchor_month, coroutine) pairs to correlate results
        tagged: list[tuple[str, object]] = []

        for anchor_month, pickup_date, return_date in anchors:
            for comp in _CAREN_COMPETITORS:
                if location not in comp["locations"]:
                    continue
                pickup_id, dropoff_id = comp["locations"][location]
                tagged.append((anchor_month, _poll_caren_one(
                    client, comp, location,
                    pickup_id, dropoff_id,
                    pickup_date, return_date,
                    anchor_month,
                )))

            if location in _GOCAR_LOCATIONS:
                pickup_id, dropoff_id = _GOCAR_LOCATIONS[location]
                tagged.append((anchor_month, _poll_gocar_one(
                    client, gocar_class_info, location,
                    pickup_id, dropoff_id,
                    pickup_date, return_date,
                    anchor_month,
                )))

        results = await asyncio.gather(*[t[1] for t in tagged], return_exceptions=True)

    for i, r in enumerate(results):
        anchor_month = tagged[i][0]
        if isinstance(r, dict):
            agg = r.get("aggregate")
            if agg:
                calendar_records.append({**agg, "anchor_month": anchor_month})
            model_records.extend(r.get("models", []))
        elif isinstance(r, Exception):
            logger.warning("Fleet calendar task raised: %s", r)

    logger.info(
        "Fleet calendar poll complete: %d calendar, %d model records.",
        len(calendar_records), len(model_records),
    )
    return {"calendar": calendar_records, "models": model_records}
