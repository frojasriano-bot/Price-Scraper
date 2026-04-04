"""
Price alert API – checks if competitors undercut Blue Car Rental
by more than a configured threshold and fires a Slack webhook.
"""

import httpx
from fastapi import APIRouter
from pydantic import BaseModel
from typing import Optional

from database import get_config, set_config, get_latest_rates

router = APIRouter(prefix="/api/alerts", tags=["alerts"])


class AlertConfig(BaseModel):
    webhook_url: Optional[str] = None
    threshold_pct: Optional[float] = None


@router.get("/config")
async def get_alert_config():
    """Return current alert configuration."""
    webhook_url = await get_config("alert_webhook_url", "")
    threshold_pct = await get_config("alert_threshold_pct", "10")
    return {
        "webhook_url": webhook_url,
        "threshold_pct": float(threshold_pct),
        "webhook_set": bool(webhook_url and webhook_url.strip()),
    }


@router.post("/config")
async def save_alert_config(payload: AlertConfig):
    """Save alert configuration."""
    if payload.webhook_url is not None:
        await set_config("alert_webhook_url", payload.webhook_url.strip())
    if payload.threshold_pct is not None:
        await set_config("alert_threshold_pct", str(payload.threshold_pct))
    return {"message": "Alert config saved."}


@router.post("/check")
async def check_alerts():
    """
    Compare latest scraped rates. If any competitor undercuts Blue Car Rental
    by >= threshold_pct on any category, send a Slack webhook notification.
    """
    webhook_url = await get_config("alert_webhook_url", "")
    threshold_pct = float(await get_config("alert_threshold_pct", "10"))

    rates = await get_latest_rates()

    # Group by category: find Blue rates and competitor rates
    blue_rates: dict[str, int] = {}      # category -> min price
    comp_rates: dict[str, dict[str, int]] = {}  # category -> {competitor -> min price}

    for r in rates:
        cat   = r["car_category"]
        price = r["price_isk"]
        comp  = r["competitor"]

        if comp == "Blue Car Rental":
            if cat not in blue_rates or price < blue_rates[cat]:
                blue_rates[cat] = price
        else:
            comp_rates.setdefault(cat, {})
            if comp not in comp_rates[cat] or price < comp_rates[cat][comp]:
                comp_rates[cat][comp] = price

    alerts_fired = []

    for cat, blue_price in blue_rates.items():
        for comp, comp_price in comp_rates.get(cat, {}).items():
            if blue_price <= 0:
                continue
            diff_pct = ((blue_price - comp_price) / blue_price) * 100
            if diff_pct >= threshold_pct:
                alerts_fired.append({
                    "category":    cat,
                    "competitor":  comp,
                    "blue_price":  blue_price,
                    "comp_price":  comp_price,
                    "diff_pct":    round(diff_pct, 1),
                })

    webhook_sent = False
    webhook_error: Optional[str] = None
    if alerts_fired and webhook_url:
        lines = [f"🚨 *Car Rental Price Alert* — {len(alerts_fired)} undercutting issue(s) detected\n"]
        for a in alerts_fired:
            lines.append(
                f"• *{a['category']}*: {a['competitor']} is {a['diff_pct']}% cheaper "
                f"({a['comp_price']:,} ISK vs your {a['blue_price']:,} ISK/week)"
            )
        message = {"text": "\n".join(lines)}
        async with httpx.AsyncClient(timeout=10) as client:
            try:
                resp = await client.post(webhook_url, json=message)
                resp.raise_for_status()
                webhook_sent = True
            except Exception as e:
                webhook_error = str(e)

    return {
        "alerts_fired":  len(alerts_fired),
        "alerts":        alerts_fired,
        "webhook_sent":  webhook_sent,
        "webhook_error": webhook_error,
        "threshold_pct": threshold_pct,
    }
