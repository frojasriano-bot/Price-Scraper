# API Documentation

Base URL (when running locally): `http://localhost:8000`

## Health

- `GET /api/health`
  - Response: `{ "status": "ok", "app": "Blue Rental Intelligence" }`

## Scheduler

- `GET /api/scheduler/status`
  - Response fields:
    - `is_running`: boolean
    - `schedule`: `hourly | daily | weekly`
    - `last_scrape_at`: ISO timestamp (or null)
    - `next_run`: ISO timestamp (or null)

- `POST /api/scheduler/reconfigure?schedule=daily|hourly|weekly`
  - Response: `{ "message": "Scheduler reconfigured to: <schedule>" }`

## Rate Intelligence (`/api/rates`)

- `GET /api/rates`
  - Optional query params:
    - `location` (pickup location filter)
    - `pickup_date` (`YYYY-MM-DD`)
    - `return_date` (`YYYY-MM-DD`)
    - `car_category` (`Economy|Compact|SUV|4x4|Minivan`)
  - Response:
    - `{ "rates": [...], "source": "database" | "mock" }`

- `POST /api/rates/scrape`
  - Optional query params:
    - `location`, `pickup_date`, `return_date`
  - Response:
    - `scraped`, `competitors`, `errors`, `message`

- `GET /api/rates/deltas`
  - Optional query params:
    - `location`, `category`
  - Response:
    - `{ "deltas": {...}, "available": boolean }`

- `GET /api/rates/price-changes`
  - Per-competitor price delta between the two most recent scrape dates (keyed by `competitor::location::model`)
  - Optional query params:
    - `location`, `category`
  - Response:
    - `{ "changes": { "<key>": { "prev": n, "curr": n, "delta": n } } }`

- `GET /api/rates/scrape-log`
  - History of every scrape run (manual, scheduled, seasonal, horizon)
  - Optional query params:
    - `limit` (default 20)
  - Response:
    - `{ "log": [ { "triggered_at", "trigger", "location", "rates_scraped", "competitors_hit", "duration_seconds", "error_count" } ] }`

- `GET /api/rates/history`
  - Optional query params:
    - `location`, `car_category`, `competitor`, `days` (1..365)
  - Response:
    - `{ "history": [...], "source": "database" | "mock" }`

- `GET /api/rates/history/models`
  - Optional query params:
    - `location`, `competitor`, `days`
  - Response:
    - `{ "data": { "<category>": { "<model>": [ ... ] } }, "source": "database" | "mock" }`

- `GET /api/rates/history/coverage`
  - Which competitors have data per day over the lookback window
  - Optional query params:
    - `location`, `days`
  - Response:
    - `{ "coverage": { "<date>": ["<competitor>", ...] } }`

- `GET /api/rates/matrix`
  - Optional query params:
    - `location`, `pickup_date`, `return_date`, `category`
  - Response:
    - `{ "cars": [...], "competitors": [...], "source": "database" | "mock" }`

- `GET /api/rates/seasonal`
  - Optional query params:
    - `category`, `location`
  - Response:
    ```json
    {
      "months": [
        {
          "month": "2026-04",
          "month_label": "Apr 2026",
          "season": "shoulder",
          "season_label": "Shoulder",
          "competitors": { "<competitor>": { "<category>": <avg_per_day_isk> } },
          "comp_overall": { "<competitor>": <avg_per_day_isk> },
          "market_avg": { "<category>": <avg_per_day_isk> }
        }
      ],
      "season_summary": {
        "low|shoulder|high|peak": { "<competitor>": <avg_per_day_isk> }
      },
      "category_season_summary": {
        "low|shoulder|high|peak": { "<category>": <avg_per_day_isk> }
      },
      "season_months": { "low": ["Nov 2026", ...] },
      "source": "live|mock",
      "rental_days": 7
    }
    ```
  - `season_summary` — average per-day ISK per competitor across all months in each season band
  - `category_season_summary` — average per-day ISK per car category (Economy/Compact/SUV/4x4/Minivan) across all competitors and months in each season band; powers the **Season Price Summary by Category** dashboard table

- `POST /api/rates/scrape-seasonal`
  - Re-scrapes all 12 anchor months and persists results
  - Optional query params: `location`

- `GET /api/rates/seasonal/history`
  - Time series showing how prices for one anchor month have evolved across successive scrapes
  - Required query params: `pickup_date` (`YYYY-MM-15`)
  - Optional query params: `category`, `location`
  - Response: `{ "history": [ { "scraped_at", "competitor", "per_day" } ] }`

- `GET /api/rates/horizon`
  - Next N weeks of per-day pricing per competitor (real scraped data only)
  - Optional query params: `location`, `category`, `weeks` (default 26, min 4, max 52)
  - Response: `{ "weeks": [ { "pickup_date", "competitors": { "<name>": <per_day_isk> } } ] }`

- `POST /api/rates/scrape-horizon`
  - Scrapes all 7 competitors × N weekly windows and persists results
  - Optional query params: `location`, `weeks` (default 26, min 4, max 52)

- `GET /api/rates/model-horizon`
  - All future scraped per-day prices for one specific canonical model, grouped by competitor
  - Required query params: `model` (canonical name, URL-encoded)
  - Optional query params: `location`
  - Response: `{ "<competitor>": [ { "pickup_date", "per_day", "car_model" } ] }`

- `GET /api/rates/scraper-status`
  - Live and mock status for each configured scraper
  - Response: `{ "scrapers": [ { "name", "status", "last_scraped_at", "rates_count" } ] }`

### Car catalog & mappings

- `GET /api/rates/car-catalog`
  - Response: `{ "catalog": [...] }`

- `GET /api/rates/car-mappings`
  - Response: `{ "mappings": [...] }`

- `POST /api/rates/car-mappings`
  - Body:
    - `competitor` (string)
    - `competitor_model` (string)
    - `canonical_name` (string)
  - Response: `{ "message": "Mapping saved." }`

- `DELETE /api/rates/car-mappings/{mapping_id}`
  - Response: `{ "message": "Mapping deleted." }`

## SEO Rank Tracking (`/api/seo`)

- `GET /api/seo/rankings`
  - Optional query params:
    - `keyword`, `location`
  - Response:
    - `{ "rankings": [...], "has_api_key": boolean, "source": "database" | "mock" }`

- `POST /api/seo/check`
  - Optional query params:
    - `location`
  - Requires: `SERPAPI_KEY` (configured via `SERPAPI_KEY` env var or DB setting)
  - Response:
    - `{ "checked": n, "keywords": [...], "errors": [...], "message": "..." }`

- `GET /api/seo/history`
  - Optional query params:
    - `keyword`, `location`, `days` (1..365)
  - Response:
    - `{ "history": [...], "source": "database" | "mock" }`

### Keyword management

- `GET /api/seo/keywords`
  - Response: `{ "keywords": [...] }`

- `POST /api/seo/keywords?keyword=<...>`
  - Response: `{ "keywords": [...], "message": "Added: <kw>" }`

- `DELETE /api/seo/keywords/{keyword}`
  - Response: `{ "keywords": [...], "message": "Removed: <kw>" }`

## Settings (`/api/settings`)

- `GET /api/settings`
  - Response includes:
    - `serpapi_key`: stored value (masked in UI by `serpapi_key_set`)
    - `scrape_schedule`
    - `locations`: array of `{name, address}`

- `POST /api/settings`
  - Body fields (all optional):
    - `serpapi_key`
    - `scrape_schedule` (`hourly|daily|weekly`)
    - `locations`: list of `{name, address}`

- `GET /api/settings/category-audit`
  - Per-model category status: mapped, unmapped, or conflict (DB category ≠ canonical)
  - Response: `{ "models": [ { "canonical_name", "db_category", "canonical_category", "status" } ], "summary": { "total", "mapped", "unmapped", "conflicts" } }`

## Insurance (`/api/insurance`)

- `GET /api/insurance`
  - Full insurance data including coverage matrix, company cards, deductibles, and category pricing with any DB overrides applied
  - Response: `{ "companies": [...], "category_pricing": { "<company>": { "<category>": { "price_isk", "note" } } } }`

- `GET /api/insurance/category-pricing`
  - Base category pricing without DB overrides applied

- `POST /api/insurance/prices`
  - Save a price override for one company + category cell
  - Body: `{ "company": str, "category": str, "price_isk": int, "note": str }`
  - Response: `{ "company", "category", "price_isk", "price_note", "updated_at" }`

- `GET /api/insurance/review-log`
  - Timestamped history of manual insurance review events
  - Response: `{ "log": [ { "reviewed_at", "reviewed_by" } ] }`

- `POST /api/insurance/mark-reviewed`
  - Records a manual review event in the audit log

## Alerts (`/api/alerts`)

- `POST /api/alerts/test-webhook`
  - Sends a test message to the configured Slack webhook URL

- `POST /api/alerts/check`
  - Runs the price alert check immediately and fires Slack alerts if any competitor undercuts Blue Car Rental

