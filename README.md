# Blue Rental Intelligence

Competitor car rental **rate intelligence** + **local SEO rank tracking** for an Icelandic car rental company.

This repo is a FastAPI backend that serves a single-page dashboard from the `static/` folder and exposes a JSON API under `/api/*`.

## Demo

After starting the server, open:

- `http://localhost:8000`

## Features

- Rate intelligence
  - Pull latest competitor rates (or mock data if scraping is not implemented)
  - Cross-competitor price matrix (canonical model -> competitor cheapest price)
  - Price history (trend charts)
  - Price deltas (latest scrape date vs previous scrape date)
  - Seasonal sweep (12-month price bands)
  - Car catalog + competitor model mapping management
  - Manual scrape trigger via API

- SEO rank tracking (optional SerpAPI integration)
  - Track keyword rankings for `bluecarrental.is`
  - Keyword CRUD (add/remove up to a limit)
  - Ranking history (trend charts)
  - Manual live rank check (requires `SERPAPI_KEY`)
  - Scheduler jobs for periodic scrape and SEO checks
  - Mock ranking fallback when `SERPAPI_KEY` is not configured

## Quickstart (local)

1. Install dependencies

```bash
python -m pip install -r requirements.txt
```

2. Configure environment variables

Copy the example env:

```bash
cp .env.example .env
```

Optional:
- Set `SERPAPI_KEY` for live SEO checks.

3. Start the server

```bash
python main.py
```

By default it binds to:
- `http://localhost:8000`

## Run options

The server reads:
- `APP_HOST` (default: `0.0.0.0`)
- `APP_PORT` (default: `8000`)
- `DEBUG` (default: `true`) – enables `uvicorn` reload in dev mode

## API Reference

### Health / scheduler

- `GET /api/health`
  - Returns `{ "status": "ok", "app": "Blue Rental Intelligence" }`

- `GET /api/scheduler/status`
  - Returns scheduler state, last scrape time, and next run time.

- `POST /api/scheduler/reconfigure?schedule=daily|hourly|weekly`
  - Updates the APScheduler cron schedule without restarting the app.

### Rate Intelligence (`/api/rates`)

- `GET /api/rates`
  - Query params (all optional):
    - `location`: pickup location filter
    - `pickup_date`: `YYYY-MM-DD`
    - `return_date`: `YYYY-MM-DD`
    - `car_category`: `Economy|Compact|SUV|4x4|Minivan`
  - Response:
    - `{ "rates": [...], "source": "database" | "mock" }`

- `POST /api/rates/scrape`
  - Optional JSON/query params: `location`, `pickup_date`, `return_date`
  - Triggers live scrapes (currently scrapers fall back to mock data unless live scraping is implemented).

- `GET /api/rates/deltas`
  - Query params:
    - `location` (optional)
    - `category` (optional)
  - Response:
    - `{ "deltas": {...}, "available": boolean }`

- `GET /api/rates/history`
  - Query params:
    - `location` (optional)
    - `car_category` (optional)
    - `competitor` (optional)
    - `days` (default: `30`, range enforced in API)

- `GET /api/rates/history/models`
  - Query params:
    - `location` (optional)
    - `competitor` (optional)
    - `days` (default: `30`)
  - Used by the “price history by model” view.

- `GET /api/rates/matrix`
  - Query params:
    - `location` (optional)
    - `pickup_date` (optional)
    - `return_date` (optional)
    - `category` (optional)

- `GET /api/rates/seasonal`
  - Query params:
    - `category` (optional)
    - `location` (optional)
  - Sweeps the next 12 months (mid-month 7-night stay) and returns per-day pricing bands.
  - Response includes:
    - `months`: per-month competitor × category pricing
    - `season_summary`: avg per-day per competitor per season (Low/Shoulder/High/Peak)
    - `category_season_summary`: avg per-day per car category per season (all competitors combined)
    - `season_months`, `source`, `rental_days`

- Car catalog
  - `GET /api/rates/car-catalog`
    - `{ "catalog": [...] }`
  - Car mappings (competitor model name -> canonical model)
    - `GET /api/rates/car-mappings`
    - `POST /api/rates/car-mappings` with body:
      - `{ "competitor": "...", "competitor_model": "...", "canonical_name": "..." }`
    - `DELETE /api/rates/car-mappings/{mapping_id}`

### SEO Rank Tracking (`/api/seo`)

- `GET /api/seo/rankings`
  - Query params:
    - `keyword` (optional)
    - `location` (optional)
  - Response:
    - `{ "rankings": [...], "has_api_key": boolean, "source": "database" | "mock" }`

- `POST /api/seo/check`
  - Query params:
    - `location` (optional)
  - Requires `SERPAPI_KEY` to be configured; otherwise returns `400`.

- `GET /api/seo/history`
  - Query params:
    - `keyword` (optional)
    - `location` (optional)
    - `days` (default: `30`)

- Keyword management
  - `GET /api/seo/keywords`
  - `POST /api/seo/keywords` with query/body param `keyword`
  - `DELETE /api/seo/keywords/{keyword}`

### Settings (`/api/settings`)

- `GET /api/settings`
- `POST /api/settings` with body:
  - `serpapi_key` (optional)
  - `scrape_schedule` (optional, one of `hourly|daily|weekly`)
  - `locations` (optional list of `{ "name": "...", "address": "..." }`)

## Scrapers

Scrapers live in `scrapers/`.

All competitor scrapers inherit from `BaseScraper` (`scrapers/base.py`):
- They define a `competitor_name`
- They define a `FLEET` mapping by car category
- They implement `scrape_rates(...)` to attempt live scraping

### Mock fallback (current state)

In the current code, each scraper’s `scrape_rates()` raises `NotImplementedError`, and the framework automatically falls back to deterministic mock pricing from each scraper’s `FLEET`.

This means:
- The dashboard is immediately testable end-to-end.
- Live competitor scraping is intentionally left as a TODO.

### Implementing live scraping

To add/enable live scraping for a competitor:
1. Open that scraper file in `scrapers/` (example: `scrapers/gocarrental.py`)
2. Replace `raise NotImplementedError(...)` with real `scrape_rates()` logic
3. Return a list of dicts matching the database schema keys used by the app:
   - `competitor`, `location`, `pickup_date`, `return_date`
   - `car_category`, `car_model`, `canonical_name`
   - `price_isk`, `currency`, `scraped_at`

See `BaseScraper.get_mock_rates()` for the exact shape.

## Database

The app uses SQLite via `aiosqlite` and initializes schema on startup (`database.py`).

Local DB file:
- `blue_rental.db`

Tables:
- `rates`
- `rankings`
- `car_catalog`
- `car_mappings`
- `config`

## Best Practices / Repo Hygiene

- Secrets and local DB files are excluded via `.gitignore`
- Use `.env.example` as the template for environment setup

## License

Add your chosen license here (e.g., MIT). If you tell me which license you prefer, I can add it.

