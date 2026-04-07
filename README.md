# Blue Rental Intelligence

Competitor pricing intelligence + insurance comparison + local SEO rank tracking for **Blue Car Rental Iceland**.

FastAPI backend · SQLite · APScheduler · Vanilla JS SPA · Chart.js

---

## Dashboard Tabs

| Tab | Description |
|-----|-------------|
| **Rate Intelligence** | Executive summary banner, live competitor rates, sortable table with per-competitor price-change arrows, bar chart, cross-competitor matrix, price history charts, seasonal analysis with price-evolution history mode, CSV export |
| **Insurance Comparison** | Coverage matrix, per-category zero-excess pricing (editable), company package cards, deductible comparison, Trigger Research + Mark Reviewed workflow with audit log |
| **SEO Rank Tracker** | Keyword ranking history with previous rank + change via SerpAPI; 10 Iceland-specific keywords pre-seeded |
| **Settings** | Scraper status, schedule config, SerpAPI key, location management, car model mappings, Slack alerts, scrape history log |

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
python main.py
# or
uvicorn main:app --reload
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
  rates.py               /api/rates/* — scraper trigger, history, matrix, seasonal,
                         per-competitor price-changes, scrape log
  insurance.py           /api/insurance — comparison data, category pricing (with DB
                         overrides), mark-reviewed workflow, review log
  seo.py                 /api/seo/* — rankings, keyword management
  settings.py            /api/settings — config, locations, scraper status
  alerts.py              /api/alerts/* — Slack webhook config & test

scrapers/
  base.py                BaseScraper abstract class + mock data fallback
  blue_rental.py         ✅ Live — Caren API (bluecarrental.is)
  holdur.py              ✅ Live — HTML scraper (holdur.is)
  lotus.py               ✅ Live — Caren API (lotuscarrental.is)
  avis_is.py             ✅ Live — HTML scraper (avis.is)
  gocarrental.py         ✅ Live — GoRentals JSON API + Sanity CMS
  hertz_is.py            ✅ Live — WordPress/CarCloud ajax + HTML (hertz.is)
  lavacarrental.py       ✅ Live — Caren API (lavacarrental.is)

static/
  index.html             Single-page dashboard shell
  app.js                 All frontend logic (Chart.js, tabs, dark mode)
  style.css              Styles + dark mode CSS vars
```

---

## Scrapers

All scrapers inherit from `BaseScraper` and implement `scrape_rates(pickup_date, return_date, location)`. On failure the base class falls back to deterministic mock pricing from each scraper's `FLEET` definition.

### Supported locations

Keflavik Airport and Reykjavik only — the two locations Blue Car Rental operates from.

| Competitor | KEF Airport | Reykjavik | Notes |
|------------|------------|-----------|-------|
| Blue Car Rental | ✅ | ✅ | Caren API |
| Holdur | ✅ | ✅ | HTML form (3 category POST requests, server-side deduplication) |
| Avis Iceland | ✅ | ✅ | HTML form |
| Go Car Rental | ✅ | ✅ | GoRentals JSON API + Sanity CMS for car names |
| Hertz Iceland | ✅ | ✅ | WordPress nonce → ajax + HTML |
| Lava Car Rental | ✅ | — | Caren API (KEF only) |
| Lotus Car Rental | ✅ | — | Caren API (KEF only) |

### Known scraper behaviours

- **Hertz**: Displays a single "from" floor price for multiple Economy models (website design, not a scraper bug)
- **Holdur**: Server ignores `vehicleCategoryId` filter and returns all cars for every POST — duplicates stripped client-side
- **Go Car Rental**: Dacia Jogger appears twice (5-seat Compact + 7-seat Minivan) — two distinct class IDs in their CMS, both legitimate
- **Lava Car Rental**: "4x4 Cars" group contains mixed SUVs and true 4x4s — classified as SUV with keyword promotion for vehicles like Land Rover Defender, Land Cruiser, Sorento

### Adding a live scraper

1. Open the scraper file and implement `scrape_rates(self, pickup_date, return_date, location)`
2. Return a list of dicts:

```python
{
    "competitor":     str,   # e.g. "Go Car Rental"
    "location":       str,   # "Keflavik Airport" | "Reykjavik"
    "pickup_date":    str,   # YYYY-MM-DD
    "return_date":    str,   # YYYY-MM-DD
    "car_category":   str,   # Economy | Compact | SUV | 4x4 | Minivan
    "car_model":      str,   # raw model name from source
    "canonical_name": str,   # normalised via canonicalize()
    "price_isk":      int,
    "currency":       str,   # "ISK"
    "scraped_at":     str,   # ISO datetime
}
```

### Car name normalisation

`canonical.py` exposes `canonicalize(name)` which strips transmission/fuel suffixes (automatic, manual, petrol, diesel, hybrid, electric, awd, 4wd) and maps variant spellings to standard names via an `_EXACT` dict. Apostrophes are normalised so e.g. `"Kia Cee'd"` matches `"Kia Ceed"`.

```
"Toyota Landcruiser 150"            → "Toyota Land Cruiser 150"
"VW Transporter 4WD"                → "VW Transporter"
"Volkswagen Caravelle"              → "VW Caravelle"
"Kia Ceed Sportswagon"              → "Kia Ceed Wagon"
"Toyota Land Cruiser 4x4 35\" ..."  → "Toyota Land Cruiser 150"
"Dacia Duster Used Model"           → "Dacia Duster"
```

---

## Database

SQLite via `aiosqlite`. Schema initialised automatically on startup by `init_db()`. Local file: `blue_rental.db`

| Table | Purpose |
|-------|---------|
| `rates` | Scraped rental rates — one row per competitor/location/model/scrape. Accumulates over time; no overwrites. |
| `car_catalog` | Master list of canonical car names and categories |
| `car_mappings` | Competitor model name → canonical name (editable via Settings) |
| `rankings` | SEO keyword rankings from SerpAPI |
| `config` | Key-value store: SerpAPI key, schedule, webhook URL, locations, SEO keywords |
| `seasonal_cache` | 30-minute response cache for the seasonal analysis endpoint |
| `scrape_log` | History of every manual, scheduled, and seasonal scrape run (rates, duration, errors) |
| `insurance_reviews` | Timestamped log of manual insurance data verifications |
| `insurance_price_overrides` | Per-company/category zero-excess price overrides (editable via Insurance tab) |

---

## Rate Intelligence

### Executive Summary Banner

Shown at the top of the Rates tab on every load:
- **Blue vs Market** — Blue's avg price vs competitor avg (green = cheaper, red = more expensive)
- **Market Low** — cheapest single rate in the current view
- **Undercutting Blue** — number of competitors with any model cheaper than Blue's equivalent
- **Price Moves** — count of models whose price has gone ↑ or ↓ since the previous scrape

### Price Change Arrows

The Δ column in the list view shows **per-competitor** price movement (not market average). `GET /api/rates/price-changes` compares each competitor's own avg price per model between the two most recent scrape dates.

### Date Picker → Auto Scrape

Changing the pickup or return date triggers a live scrape after an 800 ms debounce, so the table always reflects actual live pricing for the selected window.

### CSV Export

Export the full rates table as CSV from the list view header button. Includes per-day pricing calculated from the rental window.

### Scrape History Log

Settings → Scrape History shows every run: timestamp, trigger (manual / scheduled / seasonal), location, rates scraped, competitors hit, duration, and error count.

---

## Seasonal Analysis

The seasonal view plots per-day pricing across the next 12 months, with one data point per competitor per month (pickup on the 15th, 7-night stay).

### Data architecture

The seasonal endpoint is **DB-first** — it reads from the `rates` table first and only live-scrapes months that have no stored anchor data:

1. For each of the 12 anchor months, query `rates WHERE pickup_date = 'YYYY-MM-15'`
2. If stored data exists → use it (fast, instant load)
3. If no stored data → live-scrape that month and persist the result for future requests
4. Response is cached for 30 minutes to avoid re-aggregating on every browser refresh

This means the seasonal chart load is instant once data is stored, and the weekly cron keeps it current without any on-demand scraping overhead.

### Scraping anchor dates

The **Scrape All** button (or `POST /api/rates/scrape-seasonal`) re-scrapes all 12 anchor months and stores fresh data. The weekly Monday cron does the same automatically.

### Price evolution / History mode

The **History** toggle switches the chart to show how prices for a selected future month have changed across successive weekly scrapes:

- X-axis: scrape dates (e.g. "7 Apr", "14 Apr", "21 Apr"...)
- Y-axis: per-day ISK
- One line per competitor

This reveals whether competitors are raising or lowering prices as a future season approaches — the most actionable competitive intelligence the tool provides.

### Mock data vs live data

`SEASON_MULTIPLIERS` in `base.py` (Jan: 0.82× → Jul: 1.92×) are **only** used by the `get_mock_rates()` fallback when a live scrape fails entirely. They are never applied to real prices returned by competitor websites.

---

## Scheduler

APScheduler (`AsyncIOScheduler`) runs four jobs:

| Job | Schedule | Description |
|-----|----------|-------------|
| `scrape_rates` | Daily 07:00 (configurable) | Scrapes all competitors for today+7 → today+10 |
| `seo_check` | Daily 07:30 (configurable) | Checks stored keywords via SerpAPI |
| `alert_check` | Daily 07:45 (configurable) | Fires Slack alerts if competitors undercut Blue |
| `scrape_seasonal` | **Every Monday 08:00** | Re-scrapes all 12 anchor months; always weekly |

The daily/hourly/weekly setting (configurable via Settings) applies to `scrape_rates`, `seo_check`, and `alert_check`. The seasonal scrape always runs weekly regardless.

Change the main schedule via Settings or:

```
POST /api/scheduler/reconfigure?schedule=weekly
```

---

## Insurance Comparison

### Views

| View | Description |
|------|-------------|
| Coverage Matrix | Which protections are included/optional/zero-excess per company |
| Company Cards | Per-company package breakdown with daily prices and deductibles |
| **Price by Category** | Zero-excess daily price broken down by car category (Economy→Minivan). Prices are **editable** — click any cell to update. Changes saved to `insurance_price_overrides` DB table and persist across restarts. |
| Deductibles | Out-of-pocket excess comparison across coverage tiers |

### Research Workflow

1. Click **Trigger Research** — opens all 7 competitor insurance pages in new tabs simultaneously
2. Review each site and update any changed prices in the **Price by Category** table (click a price cell to edit inline)
3. Click **Mark Reviewed** — records a timestamped verification entry in the `insurance_reviews` log

The header shows `Research: April 2026 · Verified [date]` once reviewed.

### Confirmed prices (April 2026)

**Lotus Car Rental** — flat rate regardless of car category:

| Package | Deductible | Per Day |
|---------|-----------|---------|
| Silver (included in base) | 150,000 ISK | 2,190 ISK |
| Gold | 65,000 ISK | 4,650 ISK |
| Platinum | 0 ISK | 6,950 ISK |

Platinum uniquely includes river crossing protection and F-road insurance.

**Avis Iceland** — two size tiers (small cars / large cars):

| Package | Deductible | Small | Large |
|---------|-----------|-------|-------|
| Grunntrygging (base) | 195k / 360k ISK | Included | Included |
| Viðbótartrygging | 0 ISK | 2,700 ISK/day | 3,600 ISK/day |
| Aukin viðbótartrygging | 0 ISK + roadside | 4,450 ISK/day | 5,350 ISK/day |

**Other key findings:**
- **Lava Car Rental** — most comprehensive base bundle (7 protections by default, incl. SAAP + TIP)
- **Hertz Iceland** — only company where CDW is **not** in the base price
- **Go Car Rental** — uniquely prices all insurance in EUR, not ISK

---

## SEO Rank Tracker

Tracks Google ranking for `bluecarrental.is` across 10 pre-seeded Iceland car rental keywords:

- car rental reykjavik / car rental iceland
- rent a car keflavik airport / keflavik airport car rental
- cheap car hire iceland / best car rental iceland
- iceland car hire comparison / 4x4 rental iceland
- bílaleiga reykjavík / leigubíll ísland

Previous rank and change (▲/▼) are tracked per keyword independently using `ROW_NUMBER() OVER (PARTITION BY keyword)`.

Keywords are managed via Settings → Keywords or `POST /api/seo/keywords?keyword=...`.

Requires `SERPAPI_KEY` set in Settings or `.env`. Without a key, mock rankings are shown.

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

GET  /api/rates/deltas           Market-avg price delta between last two scrape dates
     ?location=  &category=

GET  /api/rates/price-changes    Per-competitor price delta (competitor::location::model key)
     ?location=  &category=

GET  /api/rates/scrape-log       Recent scrape history (manual + scheduled + seasonal)
     ?limit=20

GET  /api/rates/history
     ?location=  &car_category=  &competitor=  &days=30

GET  /api/rates/history/models
     ?location=  &competitor=  &days=30

GET  /api/rates/history/coverage
     ?location=  &days=30

GET  /api/rates/matrix
     ?location=  &pickup_date=  &return_date=  &category=

GET  /api/rates/seasonal         DB-first; response cached 30 min
     ?category=  &location=  &force=false

POST /api/rates/scrape-seasonal  Scrape all 12 anchor months and persist
     ?location=

GET  /api/rates/seasonal/history Time series showing how prices for one anchor month evolved
     ?pickup_date=YYYY-MM-DD  &category=  &location=

GET  /api/rates/scraper-status
GET  /api/rates/car-catalog
GET  /api/rates/car-mappings
POST /api/rates/car-mappings
DELETE /api/rates/car-mappings/{id}
```

### Insurance

```
GET  /api/insurance                  Full data + category pricing (with DB overrides)
GET  /api/insurance/category-pricing Base category pricing without overrides
POST /api/insurance/prices           Save a price override {company, category, price_isk, note}
GET  /api/insurance/review-log       Verification history
POST /api/insurance/mark-reviewed    Log a manual review event
```

### SEO Rank Tracking

```
GET  /api/seo/rankings
     ?keyword=  &location=

POST /api/seo/check
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
POST /api/settings

POST /api/alerts/test-webhook
POST /api/alerts/check
```

---

## Brand Colours

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

Toggle via moon/sun icon in the top bar. Persisted to `localStorage`. Implemented via `body.dark-mode` CSS class. Filter bar inputs (date pickers, selects) use `color-scheme: dark` for correct rendering.

---

## Repo Hygiene

- `blue_rental.db` and `.env` excluded via `.gitignore`
- Secrets (SerpAPI key, Slack webhook URL) stored in `config` DB table at runtime
