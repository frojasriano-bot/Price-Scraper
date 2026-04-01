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

from database import init_db, get_config, set_config
from routes.rates import router as rates_router
from routes.seo import router as seo_router
from routes.settings import router as settings_router

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
    from scrapers import ALL_SCRAPERS
    from database import insert_rates
    from datetime import date, timedelta, datetime

    logger.info("Scheduled scrape starting...")
    pickup = (date.today() + timedelta(days=7)).isoformat()
    ret = (date.today() + timedelta(days=10)).isoformat()

    all_rates = []
    for ScraperClass in ALL_SCRAPERS:
        async with ScraperClass() as scraper:
            try:
                rates = await scraper.run(pickup_date=pickup, return_date=ret)
                all_rates.extend(rates)
            except Exception as e:
                logger.warning(f"Scraper {ScraperClass.__name__} failed: {e}")

    if all_rates:
        await insert_rates(all_rates)
        await set_config("last_scrape_at", datetime.utcnow().isoformat())
        logger.info(f"Scheduled scrape complete: {len(all_rates)} rate records stored.")
    else:
        logger.warning("Scheduled scrape returned no results.")


async def scheduled_seo_check():
    """Check SEO rankings via SerpAPI — called by APScheduler."""
    from routes.seo import DEFAULT_KEYWORDS, DEFAULT_LOCATION, _check_keyword_rank
    from database import insert_rankings
    import httpx

    api_key = await get_config("serpapi_key", "")
    if not api_key:
        api_key = os.getenv("SERPAPI_KEY", "")

    if not api_key:
        logger.info("Scheduled SEO check skipped: no SerpAPI key configured.")
        return

    logger.info("Scheduled SEO check starting...")
    async with httpx.AsyncClient() as client:
        tasks = [
            _check_keyword_rank(client, api_key, kw, DEFAULT_LOCATION)
            for kw in DEFAULT_KEYWORDS
        ]
        results = await asyncio.gather(*tasks, return_exceptions=True)

    successful = [r for r in results if not isinstance(r, Exception)]
    if successful:
        await insert_rankings(successful)
        logger.info(f"SEO check complete: {len(successful)}/{len(DEFAULT_KEYWORDS)} keywords checked.")


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
    logger.info(f"Scheduler configured: {schedule} schedule active.")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application startup and shutdown lifecycle."""
    # Initialize the database
    await init_db()
    logger.info("Database initialized.")

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
