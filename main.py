"""
Blue Rental Intelligence - Main Application Entry Point

A competitor rate intelligence + local SEO rank tracking dashboard
for an Icelandic car rental company.

Run with:
    python main.py

Then open: http://localhost:8000
"""

import os
import asyncio
import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, HTMLResponse
from dotenv import load_dotenv
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

from database import init_db, recanonicalize_all_rates, recategorize_all_rates, get_config, set_config
from routes.rates import router as rates_router
from routes.seo import router as seo_router
from routes.settings import router as settings_router
from routes.alerts import router as alerts_router
from routes.insurance import router as insurance_router
from routes.fleet import router as fleet_router

# Load environment variables from .env if present
load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("blue_rental")

# APScheduler instance (global so we can reconfigure from settings)
scheduler = AsyncIOScheduler()


async def scheduled_scrape():
    """Run all scrapers and store results — called by APScheduler."""
    import time
    from scrapers import ALL_SCRAPERS
    from database import insert_rates, log_scrape
    from datetime import date, timedelta, datetime

    logger.info("Scheduled scrape starting...")
    pickup = (date.today() + timedelta(days=7)).isoformat()
    ret = (date.today() + timedelta(days=10)).isoformat()

    all_rates = []
    errors = []
    started_at = time.monotonic()

    for ScraperClass in ALL_SCRAPERS:
        async with ScraperClass() as scraper:
            try:
                rates = await scraper.run(pickup_date=pickup, return_date=ret)
                all_rates.extend(rates)
            except Exception as e:
                err_msg = f"{ScraperClass.__name__}: {e}"
                logger.warning(f"Scraper {ScraperClass.__name__} failed: {e}")
                errors.append(err_msg)

    duration = time.monotonic() - started_at

    if all_rates:
        await insert_rates(all_rates)
        await set_config("last_scrape_at", datetime.utcnow().isoformat())
        logger.info(f"Scheduled scrape complete: {len(all_rates)} rate records stored.")
    else:
        logger.warning("Scheduled scrape returned no results.")

    await log_scrape(
        location=None,
        total_rates=len(all_rates),
        competitors=len(ALL_SCRAPERS),
        errors=errors,
        duration_seconds=duration,
        trigger="scheduled",
    )


async def scheduled_seasonal_scrape():
    """
    Scrape anchor dates (15th of each month) for the next 12 months and persist.
    Runs every Monday so the seasonal chart always has fresh weekly data points.
    """
    import time
    from scrapers import ALL_SCRAPERS
    from database import insert_rates, log_scrape, clear_seasonal_cache
    from datetime import date, timedelta

    logger.info("Scheduled seasonal scrape starting (12 anchor months)…")
    scrape_loc  = "Keflavik Airport"
    today       = date.today()
    started_at  = time.monotonic()
    total_rates = 0
    errors: list[str] = []

    for offset in range(12):
        total_month = today.month + offset
        year  = today.year + (total_month - 1) // 12
        month = (total_month - 1) % 12 + 1
        pickup = date(year, month, 15).isoformat()
        ret    = (date(year, month, 15) + timedelta(days=7)).isoformat()

        month_rates: list[dict] = []

        async def _scrape(ScraperClass, p=pickup, r=ret):
            async with ScraperClass() as scraper:
                try:
                    return await asyncio.wait_for(
                        scraper.scrape_rates(scrape_loc, p, r), timeout=15
                    )
                except Exception as e:
                    errors.append(f"{ScraperClass.__name__} {p}: {e}")
                    return []

        results = await asyncio.gather(*[_scrape(Cls) for Cls in ALL_SCRAPERS])
        for r_list in results:
            month_rates.extend(r_list)

        if month_rates:
            await insert_rates(month_rates)
            total_rates += len(month_rates)

    await clear_seasonal_cache()
    duration = time.monotonic() - started_at
    logger.info(f"Seasonal scrape complete: {total_rates} rates across 12 months in {duration:.1f}s.")

    await log_scrape(
        location=scrape_loc,
        total_rates=total_rates,
        competitors=len(ALL_SCRAPERS),
        errors=errors[:20],
        duration_seconds=duration,
        trigger="seasonal",
    )


async def scheduled_horizon_scrape():
    """
    Scrape the next 12 weekly pickup windows and persist — feeds the Forward Rates view.
    Runs daily at 07:15 (15 min after the main daily scrape).
    """
    import time
    from scrapers import ALL_SCRAPERS
    from database import insert_rates, log_scrape
    from datetime import date, timedelta

    logger.info("Scheduled horizon scrape starting (26 weeks)…")
    scrape_loc = "Keflavik Airport"
    today      = date.today()
    started_at = time.monotonic()
    total_rates = 0
    errors: list[str] = []

    for w in range(1, 27):
        pickup_d = today + timedelta(weeks=w)
        ret_d    = pickup_d + timedelta(days=7)
        pickup   = pickup_d.isoformat()
        ret      = ret_d.isoformat()

        async def _scrape(ScraperClass, p=pickup, r=ret):
            async with ScraperClass() as scraper:
                try:
                    return await asyncio.wait_for(
                        scraper.scrape_rates(scrape_loc, p, r), timeout=15
                    )
                except Exception as e:
                    errors.append(f"{ScraperClass.__name__} {p}: {e}")
                    return []

        results = await asyncio.gather(*[_scrape(Cls) for Cls in ALL_SCRAPERS])
        week_rates: list[dict] = []
        for r_list in results:
            week_rates.extend(r_list)

        if week_rates:
            await insert_rates(week_rates)
            total_rates += len(week_rates)

    duration = time.monotonic() - started_at
    logger.info(f"Horizon scrape complete: {total_rates} rates across 26 weeks in {duration:.1f}s.")

    await log_scrape(
        location=scrape_loc,
        total_rates=total_rates,
        competitors=len(ALL_SCRAPERS),
        errors=errors[:20],
        duration_seconds=duration,
        trigger="horizon",
    )


async def scheduled_fleet_poll():
    """Poll Caren competitors for fleet availability — called by APScheduler (twice daily)."""
    from scrapers.fleet_pressure import poll_fleet_pressure
    from database import insert_fleet_pressure

    logger.info("Scheduled fleet pressure poll starting...")
    try:
        records = await poll_fleet_pressure()
        if records:
            await insert_fleet_pressure(records)
            logger.info(f"Fleet pressure poll complete: {len(records)} records stored.")
        else:
            logger.warning("Fleet pressure poll returned no records.")
    except Exception as e:
        logger.error(f"Fleet pressure poll failed: {e}")


async def scheduled_alert_check():
    """Run price alert check after scrape — called by APScheduler."""
    from routes.alerts import check_alerts

    webhook_url = await get_config("alert_webhook_url", "")
    if not webhook_url:
        logger.info("Scheduled alert check skipped: no webhook URL configured.")
        return

    logger.info("Scheduled alert check starting...")
    try:
        result = await check_alerts()
        if result["alerts_fired"]:
            logger.info(
                f"Alert check: {result['alerts_fired']} alert(s) fired, "
                f"webhook_sent={result['webhook_sent']}"
            )
        else:
            logger.info("Alert check: no undercutting detected.")
    except Exception as e:
        logger.warning(f"Alert check failed: {e}")


async def scheduled_seo_check():
    """Check SEO rankings via SerpAPI — called by APScheduler."""
    from routes.seo import DEFAULT_LOCATION, _check_keyword_rank, get_stored_keywords
    from database import insert_rankings
    import httpx

    api_key = await get_config("serpapi_key", "")
    if not api_key:
        api_key = os.getenv("SERPAPI_KEY", "")

    if not api_key:
        logger.info("Scheduled SEO check skipped: no SerpAPI key configured.")
        return

    keywords = await get_stored_keywords()
    logger.info(f"Scheduled SEO check starting for {len(keywords)} keywords...")
    async with httpx.AsyncClient() as client:
        tasks = [
            _check_keyword_rank(client, api_key, kw, DEFAULT_LOCATION)
            for kw in keywords
        ]
        results = await asyncio.gather(*tasks, return_exceptions=True)

    successful = [r for r in results if not isinstance(r, Exception)]
    if successful:
        await insert_rankings(successful)
        logger.info(f"SEO check complete: {len(successful)}/{len(keywords)} keywords checked.")


def setup_scheduler(schedule: str = "daily"):
    """Configure and start the APScheduler with the given schedule."""
    scheduler.remove_all_jobs()

    if schedule == "hourly":
        scrape_trigger = CronTrigger(minute=0)
        seo_trigger = CronTrigger(minute=30)
    elif schedule == "weekly":
        scrape_trigger = CronTrigger(day_of_week="mon", hour=7, minute=0)
        seo_trigger = CronTrigger(day_of_week="mon", hour=7, minute=30)
    else:
        # Default: daily at 7:00 AM
        scrape_trigger = CronTrigger(hour=7, minute=0)
        seo_trigger = CronTrigger(hour=7, minute=30)

    scheduler.add_job(
        scheduled_scrape,
        trigger=scrape_trigger,
        id="scrape_rates",
        replace_existing=True,
        name="Competitor Rate Scrape",
    )
    scheduler.add_job(
        scheduled_seo_check,
        trigger=seo_trigger,
        id="seo_check",
        replace_existing=True,
        name="SEO Rank Check",
    )

    if schedule == "hourly":
        alert_trigger = CronTrigger(minute=45)
    elif schedule == "weekly":
        alert_trigger = CronTrigger(day_of_week="mon", hour=7, minute=45)
    else:
        alert_trigger = CronTrigger(hour=7, minute=45)

    scheduler.add_job(
        scheduled_alert_check,
        trigger=alert_trigger,
        id="alert_check",
        replace_existing=True,
        name="Price Alert Check",
    )
    # Seasonal scrape: always weekly on Monday 08:00, regardless of main schedule
    scheduler.add_job(
        scheduled_seasonal_scrape,
        trigger=CronTrigger(day_of_week="mon", hour=8, minute=0),
        id="scrape_seasonal",
        replace_existing=True,
        name="Seasonal Anchor Scrape (12 months)",
    )
    # Horizon scrape: daily at 07:15 (15 min after main scrape) — feeds Forward Rates view
    scheduler.add_job(
        scheduled_horizon_scrape,
        trigger=CronTrigger(hour=7, minute=15),
        id="scrape_horizon",
        replace_existing=True,
        name="Horizon Rate Scrape (26 weeks / 6 months)",
    )
    # Fleet pressure poll: twice daily (09:00 and 21:00) — lightweight, Caren only
    scheduler.add_job(
        scheduled_fleet_poll,
        trigger=CronTrigger(hour=9, minute=0),
        id="fleet_poll_morning",
        replace_existing=True,
        name="Fleet Pressure Poll (morning)",
    )
    scheduler.add_job(
        scheduled_fleet_poll,
        trigger=CronTrigger(hour=21, minute=0),
        id="fleet_poll_evening",
        replace_existing=True,
        name="Fleet Pressure Poll (evening)",
    )

    logger.info(f"Scheduler configured: {schedule} schedule active.")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application startup and shutdown lifecycle."""
    # Initialize the database
    await init_db()
    logger.info("Database initialized.")

    # Re-canonicalize stale names from before scraper/canonical fixes
    await recanonicalize_all_rates()
    # Re-categorize all rates using the canonical category map
    await recategorize_all_rates()

    # Load schedule preference from DB
    schedule = await get_config("scrape_schedule", "daily")
    setup_scheduler(schedule)

    if not scheduler.running:
        scheduler.start()
        logger.info("APScheduler started.")

    logger.info("Blue Rental Intelligence is ready. Open http://localhost:8000")

    yield

    # Shutdown
    if scheduler.running:
        scheduler.shutdown(wait=False)
        logger.info("APScheduler stopped.")


# Create the FastAPI application
app = FastAPI(
    title="Blue Rental Intelligence",
    description="Competitor rate intelligence + local SEO rank tracking for Icelandic car rental.",
    version="1.0.0",
    lifespan=lifespan,
)

# CORS — allow all origins for local development
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# API routes
app.include_router(rates_router)
app.include_router(seo_router)
app.include_router(settings_router)
app.include_router(alerts_router)
app.include_router(insurance_router)
app.include_router(fleet_router)

# Serve static files (the SPA dashboard)
static_dir = Path(__file__).parent / "static"
app.mount("/static", StaticFiles(directory=static_dir), name="static")


@app.get("/")
async def serve_dashboard():
    """Serve the main dashboard SPA with cache-busting version tokens."""
    index_path = static_dir / "index.html"
    js_path    = static_dir / "app.js"
    css_path   = static_dir / "style.css"

    js_ver  = str(int(js_path.stat().st_mtime))  if js_path.exists()  else "0"
    css_ver = str(int(css_path.stat().st_mtime)) if css_path.exists() else "0"

    html = index_path.read_text(encoding="utf-8")
    html = html.replace("__JS_VERSION__",  js_ver)
    html = html.replace("__CSS_VERSION__", css_ver)

    return HTMLResponse(content=html, headers={"Cache-Control": "no-store"})


@app.get("/api/health")
async def health():
    """Health check endpoint."""
    return {"status": "ok", "app": "Blue Rental Intelligence"}


@app.get("/api/scheduler/status")
async def scheduler_status():
    """Return current APScheduler state: schedule, next run, last run."""
    last_scrape = await get_config("last_scrape_at", None)
    schedule    = await get_config("scrape_schedule", "daily")

    scrape_job = scheduler.get_job("scrape_rates")
    next_run   = None
    if scrape_job and scrape_job.next_run_time:
        next_run = scrape_job.next_run_time.isoformat()

    return {
        "is_running":    scheduler.running,
        "schedule":      schedule,
        "last_scrape_at": last_scrape,
        "next_run":      next_run,
    }


@app.post("/api/scheduler/reconfigure")
async def reconfigure_scheduler(schedule: str = "daily"):
    """Reconfigure the scheduler without restarting the app."""
    valid = ["hourly", "daily", "weekly"]
    if schedule not in valid:
        from fastapi import HTTPException
        raise HTTPException(400, f"Invalid schedule. Choose from: {valid}")
    setup_scheduler(schedule)
    return {"message": f"Scheduler reconfigured to: {schedule}"}


if __name__ == "__main__":
    import uvicorn

    host = os.getenv("APP_HOST", "0.0.0.0")
    port = int(os.getenv("APP_PORT", "8000"))
    debug = os.getenv("DEBUG", "true").lower() == "true"

    uvicorn.run(
        "main:app",
        host=host,
        port=port,
        reload=debug,
        log_level="info",
    )
