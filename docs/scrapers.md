# Scrapers

All competitor scrapers are located in `scrapers/`.

## Base class

Scrapers inherit from `BaseScraper` in `scrapers/base.py`.

Key concepts:
- `competitor_name`: label used in the database and returned by the API
- `FLEET`: per-category list of car models and `price_range`
- `scrape_rates()`: implement live scraping; on failure, callers fall back to mock rates
- `get_mock_rates()`: deterministic mock pricing derived from `FLEET`, seasonal multipliers, and a competitor “personality”

### Current state (mock fallback)

In the current codebase, each scraper’s `scrape_rates()` raises `NotImplementedError`, which triggers mock fallback.

That’s intentional for end-to-end dashboard testing without fragile scraping selectors.

## Adding live scraping

1. Pick the scraper file for your competitor:
   - `scrapers/blue_rental.py`
   - `scrapers/gocarrental.py`
   - `scrapers/lavacarrental.py`
   - `scrapers/hertz_is.py`
   - `scrapers/lotus.py`
   - `scrapers/avis_is.py`
   - `scrapers/holdur.py`

2. Implement `async def scrape_rates(self, location, pickup_date, return_date) -> list[dict]`

3. Return a list of dicts with the database schema fields the app expects:
   - `competitor`
   - `location`
   - `pickup_date`, `return_date`
   - `car_category`
   - `car_model`
   - `canonical_name` (recommended for consistent model grouping)
   - `price_isk`
   - `currency` (usually `ISK`)
   - `scraped_at` (ISO timestamp)

If your scrape fails at any point, raise an exception and the system will fall back to `get_mock_rates()`.

## Mapping competitor models to canonical models

Some competitors label car models differently.

The dashboard uses “canonical names” to group rates across competitors.

Mappings are stored in the `car_mappings` table and edited via:
- `GET /api/rates/car-mappings`
- `POST /api/rates/car-mappings`
- `DELETE /api/rates/car-mappings/{mapping_id}`

In your scraper, set:
- `car_model`: the competitor’s label
- `canonical_name`: the canonical model your label should map to

If you can’t map at scrape time, you can still add/edit mappings in the dashboard.

