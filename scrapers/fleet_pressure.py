"""
Fleet pressure poller — Caren-based competitors only.

Calls each Caren endpoint with showAll=true so we get every car class
(available AND unavailable). Counting Available=false classes is a direct
proxy for fleet utilization: more unavailable = higher demand / tighter supply.

Competitors covered:
  - Blue Car Rental  (bluecarrental.is  /_carenapix/class/)
  - Lotus Car Rental (lotuscarrental.is /_carenapix/class/)
  - Lava Car Rental  (lavacarrental.is  /_plugins/carenapi/class)

We poll three forward rental windows (1 week, 2 weeks, 4 weeks out) at each
run so the dashboard can show whether near-term vs mid-term inventory differs.
"""

from __future__ import annotations

import asyncio
import logging
from datetime import date, timedelta

import httpx

logger = logging.getLogger("blue_rental.fleet_pressure")

# ── Competitor definitions ────────────────────────────────────────────────────

_COMPETITORS: list[dict] = [
    {
        "name":      "Blue Car Rental",
        "url":       "https://www.bluecarrental.is/_carenapix/class/",
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
        "name":      "Lotus Car Rental",
        "url":       "https://www.lotuscarrental.is/_carenapix/class/",
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
        "name":      "Lava Car Rental",
        "url":       "https://www.lavacarrental.is/_plugins/carenapi/class",
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

# Rental windows to check at each poll (days from today)
_WINDOWS: list[tuple[str, int]] = [
    ("1w",  7),
    ("2w", 14),
    ("4w", 28),
]
_DURATION_DAYS = 7


# ── Single-request helper ─────────────────────────────────────────────────────

async def _poll_one(
    client: httpx.AsyncClient,
    comp: dict,
    location: str,
    pickup_id: int,
    dropoff_id: int,
    pickup_date: str,
    return_date: str,
    window_label: str,
) -> dict | None:
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

        return {
            "competitor":          comp["name"],
            "location":            location,
            "pickup_date":         pickup_date,
            "return_date":         return_date,
            "window_label":        window_label,
            "total_classes":       total,
            "available_classes":   available,
            "unavailable_classes": total - available,
            "availability_pct":    round(available / total * 100, 1),
        }
    except Exception as exc:
        logger.warning(
            "Fleet poll failed — %s @ %s (%s→%s): %s",
            comp["name"], location, pickup_date, return_date, exc,
        )
        return None


# ── Public entry point ────────────────────────────────────────────────────────

async def poll_fleet_pressure() -> list[dict]:
    """
    Poll all Caren competitors across all locations and forward windows.
    Returns a flat list of records ready for DB insertion.
    """
    today   = date.today()
    records = []

    async with httpx.AsyncClient(timeout=20, follow_redirects=True) as client:
        tasks = []
        meta  = []

        for comp in _COMPETITORS:
            for loc_name, (pickup_id, dropoff_id) in comp["locations"].items():
                for window_label, days_out in _WINDOWS:
                    pickup = today + timedelta(days=days_out)
                    ret    = pickup + timedelta(days=_DURATION_DAYS)
                    tasks.append(
                        _poll_one(
                            client, comp, loc_name,
                            pickup_id, dropoff_id,
                            pickup.isoformat(), ret.isoformat(),
                            window_label,
                        )
                    )

        results = await asyncio.gather(*tasks, return_exceptions=True)

    for r in results:
        if isinstance(r, dict):
            records.append(r)
        elif isinstance(r, Exception):
            logger.warning("Fleet poll task raised: %s", r)

    logger.info("Fleet pressure poll complete: %d records collected.", len(records))
    return records
