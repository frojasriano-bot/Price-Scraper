# Blue Rental Intelligence

Competitor pricing intelligence + insurance comparison + local SEO rank tracking for **Blue Car Rental Iceland**.

FastAPI backend · SQLite · APScheduler · Vanilla JS SPA · Chart.js

---

## Dashboard Tabs

| Tab | Description |
|-----|-------------|
| **Rate Intelligence** | Four live status tiles (Last Scrape, Scraper Health, Last Runs, Price Alerts); per-competitor freshness strip; executive summary banner; sortable rate table; **Competitive Radar** spider chart with ghost polygons (prev scrape) + companion table; cross-competitor matrix; price history; seasonal analysis; forward horizon; price changes; booking window; win/loss scorecard with CSV export |
| **Insurance Comparison** | Coverage matrix, per-category zero-excess pricing (editable inline) + package comparison, company cards, deductible comparison, Trigger Research + Mark Reviewed workflow with audit log |
| **SEO Rank Tracker** | Keyword ranking history with previous rank + change delta via SerpAPI; 5 Iceland car rental keywords pre-loaded |
| **Settings** | Scraper status, schedule config, SerpAPI key, location management, car model mappings, Slack alerts, scrape history log, category audit |
| **How to Use** | Step-by-step setup guide, automated schedule reference, view descriptions, and usage tips |

### Rate Intelligence — View Modes

| View | Description |
|------|-------------|
| **Competitive Radar** | Spider chart — one solid polygon per competitor (five axes, distance = average ISK/day); a faint dashed **ghost polygon** shows each competitor's position from the previous scrape so movement is immediately visible. Scale auto-fits to the data range (floor ≈ 80 % of cheapest value, ceiling ≈ 115 % of priciest). Companion table on the right shows clean k-ISK averages with green cell tint = cheapest, red = priciest per category column, plus a date-range context line. **Freshness strip** above the rates table shows per-competitor last-scraped age with amber (> 2 h) and red (> 12 h) stale indicators. |
| **List View** | Sortable table of all live rates per competitor + model, with per-day price and Δ vs previous scrape |
| **Car Model Matrix** | Cross-competitor price grid per canonical model; green = cheapest, red = most expensive |
| **Price History** | Time-series line charts per model grouped by category — shows how scraped prices have evolved over the past 7/14/30/90 days |
| **Seasonal Analysis** | Per-day pricing across the next 12 months (15th anchor date, 7-night stay). Three modes: default chart; **History** to see how a future month evolved across weekly scrapes; **Gap Map** heatmap. Toggle between **Competitors** view (all competitors × four seasons) and **By Category** view (market average per category × season) via the card header. |
| **Forward Rates** | Up to 12 months of competitor pricing — horizon line chart + color-coded heatmap table with 3M / 6M / 12M range toggle; scrape-driven, no estimates. Select a model from the dropdown for per-model competitor lines |
| **Price Changes** | Chronological activity feed of every meaningful competitor price move (≥5% by default). Filter by lookback window, category, and minimum change %. Select a specific model to view a line chart of its full scraped price history per competitor |
| **Booking Window** | Pick any future pickup date to see how each competitor's price has changed across successive weekly scrapes as that date approaches — reveals early-bird vs last-minute pricing strategy. Model drill-down available |
| **Win/Loss Scorecard** | Answers "where do we beat each competitor, and by how much?" Risk Alerts + Raise Opportunities panels; category position strip; price scatter chart. **Export CSV** button downloads per-model ISK/day vs every competitor with outcome labels. |
| **Fleet Pressure** | (1) **Availability snapshot** — Blue, Lotus, Lava, Go Car Rental polled across 1w / 2w / 4w windows with sold-out counts. (2) **Sold-Out Models** — named red-pill list filterable by window; **Inferred Signals** (Hertz/Avis/Holdur absence from scrape) shown inline below a divider in the same card. (3) **12-month calendar heatmap** — competitor × month grid coloured by availability %. |

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
main.py                  FastAPI app, APScheduler (8 jobs), lifespan setup
canonical.py             Car name normalisation (canonicalize()) +
                         category normalisation (canonicalize_category()) +
                         CANONICAL_CATEGORIES — single source of truth for
                         all 100 canonical models and their categories
database.py              SQLite schema, all DB helpers, migrations

routes/
  rates.py               /api/rates/* — scraper trigger, history, matrix,
                         seasonal (DB-first + history + gap map), forward
                         horizon (aggregate + per-model), price-timeline,
                         booking-window, scrape log
  insurance.py           /api/insurance — comparison data, category pricing
                         (with DB overrides), mark-reviewed workflow, review log
  seo.py                 /api/seo/* — rankings, keyword management
  settings.py            /api/settings — config, locations, scraper status,
                         category audit
  alerts.py              /api/alerts/* — Slack webhook config & test
  fleet.py               /api/fleet/* — fleet pressure snapshot, sold-out
                         models, 12-month calendar, absence alerts

scrapers/
  base.py                BaseScraper abstract class + mock data fallback
  blue_rental.py         ✅ Live — Caren API (bluecarrental.is)
  holdur.py              ✅ Live — HTML form scraper (holdur.is)
  lotus.py               ✅ Live — Caren API (lotuscarrental.is)
  avis_is.py             ✅ Live — HTML form scraper (avis.is)
  gocarrental.py         ✅ Live — GoRentals JSON API + Sanity CMS
  hertz_is.py            ✅ Live — WordPress/CarCloud ajax + HTML (hertz.is)
  lavacarrental.py       ✅ Live — Caren API (lavacarrental.is)
  goiceland_com.py       ✅ Live — Cloudflare Worker JSON API (goiceland.com, KEF only)
  fleet_pressure.py      Fleet intelligence: Caren + Go Car availability polling,
                         12-month calendar sweep, absence detection for
                         Hertz/Avis/Holdur via catalog comparison

static/
  index.html             Single-page dashboard shell
  app.js                 All frontend logic (Chart.js, tabs, dark mode)
  style.css              Styles + dark mode CSS vars
```

---

## Scrapers

All scrapers inherit from `BaseScraper` and implement `scrape_rates(location, pickup_date, return_date)`. On failure the base class falls back to deterministic mock pricing from each scraper's `FLEET` definition.

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
| Go Iceland | ✅ | — | Cloudflare Worker JSON API (KEF only) |

### Known scraper behaviours

- **Hertz**: Displays a single "from" floor price for multiple Economy models (website design, not a scraper bug). Returns HTTP 400 "at least 24 hours advance notice" for pickup dates within 24h — affects the nearest seasonal anchor slot only.
- **Holdur**: Server ignores `vehicleCategoryId` filter and returns all cars for every POST — duplicates stripped client-side
- **Go Car Rental**: Dacia Jogger appears twice (5-seat Compact + 7-seat Minivan) — two distinct class IDs in their CMS, both legitimate. API occasionally returns HTTP 500 (transient, retried automatically).
- **Lava Car Rental**: "4x4 Cars" group contains mixed SUVs and true 4x4s — classified as SUV with keyword promotion for vehicles like Land Rover Defender, Land Cruiser, Sorento. Occasionally returns HTTP 500 for past/near-future dates.
- **Go Iceland**: Uses a Cloudflare Worker backend (`goiceland-backend.orn-d86.workers.dev`). KEF only. Occasionally returns HTTP 500 for historical date ranges.

### Adding a live scraper

1. Open the scraper file and implement `scrape_rates(self, location, pickup_date, return_date)`
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

---

## Car Name & Category Normalisation

`canonical.py` is the single source of truth for all car data. It exposes three things:

### `canonicalize(name)` → str

Strips transmission/fuel suffixes (automatic, manual, petrol, diesel, hybrid, electric, awd, 4wd) and maps variant spellings to standard names via the `_EXACT` dict. Apostrophes are normalised so e.g. `"Kia Cee'd"` matches `"Kia Ceed"`.

```
"Toyota Landcruiser 150"            → "Toyota Land Cruiser 150"
"VW Transporter 4WD"                → "VW Transporter"
"Volkswagen Caravelle"              → "VW Caravelle"
"Kia Ceed Sportswagon"              → "Kia Ceed Wagon"
"Toyota Land Cruiser 4x4 35\" ..."  → "Toyota Land Cruiser 150"
"Dacia Duster Used Model"           → "Dacia Duster (Older Model)"
```

### `CANONICAL_CATEGORIES` → dict[str, str]

Maps every canonical model name to its category. 100 models across 5 categories:

| Category | Count |
|----------|-------|
| Economy  | 17 |
| Compact  | 18 |
| SUV      | 27 |
| 4x4      | 25 |
| Minivan  | 13 |

This dict is the **authoritative source** — `car_catalog` DB table is seeded from it, and `insert_rates()` applies it at write time so no category conflicts accumulate.

### `canonicalize_category(canonical_name, fallback)` → str

Looks up `CANONICAL_CATEGORIES[canonical_name]` and returns it. Falls back to the provided value if the model is unknown.

### Category Audit

Settings → Category Audit shows a live table of every model currently in the DB, its stored category, the correct category from `CANONICAL_CATEGORIES`, and whether they match. Summary stats show total models, mapped count, unmapped count, and conflict count.

---

## Database

SQLite via `aiosqlite`. Schema initialised automatically on startup by `init_db()`. Local file: `blue_rental.db`

| Table | Purpose |
|-------|---------|
| `rates` | Scraped rental rates — one row per competitor/location/model/scrape. Accumulates over time; no overwrites. |
| `car_catalog` | Master list of canonical car names and categories (seeded from `CANONICAL_CATEGORIES`) |
| `car_mappings` | Competitor model name → canonical name (editable via Settings) |
| `rankings` | SEO keyword rankings from SerpAPI |
| `config` | Key-value store: SerpAPI key, schedule, webhook URL, locations, SEO keywords |
| `seasonal_cache` | 30-minute response cache for the seasonal analysis endpoint |
| `fleet_pressure` | Time-series of fleet availability: competitor × location × window (1w/2w/4w) with `available_classes`, `total_classes`, and `availability_pct`. Feeds the pressure history chart |
| `scrape_log` | History of every manual, scheduled, seasonal, and horizon scrape run (rates, duration, errors) |
| `insurance_reviews` | Timestamped log of manual insurance data verifications |
| `insurance_price_overrides` | Per-company/category zero-excess price overrides (editable via Insurance tab) |
| `fleet_sold_out_models` | Per-poll record of every car class returned by Caren + Go Car API, with `is_available` flag and `car_name`. Used for sold-out pills and model-level drill-down |
| `fleet_availability_calendar` | Monthly availability snapshot: competitor × anchor_month with `total_classes`, `available_classes`, `availability_pct`. Feeds the 12-month heatmap |
| `competitor_catalog` | Known car models per competitor — built from historical `rates` scrapes via UPSERT on every scheduled scrape. Drives absence detection for Hertz/Avis/Holdur |
| `fleet_absence` | Inferred sold-out events: catalog models missing from Hertz/Avis/Holdur scrape results for a given anchor month |

### Migrations

Three one-time migrations run at startup (idempotent):

| Migration | Function | What it fixes |
|-----------|----------|---------------|
| `recanonicalize_all_rates()` | v2 | Re-applies `canonicalize()` to all stored `canonical_name` values |
| `recategorize_all_rates()` | v1 | Re-applies `canonicalize_category()` to all stored `car_category` values |
| `backfill_competitor_catalog()` | v1 | Seeds `competitor_catalog` from historical `rates` table on first run — required for absence detection to work on existing databases |

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

Changing the pickup or return date triggers a live scrape after an 800 ms debounce, so the table always reflects actual live pricing for the selected window. The return date is constrained to be at least 1 day after the pickup date; if a return date is selected before the pickup date it is automatically corrected to pickup + 3 days.

### CSV Export

Multiple export functions are available across views:

| Button | View | Contents |
|--------|------|----------|
| Export CSV | List View | All rates for the selected window — competitor, model, category, total ISK, per-day ISK, pickup/return dates |
| Export Matrix CSV | Car Model Matrix | Cross-competitor price grid with pickup/return dates and prices labelled "(ISK total)" |
| Export Seasonal CSV | Seasonal Analysis | Month-by-month per-day ISK per competitor + season summary rows with "vs Blue %" column |
| Export Horizon CSV | Forward Rates (all categories) | Weekly per-day ISK per competitor for the selected horizon range |
| Export Model CSV | Forward Rates (per-model view) | Weekly per-day ISK per competitor for the selected canonical model |

### Scrape History Log

Settings → Scrape History shows every run: timestamp, trigger (manual / scheduled / seasonal / horizon), location, rates scraped, competitors hit, duration, and error count.

---

## Seasonal Analysis

The seasonal view plots per-day pricing across the next 12 months, with one data point per competitor per month (pickup on the 15th, 7-night stay).

### Data architecture

The seasonal endpoint is **DB-first** — it reads from the `rates` table first and only live-scrapes months that have no stored anchor data:

1. For each of the 12 anchor months, query `rates WHERE pickup_date = 'YYYY-MM-15'`
2. If stored data exists → use it (fast, instant load)
3. If no stored data → live-scrape that month and persist the result for future requests
4. Response is cached for 30 minutes to avoid re-aggregating on every browser refresh

### Season summary tables

Two summary tables below the chart show per-competitor and per-category averages broken down by season band (Low / Shoulder / High / Peak). Each row includes a **vs Blue %** column showing how each competitor's average compares to Blue Car Rental's average for that season — green means the competitor is more expensive than Blue, red means cheaper.

### Scraping anchor dates

The **Scrape All** button (or `POST /api/rates/scrape-seasonal`) re-scrapes all 12 anchor months and stores fresh data. The weekly Monday cron does the same automatically.

### Price evolution / History mode

The **History** toggle switches the chart to show how prices for a selected future month have changed across successive weekly scrapes:

- X-axis: scrape dates (e.g. "7 Apr", "14 Apr", "21 Apr"...)
- Y-axis: per-day ISK
- One line per competitor

Requires at least 2 weekly snapshots for the selected anchor month. Shows "not enough data" message until then.

### Price Gap Heatmap (Gap Map mode)

The **Gap Map** toggle switches the seasonal chart to a heatmap showing Blue's price relative to the market average. A **Granularity** toggle (top-right of the card) offers two views:

#### By Category (default)
A 5×12 grid: 5 car categories (rows) × 12 future months (columns). Uses the same `state.seasonalData` already loaded — no extra API call.

#### By Model
A per-model, per-competitor breakdown for the selected category. Each row is one canonical model × one competitor, showing Blue's exact gap % versus that specific company across all 12 anchor months. Fetches from `GET /api/rates/seasonal/gap-by-model?category=`. More actionable than the category view — reveals whether pricing pressure comes from one specific rival or the whole market.

**Cell colour scale (both views):**
- **Green** = Blue is cheaper than the competitor (Blue undercuts that rival)
- **Red** = Blue is more expensive than the competitor (Blue charges a premium over that rival)
- **Neutral** = within ±3% of the competitor's price

**Special states:**
- *n/a* (grey) — no Blue price for this model/month
- *solo* (blue outline) — Blue is the only competitor with data; no market comparison possible

---

## Win/Loss Scorecard

`GET /api/rates/win-loss` compares every canonical car model where both Blue Car Rental and a competitor have a current scraped price. Uses the same snapshot as the matrix view.

**Outcome logic** (configurable via `?threshold=` param, default 5%):

| Outcome | Condition |
|---------|-----------|
| **Win** | Blue price more than `threshold`% cheaper than competitor |
| **Tie** | Within ±`threshold`% |
| **Loss** | Blue price more than `threshold`% more expensive |

`margin_pct` convention: negative = Blue cheaper (a win), positive = Blue more expensive (a loss).

### Summary strip

One card per competitor showing:
- Win rate % with colour-coded progress bar (green ≥60%, amber 40–59%, red <40%)
- W / T / L split counts
- Average win margin ("Blue X% cheaper when winning")
- Average loss margin ("Blue X% pricier when losing")

### Category grid

Competitor × category table; click any cell — or the **Overall** column — to open the model drill-down panel.

### Model drill-down

Sorted wins-first, then ties, then losses. Each row shows: model, category, Blue ISK price, competitor ISK price, outcome badge, margin %.

### Interpreting the data

The scorecard gives the sales team immediate answers to:
- Which competitors are genuinely beating Blue on price across most models?
- In which car categories is Blue strongest / weakest?
- For a specific competitor, exactly which models is Blue losing on and by how much?

---

## Forward Rate Horizon

The Forward Rates view shows **actual scraped prices** for future weekly pickup windows (today+1w through today+Nw, all 7-night stays). No estimates or interpolation — weeks with no scraped data show "No data — click Scrape Horizon".

### Range toggle

A **3M / 6M / 12M** toggle controls how many weeks are displayed and scraped:

| Button | Weeks | Scrape calls (8 competitors) |
|--------|-------|------------------------------|
| 3M | 13 | 104 |
| **6M** | **26** | **208** ← default |
| 12M | 52 | 416 |

The daily cron job always scrapes the full 26-week (6M) range.

### How it works

1. `GET /api/rates/horizon` queries the DB for the latest scraped rates for each weekly anchor date
2. Per-day prices are calculated using the **actual rental duration** (`return_date − pickup_date`) so 3-night and 7-night scrapes both produce correct values
3. Results are grouped by competitor and category; `_overall` is the cross-category average

### Horizon line chart

- X-axis: future pickup weeks (up to 52 data points)
- Y-axis: per-day ISK
- One line per competitor, filtered by selected category pill
- Lines end where data runs out — no phantom estimates

### Rate heatmap table

- Rows: each future week (with days-out indicator)
- Columns: one per competitor
- Cells: color-coded green → red (cheapest to most expensive within the selected window)
- "Cheapest" column identifies the cheapest competitor per week at a glance

### Category filter

Pills (All / Economy / Compact / SUV / 4x4 / Minivan) re-fetch the API with a `?category=` filter so the chart and heatmap show apples-to-apples comparison within one segment.

### Scraping

The **Scrape Horizon** button (`POST /api/rates/scrape-horizon`) runs all 8 scrapers against each weekly anchor date in the selected range. Results are stored in the `rates` table and available immediately.

The daily cron job also runs a 26-week horizon scrape at 07:15 automatically.

---

## Price Change Timeline

`GET /api/rates/price-timeline` compares consecutive scrape snapshots per competitor × model and returns only events where `abs(change_pct) ≥ min_change_pct` (default 5%).

### Feed view (no model selected)
Grouped by date, newest first. Each card shows: competitor colour dot, model name + category, ↑/↓ percentage change, and before/after per-day prices.

### Model drill-down (model selected)
Switches to a Chart.js line chart showing the absolute price per scrape date for each competitor carrying that model. Summary cards show each competitor's latest price and net overall change since the first recorded snapshot.

### Filters
- **Days back**: 7 / 14 / 30
- **Category**: all or a single category
- **Model**: all or a specific canonical model (resets when category changes)
- **Min change %**: 5% default; lower to capture smaller moves

---

## Booking Window Analysis

`GET /api/rates/booking-window` groups rates by competitor × scrape date for a specific future pickup date and returns the per-day price at each snapshot.

### How to read it
X-axis shows "X weeks before pickup" (e.g. "8 weeks before"). Y-axis shows per-day ISK. A line that drops sharply near pickup = last-minute discounting. A flat or rising line = yield management / early-bird pricing.

### Requirements
Needs at least 2 scrape snapshots for the selected pickup date (i.e. the same pickup date must have been scraped on at least two different days). Run **Scrape Horizon** regularly to accumulate lead-time history.

### Model drill-down
Select a model to filter to that canonical model only — useful for watching a specific vehicle class's lead-time curve.

---

## Scheduler

APScheduler (`AsyncIOScheduler`) runs eight jobs:

| Job | Schedule | Description |
|-----|----------|-------------|
| `scrape_rates` | Daily 07:00 (configurable) | Scrapes all competitors for today+7 → today+10; updates `competitor_catalog` via UPSERT |
| `seo_check` | Daily 07:30 (configurable) | Checks stored keywords via SerpAPI |
| `alert_check` | Daily 07:45 (configurable) | Fires Slack alerts if competitors undercut Blue |
| `scrape_seasonal` | **Every Monday 08:00** | Re-scrapes all 12 anchor months; always weekly |
| `scrape_horizon` | Daily 07:15 | Scrapes all 8 competitors × 26 future weekly windows (6 months) |
| `fleet_poll_morning` | Daily 09:00 | Polls Caren + Go Car for fleet availability across 1w / 2w / 4w; saves aggregate + named model records |
| `fleet_poll_evening` | Daily 21:00 | Same as morning poll — twice-daily cadence captures intra-day inventory changes |
| `fleet_calendar_poll` | **Every Monday 08:30** | 12-month calendar sweep for Caren + Go Car; then absence detection for Hertz/Avis/Holdur via catalog comparison |

The daily/hourly/weekly setting (configurable via Settings) applies to `scrape_rates`, `seo_check`, and `alert_check`. All other jobs run on fixed schedules regardless of the Settings configuration.

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

Tracks Google ranking for `bluecarrental.is` across configurable Iceland car rental keywords. Five keywords are pre-loaded by default:

- car rental reykjavik
- rent a car keflavik airport
- cheap car hire iceland
- bílaleiga reykjavík
- leigubíll ísland

Keywords are stored in the `config` DB table and persist across restarts. Add or remove keywords via Settings → Keywords or the API. There is no hard limit on keyword count.

Previous rank and change (▲/▼) are tracked per keyword independently using `ROW_NUMBER() OVER (PARTITION BY keyword)`.

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

GET  /api/rates/scrape-log       Recent scrape history (manual + scheduled + seasonal + horizon)
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

GET  /api/rates/seasonal/gap-by-model  Per-model gap vs market avg across 12 anchor months
     ?category=  &location=            (category is required)

GET  /api/rates/horizon          Next N weeks of per-day pricing per competitor (real data only)
     ?location=  &category=  &weeks=26  (default 26, max 52)

POST /api/rates/scrape-horizon   Scrape all competitors × N weekly windows and persist
     ?location=  &weeks=26  (default 26, max 52)

GET  /api/rates/model-horizon    All future scraped prices for one canonical model
     ?model=  &location=

GET  /api/rates/price-timeline   Chronological feed of meaningful price changes (≥min_change_pct%)
     ?days=30  &min_change_pct=5.0  &category=  &location=  &model=

GET  /api/rates/booking-window   Price trajectory for one pickup date across successive scrapes
     ?pickup_date=YYYY-MM-DD  &category=  &location=  &model=

GET  /api/rates/win-loss         Blue vs each competitor: wins / ties / losses per model & category
     ?location=  &category=  &threshold=5.0

GET  /api/rates/scraper-status
GET  /api/rates/car-catalog
GET  /api/rates/car-mappings
POST /api/rates/car-mappings
DELETE /api/rates/car-mappings/{id}    Returns 404 if mapping ID not found
```

### Settings & Category Audit

```
GET  /api/settings
POST /api/settings
GET  /api/settings/category-audit   Per-model category status (mapped / unmapped / conflict)
```

### Insurance

```
GET  /api/insurance                  Full data + category pricing (with DB overrides)
GET  /api/insurance/category-pricing Zero-excess category pricing with DB overrides applied
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

### Fleet Intelligence

```
GET  /api/fleet/pressure         Time-series of fleet availability (Caren + Go Car)
     ?location=  &days=30  &window_label=1w|2w|4w

GET  /api/fleet/pressure/latest  Most-recent snapshot per competitor × location × window

POST /api/fleet/poll             Manually trigger a fleet pressure poll and persist results

GET  /api/fleet/sold-out         Latest per-model availability — shows named sold-out models
     ?competitor=  &location=  &window_label=1w|2w|4w

GET  /api/fleet/calendar         12-month availability calendar with sold_out_models list per row
     ?location=

POST /api/fleet/calendar/poll    Full sweep: 12-month calendar (Caren + Go Car) + absence
                                 detection for Hertz, Avis, Holdur

GET  /api/fleet/absence          Absence-inferred sold-out events for Hertz, Avis, Holdur
     ?competitor=  &location=  &days=90
```

### Alerts

```
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
| Go Iceland | `#4ade80` |
| Hertz Iceland | `#eab308` |
| Lava Car Rental | `#a855f7` |

---

## Dark Mode

Toggle via moon/sun icon in the top bar. Persisted to `localStorage`. Implemented via `body.dark-mode` CSS class. Filter bar inputs (date pickers, selects) use `color-scheme: dark` for correct rendering.

---

## Repo Hygiene

- `blue_rental.db` and `.env` excluded via `.gitignore`
- Secrets (SerpAPI key, Slack webhook URL) stored in `config` DB table at runtime
- Python 3.9+ compatible (`from __future__ import annotations` used throughout)

---

## Known Exclusions

**MyCar Iceland (`mycar_is.py`)** — a scraper class exists for MyCar but is intentionally not registered in `ALL_SCRAPERS`. MyCar actively blocks automated requests, so including it would cause every scrape run to generate a failed request with no useful fallback data.

---

## Changelog

### April 2026

- **XSS protection** — `escHtml()` helper defined in `app.js` and applied to all innerHTML interpolation (car model names, competitor names, keywords, URLs, etc.)
- **API correctness** — `DELETE /api/rates/car-mappings/{id}` now returns HTTP 404 if the mapping ID does not exist (previously always returned 200)
- **Fetch timeout** — `apiFetch()` now uses `AbortController` with a 30-second default timeout; hanging requests no longer block the UI indefinitely
- **Scraper failure logging** — `BaseScraper.run()` now logs a WARNING (competitor name, location, exception) before falling back to mock data, making silent scrape failures visible in the server log
- **Go Car Rental scraper** — `_get_class_info()` now uses `id_ is None` instead of `not id_` so a hypothetical class ID of 0 is no longer silently dropped
- **Database index** — added `idx_scrape_log_trigger ON scrape_log(trigger)` for faster scrape log filtering by trigger type
- **Design system** — `--font` and `--mono` CSS custom properties added to `:root`; `html, body` now uses `var(--font)` instead of a hardcoded font stack
