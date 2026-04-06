# Blue Rental Intelligence

Competitor pricing intelligence + insurance comparison + local SEO rank tracking for **Blue Car Rental Iceland**.

A FastAPI backend serving a single-page dashboard from `static/` with a JSON API under `/api/*`. Uses SQLite for storage and APScheduler for automated scraping.

---

## Dashboard Tabs

| Tab | Description |
|-----|-------------|
| **Rate Intelligence** | Latest competitor rates, sortable table, cross-competitor matrix, price history charts, seasonal analysis |
| **Insurance Comparison** | Full coverage matrix, per-company package breakdowns, deductible comparison across all 7 competitors |
| **SEO Rank Tracker** | Keyword ranking history for bluecarrental.is via SerpAPI |
| **Settings** | Scraper status, schedule config, SerpAPI key, location management, car model mappings, Slack alerts |

---

## Quickstart

### 1. Install dependencies

```bash
python -m pip install -r requirements.txt
```

### 2. Configure environment (optional)

```bash
cp .env.example .env
```

Set `SERPAPI_KEY` to enable live SEO rank checks. All other features work without any API keys.

### 3. Start the server

```bash
uvicorn main:app --reload
```

Or:

```bash
python main.py
```

Open **http://localhost:8000**

### Environment variables

| Variable | Default | Description |
|----------|---------|-------------|
| `APP_HOST` | `0.0.0.0` | Bind address |
| `APP_PORT` | `8000` | Port |
| `DEBUG` | `true` | Enables uvicorn `--reload` |
| `SERPAPI_KEY` | — | Required for live SEO rank checks |

---

## Architecture

```
main.py                  FastAPI app, APScheduler, lifespan setup
canonical.py             Car name normalisation (canonicalize() function)
database.py              SQLite schema, CAR_CATALOG, all DB helpers

routes/
  rates.py               /api/rates/* — scraper trigger, history, matrix, seasonal
  insurance.py           /api/insurance  — static insurance comparison data
  seo.py                 /api/seo/*  — rankings, keyword management
  settings.py            /api/settings — config, locations, scraper status
  alerts.py              /api/alerts/* — Slack webhook config & test

scrapers/
  base.py                BaseScraper abstract class + mock data fallback
  blue_rental.py         ✅ Live — Caren API (bluecarrental.is)
  holdur.py              ✅ Live — HTML scraper (holdur.is)
  lotus.py               ✅ Live — Caren API (lotuscarrental.is)
  avis_is.py             🔶 Mock data only
  gocarrental.py         🔶 Mock data only
  hertz_is.py            🔶 Mock data only
  lavacarrental.py       🔶 Mock data only

static/
  index.html             Single-page dashboard shell
  app.js                 All frontend logic (Chart.js, tabs, dark mode)
  style.css              Styles + dark mode CSS vars
```

---

## Scrapers

All scrapers inherit from `BaseScraper` (`scrapers/base.py`) and implement `scrape_rates(pickup_date, return_date, location)`. On failure, or when not yet implemented, the base class falls back to deterministic mock pricing from each scraper's `FLEET` definition.

### Live scrapers

**Blue Car Rental** and **Lotus Car Rental** both use the [Caren](https://www.caren.is) booking API:

```
POST /_carenapix/class/
Params: dateFrom, dateTo (YYYY-MM-DD HH:MM format)
```

**Holdur** is scraped via HTTP POST to their booking form and BeautifulSoup HTML parsing.

### Supported locations

| Location | Blue | Holdur | Lotus | Mock competitors |
|----------|------|--------|-------|-----------------|
| Keflavik Airport | ✅ | ✅ | ✅ | ✅ |
| Reykjavik | ✅ | ✅ | ✅ | ✅ |
| Akureyri | — | ✅ | ✅ | ✅ |
| Egilsstaðir | — | ✅ | ✅ | ✅ |

Blue Car Rental returns an empty list for Akureyri and Egilsstaðir (no branches there).

### Adding a live scraper

1. Open the scraper file (e.g. `scrapers/gocarrental.py`)
2. Implement `scrape_rates(self, pickup_date, return_date, location)` — replace `raise NotImplementedError`
3. Return a list of dicts with these keys:

```python
{
    "competitor":     str,   # e.g. "Go Car Rental"
    "location":       str,   # e.g. "Keflavik Airport"
    "pickup_date":    str,   # YYYY-MM-DD
    "return_date":    str,   # YYYY-MM-DD
    "car_category":   str,   # Economy | Compact | SUV | 4x4 | Minivan
    "car_model":      str,   # raw model name from source
    "canonical_name": str,   # normalised via canonicalize() from canonical.py
    "price_isk":      int,
    "currency":       str,   # "ISK"
    "scraped_at":     str,   # ISO datetime
}
```

### Car name normalisation

`canonical.py` exposes a `canonicalize(name)` function that maps variant spellings to a standard canonical name used across all scrapers and the database (e.g. `"Toyota Landcruiser 150"` → `"Toyota Land Cruiser 150"`). Add new entries to the `_EXACT` dict in that file.

`insert_rates()` in `database.py` applies `canonicalize()` automatically on every insert.

---

## Database

SQLite via `aiosqlite`. Schema is initialised automatically on startup by `init_db()` in `database.py`. Local file: `blue_rental.db`

| Table | Purpose |
|-------|---------|
| `rates` | Scraped rental rates — one row per competitor/location/model/scrape |
| `car_catalog` | Master list of canonical car names and categories |
| `car_mappings` | Competitor model name → canonical name mapping (editable via UI) |
| `rankings` | SEO keyword rankings (from SerpAPI) |
| `config` | Key-value store: SerpAPI key, schedule, webhook URL, locations, etc. |
| `seasonal_cache` | 6-hour cached seasonal analysis results |

`rates` table columns: `competitor`, `location`, `pickup_date`, `return_date`, `car_category`, `car_model`, `canonical_name`, `price_isk`, `currency`, `scraped_at`

---

## Scheduler

APScheduler (`AsyncIOScheduler`) runs three jobs:

| Job | Default schedule | Description |
|-----|-----------------|-------------|
| `scrape_rates` | Daily 07:00 | Scrapes all competitors and inserts to DB |
| `seo_check` | Daily 07:30 | Checks keyword rankings via SerpAPI |
| `alert_check` | Daily 07:45 | Fires Slack alerts if competitors undercut Blue's rates |

Schedule can be changed to `hourly` or `weekly` via Settings → Auto-scrape schedule, or via:

```
POST /api/scheduler/reconfigure?schedule=weekly
```

---

## Insurance Comparison

The Insurance tab (`GET /api/insurance`) contains static, researched data for all 7 competitors — no scraping, no DB required. Data lives in `routes/insurance.py`.

**Covered protection types:** TPL, CDW, SCDW, TP, GP (Gravel/Glass), SAAP (Sand & Ash), TIP (Tire & Wheel), PAI, Roadside Assistance, F-Road Protection, River Crossing, Zero Excess

**Per-company data includes:**
- Which protections are included in the base rental (with deductible amounts)
- All available packages/tiers with daily price and deductible summary
- Individual product pricing where applicable (Hertz uses an unbundled model)

**Key findings surfaced in the UI:**
- **Lava Car Rental** has the most comprehensive base bundle (7 protections included by default)
- **Hertz Iceland** is the only company where CDW is **not** included in the base price
- **Lotus Car Rental** is the only company offering river crossing protection (Platinum, 4x4 only)
- **Go Car Rental** uniquely prices all insurance in EUR rather than ISK

Data sourced April 2025 from publicly available company websites. To update, edit the `INSURANCE_DATA` dict in `routes/insurance.py`.

---

## API Reference

### Health & Scheduler

```
GET  /api/health
GET  /api/scheduler/status
POST /api/scheduler/reconfigure?schedule=daily|hourly|weekly
```

### Rate Intelligence

```
GET  /api/rates
     ?location=  &pickup_date=  &return_date=  &car_category=

POST /api/rates/scrape
     ?location=  &pickup_date=  &return_date=

GET  /api/rates/deltas
     ?location=  &category=

GET  /api/rates/history
     ?location=  &car_category=  &competitor=  &days=30

GET  /api/rates/history/models
     ?location=  &competitor=  &days=30

GET  /api/rates/history/coverage
     ?location=  &days=30

GET  /api/rates/matrix
     ?location=  &pickup_date=  &return_date=  &category=

GET  /api/rates/seasonal                 (cached 6h)
     ?category=  &location=

GET  /api/rates/scraper-status
GET  /api/rates/car-catalog
GET  /api/rates/car-mappings
POST /api/rates/car-mappings
DELETE /api/rates/car-mappings/{id}
```

### Insurance

```
GET  /api/insurance
```

### SEO Rank Tracking

```
GET  /api/seo/rankings
     ?keyword=  &location=

POST /api/seo/check                      Requires SERPAPI_KEY
     ?location=

GET  /api/seo/history
     ?keyword=  &location=  &days=30

GET    /api/seo/keywords
POST   /api/seo/keywords?keyword=
DELETE /api/seo/keywords/{keyword}
```

### Settings & Alerts

```
GET  /api/settings
POST /api/settings                       serpapi_key, schedule, locations

POST /api/alerts/test-webhook
POST /api/alerts/check
```

---

## Brand Colours

Used in charts and the insurance comparison UI:

| Competitor | Colour |
|-----------|--------|
| Blue Car Rental | `#2563eb` |
| Holdur | `#22c55e` |
| Lotus Car Rental | `#881337` |
| Avis Iceland | `#ef4444` |
| Go Car Rental | `#f97316` |
| Hertz Iceland | `#eab308` |
| Lava Car Rental | `#a855f7` |

---

## Dark Mode

Toggle via the moon/sun icon in the top bar. Preference is persisted to `localStorage`. Implemented via `body.dark-mode` class + CSS custom property overrides in `style.css`.

> **Note:** Do not override the `--white` CSS variable in dark mode overrides — the sidebar uses it for text colour and is intentionally always dark regardless of theme.

---

## Repo Hygiene

- `blue_rental.db` and `.env` are excluded via `.gitignore`
- Copy `.env.example` to `.env` for local setup
- Secrets (SerpAPI key, Slack webhook URL) are stored in the `config` DB table at runtime, not in env files
