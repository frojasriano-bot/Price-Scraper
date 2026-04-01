# Overview

Blue Rental Intelligence is composed of three layers:

1. **FastAPI backend** (`main.py`, `routes/`)
   - Serves the SPA dashboard from `static/`
   - Exposes JSON API endpoints under `/api`
   - Initializes the SQLite database on startup
   - Starts APScheduler jobs for periodic scraping and SEO checks

2. **Data layer** (`database.py`)
   - Async SQLite access via `aiosqlite`
   - Schema initialization + default configuration seeding
   - Helper queries for rates matrices, history, deltas, rankings history, etc.

3. **Scrapers** (`scrapers/`)
   - Each competitor scraper implements `scrape_rates()`
   - When live scraping is not configured, the backend falls back to deterministic mock data (based on `FLEET` and date/season multipliers)

## Dashboard

The dashboard is a static SPA served from:
- `static/index.html`
- `static/app.js`
- `static/style.css`

The SPA calls the backend API directly (no separate frontend server).

