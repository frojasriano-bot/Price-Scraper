# Scrapers

All competitor scrapers are located in `scrapers/`.

## Base class

Scrapers inherit from `BaseScraper` in `scrapers/base.py`.

Key concepts:
- `competitor_name`: label used in the database and returned by the API
- `FLEET`: per-category list of car models and `price_range` (used for mock fallback)
- `scrape_rates()`: implements live scraping; on exception the caller falls back to mock rates
- `get_mock_rates()`: deterministic mock pricing derived from `FLEET`, seasonal multipliers, and a competitor "personality"

## Live scrapers

All 7 scrapers are live:

| Scraper | Method | Notes |
|---------|--------|-------|
| `blue_rental.py` | Caren API | bluecarrental.is |
| `gocarrental.py` | GoRentals JSON API + Sanity CMS | Car names resolved via CMS |
| `lavacarrental.py` | Caren API | KEF only |
| `hertz_is.py` | WordPress nonce → ajax + HTML | KEF + Reykjavik |
| `lotus.py` | Caren API | KEF only |
| `avis_is.py` | HTML form | KEF + Reykjavik |
| `holdur.py` | HTML form (3 POST requests) | Server-side deduplication strips duplicate results |

If a live scrape fails (network error, selector change, timeout), the base class falls back to `get_mock_rates()` so the dashboard always has data.

## Adding a new competitor scraper

1. Create a new file in `scrapers/` (e.g. `mycompetitor.py`)
2. Implement a class inheriting from `BaseScraper`:

```python
class MyCompetitor(BaseScraper):
    competitor_name = "My Competitor"

    async def scrape_rates(self, location, pickup_date, return_date) -> list[dict]:
        # fetch and parse ...
        return [...]
```

3. Add it to `scrapers/__init__.py` — import the class and add it to `ALL_SCRAPERS`

4. Return a list of dicts matching the `rates` table schema:
   - `competitor` — must match `competitor_name`
   - `location` — `"Keflavik Airport"` or `"Reykjavik"`
   - `pickup_date`, `return_date` — `YYYY-MM-DD`
   - `car_category` — `Economy | Compact | SUV | 4x4 | Minivan`
   - `car_model` — raw model name from the source
   - `canonical_name` — normalised via `canonicalize()` from `canonical.py`
   - `price_isk` — integer
   - `currency` — `"ISK"`
   - `scraped_at` — ISO datetime string

If your scrape fails at any point, raise an exception and the system will fall back to `get_mock_rates()`.

## Mapping competitor models to canonical models

Some competitors label car models differently. The dashboard uses canonical names to group rates across competitors. These mappings are stored in the `car_mappings` table and edited via Settings → Car Model Mappings or the API:

- `GET /api/rates/car-mappings`
- `POST /api/rates/car-mappings`
- `DELETE /api/rates/car-mappings/{mapping_id}`

In your scraper, pass `canonical_name` through `canonicalize()` from `canonical.py` — it handles suffix stripping, spelling variants, and older-model tagging automatically.
