# Blue Rental Intelligence — Next Session Brief

## Project Overview

FastAPI + SQLite + Vanilla JS SPA for Blue Car Rental Iceland. Competitor pricing intelligence dashboard.
Repo: https://github.com/frojasriano-bot/Price-Scraper  
Server: `python main.py` → http://localhost:8000  
Latest commit: `27036ff` (main branch, fully pushed)

---

## Current Architecture

```
main.py              FastAPI app, APScheduler (5 jobs), lifespan
canonical.py         100 canonical models, 5 categories (Economy/Compact/SUV/4x4/Minivan)
database.py          SQLite via aiosqlite — all DB helpers (1460 lines)
routes/rates.py      /api/rates/* (909 lines)
routes/insurance.py  /api/insurance/*
routes/seo.py        /api/seo/*
routes/settings.py   /api/settings/*
routes/alerts.py     /api/alerts/*
static/app.js        All frontend logic — 3342 lines
static/index.html    SPA shell — 1331 lines
static/style.css     Styles + dark mode — 929 lines
```

**DB file:** `blue_rental.db` (SQLite, local, gitignored)

---

## Frontend Architecture

### State object (top of app.js)
```javascript
const state = {
  currentTab: 'rates',
  ratesView: 'list',        // 'list'|'matrix'|'history'|'seasonal'|'horizon-fwd'
  rates: [], ratesSource: 'mock',
  matrix: null, matrixSource: 'mock',
  historyData: null, historyCharts: {}, historySource: 'mock',
  historyCategory: '', historyModelSearch: '', historyCoverage: null,
  ratesSort: { col: null, dir: 'asc' },
  seasonalData: null, seasonalChart: null,
  historyMode: false,             // seasonal history evolution mode
  historyEvolutionData: null, historyEvolutionChart: null, historyEvolutionMonth: null,
  horizonData: null, horizonChart: null,
  horizonCategory: '', horizonWeeks: 26, horizonScraping: false,
  horizonModel: '', modelHorizonData: null, modelHorizonChart: null,
  deltas: {}, deltasAvailable: false,
  priceChanges: {}, priceChangesAvailable: false,
  rankings: [], rankingsSource: 'mock', rankingsHistory: [], seoKeywords: [],
  seoSort: { col: 'rank', dir: 'asc' }, seoChartFilter: 'all',
  settings: {}, locations: [],
};
```

### Tab switching
- `switchTab(tab)` — hides all source badges, calls appropriate `loadX()`
- Tabs: `rates`, `seo`, `insurance`, `settings`, `guide`

### View switching (within Rates tab)
- `setRatesView(view)` — shows/hides `view-list`, `view-matrix`, `view-history`, `view-seasonal`, `view-horizon-fwd`
- Toggles `.active` on corresponding view buttons

### Brand colors (used in all charts)
```javascript
const BRAND_COLORS = {
  'Avis Iceland':    '#ef4444',
  'Blue Car Rental': '#2563eb',
  'Go Car Rental':   '#f97316',
  'Hertz Iceland':   '#eab308',
  'Holdur':          '#22c55e',
  'Lava Car Rental': '#a855f7',
  'Lotus Car Rental':'#881337',
};
function compColor(name, fallbackIndex = 0) { ... }
```

### Key API helper
```javascript
async function apiFetch(url, opts = {}) { ... }  // handles JSON, errors
function downloadCSV(filename, rows) { ... }       // CSV export helper
function formatISK(amount) { ... }                 // Intl.NumberFormat ISK
function setSourceBadge(id, source) { ... }        // shows Live/Mock badge
function showToast(msg, type, duration) { ... }    // toast notifications
```

---

## Existing API Endpoints (relevant ones)

```
GET  /api/rates                        ?location= &pickup_date= &return_date= &car_category=
GET  /api/rates/matrix                 ?location= &pickup_date= &return_date= &category=
GET  /api/rates/history                ?location= &car_category= &competitor= &days=30
GET  /api/rates/history/models         ?location= &competitor= &days=30
GET  /api/rates/seasonal               ?category= &location=    (DB-first, 30-min cache)
GET  /api/rates/seasonal/history       ?pickup_date=YYYY-MM-15 &category= &location=
GET  /api/rates/horizon                ?location= &category= &weeks=26 (max 52)
GET  /api/rates/model-horizon          ?model= &location=
GET  /api/rates/price-changes          ?location= &category=
POST /api/rates/scrape                 ?location= &pickup_date= &return_date=
POST /api/rates/scrape-horizon         ?location= &weeks=26
POST /api/rates/scrape-seasonal        ?location=
```

### Key DB table: `rates`
```sql
competitor, location, pickup_date, return_date, car_category,
car_model, canonical_name, price_isk, currency, scraped_at
```
Per-day price = `price_isk / (return_date - pickup_date).days`

### Season bands (defined in routes/rates.py lines 44-55)
```python
MONTH_SEASONS = {
  1:("low","Low Season"), 2:("low","Low Season"), 3:("low","Low Season"),
  4:("shoulder","Shoulder"), 5:("shoulder","Shoulder"),
  6:("high","High Season"), 7:("peak","Peak Season"), 8:("high","High Season"),
  9:("shoulder","Shoulder"), 10:("shoulder","Shoulder"),
  11:("low","Low Season"), 12:("low","Low Season"),
}
```

---

## HTML Structure (static/index.html)

```
tab-rates
  view-list        — bar chart + sortable rates table
  view-matrix      — cross-competitor price grid
  view-history     — time series line charts by category
  view-seasonal    — 12-month per-day chart + 2 summary tables (vs Blue %)
  view-horizon-fwd — horizon line chart + heatmap + per-model chart
tab-seo
tab-insurance
tab-settings
tab-guide         — How to Use (4 cards, no JS needed)
```

---

## Three New Features to Build

### Feature 1: Booking Window / Lead Time Analysis

**What it is:** For any future pickup date, show how ALL competitors' prices have changed week-by-week as that date approaches. Shows price trajectory (rising / falling / stable) as bookings fill up.

**How it differs from existing "Seasonal History" mode:**
- Seasonal History: monthly granularity, only shows how one month's price evolved
- Booking Window: weekly granularity, shows lead-time behaviour across ALL future dates simultaneously

**Data source:** Already in the `rates` table — we have `pickup_date` and `scraped_at`. Query: group by `pickup_date`, order by `scraped_at`, compute per-day ISK per scrape snapshot.

**Proposed API endpoint:**
```
GET /api/rates/booking-window
  ?pickup_date=YYYY-MM-DD   (required — the future pickup date to analyse)
  &location=
  &category=
  &weeks_back=12            (how many scrape snapshots back to show)
Response: {
  "pickup_date": "2026-07-15",
  "series": {
    "Blue Car Rental": [{"scraped_at":"2026-04-10","per_day":12000}, ...],
    "Holdur": [...],
    ...
  }
}
```

**Frontend placement:** New view inside Rate Intelligence — `view-booking-window`. Button in the view toggle row. Needs a date picker to select which future pickup date to analyse + category filter. Renders a Chart.js line chart (one line per competitor, x-axis = scrape date / weeks-before-pickup, y-axis = per-day ISK).

**Key insight to highlight:** Label x-axis as "X weeks before pickup" (not scrape date) — so users can see "Hertz drops prices 4 weeks out, Holdur holds firm until 1 week out."

---

### Feature 2: Price Gap Heatmap

**What it is:** Single glanceable matrix showing how Blue's price compares to market average across every category × month combination.

**Rows:** 5 categories (Economy, Compact, SUV, 4x4, Minivan)  
**Columns:** 12 months (May 2026 → Apr 2027)  
**Cell value:** Blue's per-day ISK vs market avg per-day ISK = `((blue - market_avg) / market_avg) * 100`  
**Cell colour:**
- Green = Blue is MORE expensive than market (opportunity to be competitive / raise concern)
- Red = Blue is CHEAPER than market (good position or leaving money on table)
- White/neutral = within ±5%

**Data source:** `/api/rates/seasonal` already returns `months[].competitors` and `months[].market_avg` per category. All data is already available — this is a pure frontend feature.

**Frontend placement:** Inside `view-seasonal` as a toggle alongside the existing chart. A "Heatmap" toggle button (next to existing "History" button). When active, hides the line chart and shows the heatmap grid instead.

**Cell content:**
```
+12%        (Blue is 12% above market — shown in green)
-8%         (Blue is 8% below market — shown in red)
—           (no data)
```

No new API needed — use `state.seasonalData` that's already loaded.

---

### Feature 3: Competitor Price Change Timeline

**What it is:** Chronological activity feed showing every meaningful price move across all competitors. Like a news feed for pricing.

**Example entries:**
```
↑ Hertz Iceland raised Economy by +18% (ISK 8,200 → ISK 9,700) — Apr 10
↓ Lava Car Rental dropped 4x4 by -12% (ISK 28,000 → ISK 24,600) — Apr 9
↑ Go Car Rental raised Compact by +6% (ISK 11,000 → ISK 11,660) — Apr 8
```

**Data source:** `GET /api/rates/price-changes` already returns per-competitor/model deltas but only for the two most recent scrape dates. Need a richer endpoint that looks back further.

**Proposed API endpoint:**
```
GET /api/rates/price-timeline
  ?location=
  &category=
  &days=30
  &min_change_pct=5     (filter out noise — only show moves ≥ 5%)
Response: {
  "events": [
    {
      "competitor": "Hertz Iceland",
      "canonical_name": "Toyota Yaris",
      "car_category": "Economy",
      "scraped_at": "2026-04-10T07:15:00",
      "prev_price": 8200,
      "curr_price": 9700,
      "prev_per_day": 1171,
      "curr_per_day": 1386,
      "change_pct": 18.3,
      "direction": "up"
    },
    ...
  ]
}
```

**DB query logic:** For each competitor × model, find all scrape snapshots ordered by `scraped_at`, compute delta between consecutive snapshots, filter by `abs(change_pct) >= min_change_pct`, return as flat list sorted by `scraped_at DESC`.

**Frontend placement:** New view inside Rate Intelligence — `view-timeline`. Button in view toggle row. Renders as a vertical feed of cards (not a chart). Each card shows competitor badge (with brand colour), model + category, price before/after, percentage change with ↑/↓ arrow, and date. Filter controls: days lookback (7/14/30) + category pill filter + minimum change % slider/select.

---

## Implementation Order Suggested

1. **Price Gap Heatmap** first — pure frontend, no new API, ~2-3 hours. Uses existing `state.seasonalData`.
2. **Competitor Price Change Timeline** second — needs new DB query + endpoint + feed UI, ~4-5 hours.
3. **Booking Window** last — needs new DB query + endpoint + chart, ~4-5 hours.

---

## CSS Patterns to Follow

```css
/* Cards */
.card { background: var(--bg); border: 1px solid var(--border); border-radius: var(--radius); margin-bottom: 16px; }
.card-header { display: flex; align-items: center; justify-content: space-between; padding: 16px 20px; }
.card-title { font-size: 15px; font-weight: 600; color: var(--text); }
.card-subtitle { font-size: 12px; color: var(--text-muted); margin-top: 2px; }

/* Buttons */
.btn.btn-secondary.btn-sm  — standard small action button
.btn.btn-secondary.btn-sm.active  — active/selected state (blue background)

/* Badges */
.badge.badge-green  — Live Data
.badge.badge-gray   — Mock Data / Manual Data

/* Category pills pattern (copy from horizon) */
<button class="btn btn-secondary btn-sm active" onclick="setXCategory('')">All</button>
<button class="btn btn-secondary btn-sm" onclick="setXCategory('Economy')">🚗 Economy</button>
```

---

## Things NOT to Change

- `canonical.py` — do not touch, single source of truth
- `database.py` schema — add new query functions only, don't alter existing tables
- `canonicalize()` / `CANONICAL_CATEGORIES` — stable
- Existing API endpoints — additive only, no breaking changes
- `scrapeHorizon()` / `loadHorizon()` logic — already working correctly

---

## Quick Reference: Adding a New View

1. Add button to view toggle row in `index.html` (after Forward Rates button)
2. Add `<div id="view-newname">` panel in `index.html`
3. In `setRatesView()` in `app.js`: add `document.getElementById('view-newname').style.display = view === 'newname' ? '' : 'none'` and `.classList.toggle('active', view === 'newname')`
4. Add `if (view === 'newname') loadNewView()` to `setRatesView()`
5. Add `loadNewView()`, `renderNewView()` functions to `app.js`

## Quick Reference: Adding a New API Endpoint

1. Add DB query function to `database.py`
2. Add import in `routes/rates.py`
3. Add `@router.get("/new-endpoint")` in `routes/rates.py`
4. No changes to `main.py` needed (router already mounted at `/api/rates`)
