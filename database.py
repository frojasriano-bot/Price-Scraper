"""
Database initialization and helpers for Blue Rental Intelligence.
Uses aiosqlite for async SQLite access.
"""

from __future__ import annotations

import aiosqlite
import json
from datetime import datetime, timezone
from pathlib import Path

from canonical import canonicalize, canonicalize_category, CANONICAL_CATEGORIES

DB_PATH = Path(__file__).parent / "blue_rental.db"

# NOTE: Car catalog is now derived from canonical.CANONICAL_CATEGORIES
# (the single source of truth for car → category mappings).

# Maps (competitor, competitor_model_name) → canonical_name
# Used to seed the car_mappings DB table (informational reference).
# The runtime normalisation is handled by canonical.canonicalize() applied
# in insert_rates() — so this list no longer needs to be exhaustive.
CAR_NAME_MAPPINGS = [
    # Lava
    ("Lava Car Rental", "Dacia Sandero Stepway",         "Dacia Sandero"),
    # Lotus
    ("Lotus Car Rental", "Toyota Land Cruiser 150 4x4",  "Toyota Land Cruiser 150"),
    ("Lotus Car Rental", "Toyota Land Cruiser 250 4x4",  "Toyota Land Cruiser 250"),
    ("Lotus Car Rental", "Kia Ceed Wagon",               "Kia Ceed Wagon"),
    ("Lotus Car Rental", "Volkswagen Caravelle 4x4",     "VW Caravelle"),
    ("Lotus Car Rental", "Mercedes Benz Vito",           "Mercedes Vito"),
    ("Lotus Car Rental", "Lexus UX250H 4x4",             "Lexus UX250H"),
    ("Lotus Car Rental", "Dacia Duster 4x4",             "Dacia Duster"),
    ("Lotus Car Rental", "Suzuki Vitara 4x4",            "Suzuki Vitara"),
    ("Lotus Car Rental", "Jeep Renegade 4x4",            "Jeep Renegade"),
    ("Lotus Car Rental", "Jeep Compass 4x4",             "Jeep Compass"),
    ("Lotus Car Rental", "Kia Sportage 4x4",             "Kia Sportage"),
    ("Lotus Car Rental", "Toyota RAV4 4x4",              "Toyota RAV4"),
    ("Lotus Car Rental", "Subaru Forester 4x4",          "Subaru Forester"),
    ("Lotus Car Rental", "Toyota Yaris Cross 4x4",       "Toyota Yaris Cross"),
    ("Lotus Car Rental", "Honda CR-V 4x4",               "Honda CR-V"),
    ("Lotus Car Rental", "Kia Sorento 4x4",              "Kia Sorento"),
    ("Lotus Car Rental", "Toyota Highlander GX 4x4",     "Toyota Highlander"),
    ("Lotus Car Rental", "Toyota Hilux 4x4",             "Toyota Hilux"),
    ("Lotus Car Rental", "Tesla Model 3 Long Range 4x4", "Tesla Model 3"),
    # Holdur
    ("Holdur", "Toyota Landcruiser 150",                 "Toyota Land Cruiser 150"),
    ("Holdur", "Toyota Landcruiser 250",                 "Toyota Land Cruiser 250"),
    ("Holdur", "Mercedes Benz 350 GLE PHEV",             "Mercedes GLE"),
    ("Holdur", "Mercedes GLE PHEV",                     "Mercedes GLE"),
    ("Holdur", "Mitsubishi Outlander PHEV",              "Mitsubishi Outlander"),
    ("Holdur", "Skoda Octavia Combi",                    "Skoda Octavia Wagon"),
    ("Holdur", "Kia Ceed Sportswagon",                   "Kia Ceed Wagon"),
    ("Holdur", "VW Caravelle",                           "VW Caravelle"),
    # Hertz
    ("Hertz Iceland", "Toyota Corolla Wagon",            "Toyota Corolla Wagon"),
    ("Hertz Iceland", "Hyundai i30 Wagon",               "Hyundai i30"),
    ("Hertz Iceland", "Skoda Octavia Wagon",             "Skoda Octavia Wagon"),
    ("Hertz Iceland", "VW Caravelle",                    "VW Caravelle"),
    # Blue Car Rental
    ("Blue Car Rental", "Toyota Land Cruiser 150 (7 seater)", "Toyota Land Cruiser 150"),
    ("Blue Car Rental", "Toyota Land Cruiser 150, 7 seater",  "Toyota Land Cruiser 150"),
    ("Blue Car Rental", "Toyota Land Cruiser Adventure",      "Toyota Land Cruiser 250"),
    ("Blue Car Rental", "Jeep Wrangler RUBICON",              "Jeep Wrangler"),
    ("Blue Car Rental", "Opel Corsa Electric",                "Opel Corsa"),
    # Go Car Rental
    ("Go Car Rental", "Kia Ceed Wagon",                  "Kia Ceed Wagon"),
    ("Go Car Rental", "Volkswagen Caravelle",            "VW Caravelle"),
    ("Go Car Rental", "Jeep Wrangler Rubicon",           "Jeep Wrangler"),
]

CATEGORY_ORDER = ["Economy", "Compact", "SUV", "4x4", "Minivan"]


async def get_db():
    """Async context manager for database connections."""
    db = await aiosqlite.connect(DB_PATH)
    db.row_factory = aiosqlite.Row
    try:
        yield db
    finally:
        await db.close()


async def init_db():
    """Initialize the database schema and seed default config."""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row

        # Rates table
        await db.execute("""
            CREATE TABLE IF NOT EXISTS rates (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                competitor TEXT NOT NULL,
                location TEXT NOT NULL,
                pickup_date TEXT NOT NULL,
                return_date TEXT NOT NULL,
                car_category TEXT NOT NULL,
                car_model TEXT,
                canonical_name TEXT,
                price_isk INTEGER NOT NULL,
                currency TEXT NOT NULL DEFAULT 'ISK',
                scraped_at TEXT NOT NULL
            )
        """)

        # Migrate existing DB: add car_model and canonical_name columns if missing
        for col in ("car_model", "canonical_name"):
            try:
                await db.execute(f"ALTER TABLE rates ADD COLUMN {col} TEXT")
            except Exception:
                pass  # Column already exists

        # Car catalog: canonical car names and their categories
        await db.execute("""
            CREATE TABLE IF NOT EXISTS car_catalog (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                canonical_name TEXT NOT NULL UNIQUE,
                category TEXT NOT NULL
            )
        """)

        # Competitor model name → canonical name mappings
        await db.execute("""
            CREATE TABLE IF NOT EXISTS car_mappings (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                competitor TEXT NOT NULL,
                competitor_model TEXT NOT NULL,
                canonical_name TEXT NOT NULL,
                UNIQUE(competitor, competitor_model)
            )
        """)

        # Rankings table
        await db.execute("""
            CREATE TABLE IF NOT EXISTS rankings (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                keyword TEXT NOT NULL,
                location TEXT NOT NULL,
                rank INTEGER,
                url TEXT,
                serp_date TEXT NOT NULL,
                created_at TEXT NOT NULL
            )
        """)

        # Config table for settings
        await db.execute("""
            CREATE TABLE IF NOT EXISTS config (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
        """)

        # Seasonal analysis cache
        await db.execute("""
            CREATE TABLE IF NOT EXISTS seasonal_cache (
                cache_key TEXT PRIMARY KEY,
                cached_at TEXT NOT NULL,
                data_json TEXT NOT NULL
            )
        """)

        # Insurance price overrides (per-company, per-category editable prices)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS insurance_price_overrides (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                company TEXT NOT NULL,
                category TEXT NOT NULL,
                price_isk INTEGER,
                price_note TEXT,
                updated_at TEXT NOT NULL,
                UNIQUE(company, category)
            )
        """)

        # Insurance review / verification log
        await db.execute("""
            CREATE TABLE IF NOT EXISTS insurance_reviews (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                reviewed_at TEXT NOT NULL,
                reviewer TEXT,
                notes TEXT,
                companies_verified TEXT
            )
        """)

        # Scrape history log
        await db.execute("""
            CREATE TABLE IF NOT EXISTS scrape_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                scraped_at TEXT NOT NULL,
                location TEXT,
                total_rates INTEGER NOT NULL DEFAULT 0,
                competitors INTEGER NOT NULL DEFAULT 0,
                errors TEXT,
                duration_seconds REAL,
                trigger TEXT NOT NULL DEFAULT 'manual'
            )
        """)

        # Indexes for query performance (safe to re-run — IF NOT EXISTS)
        await db.execute(
            "CREATE INDEX IF NOT EXISTS idx_rates_scraped_at ON rates(scraped_at)"
        )
        await db.execute(
            "CREATE INDEX IF NOT EXISTS idx_rates_competitor ON rates(competitor)"
        )
        await db.execute(
            "CREATE INDEX IF NOT EXISTS idx_rates_lookup ON rates(competitor, location, car_model, scraped_at)"
        )
        await db.execute(
            "CREATE INDEX IF NOT EXISTS idx_rankings_keyword ON rankings(keyword, serp_date)"
        )

        await db.commit()

        # Seed car catalog from canonical category map (single source of truth)
        for canonical_name, category in CANONICAL_CATEGORIES.items():
            await db.execute(
                "INSERT OR IGNORE INTO car_catalog (canonical_name, category) VALUES (?, ?)",
                (canonical_name, category),
            )

        # Seed competitor model mappings
        for competitor, competitor_model, canonical_name in CAR_NAME_MAPPINGS:
            await db.execute(
                "INSERT OR IGNORE INTO car_mappings (competitor, competitor_model, canonical_name) VALUES (?, ?, ?)",
                (competitor, competitor_model, canonical_name),
            )

        await db.commit()

        # Seed default config if missing
        defaults = {
            "serpapi_key": "",
            "scrape_schedule": "daily",
            "alert_webhook_url": "",
            "alert_threshold_pct": "10",
            "locations": json.dumps([
                {"name": "Keflavik Airport", "address": "Keflavíkurflugvöllur, 235 Reykjanesbær, Iceland"},
                {"name": "Reykjavik", "address": "Reykjavík, Iceland"},
            ]),
            "seo_keywords": json.dumps([
                "car rental reykjavik",
                "car rental iceland",
                "rent a car keflavik airport",
                "cheap car hire iceland",
                "bílaleiga reykjavík",
                "leigubíll ísland",
                "4x4 rental iceland",
                "iceland car hire comparison",
                "keflavik airport car rental",
                "best car rental iceland",
            ]),
        }
        for key, value in defaults.items():
            await db.execute(
                """
                INSERT OR IGNORE INTO config (key, value, updated_at)
                VALUES (?, ?, ?)
                """,
                (key, value, datetime.now(timezone.utc).isoformat()),
            )
        await db.commit()


async def recanonicalize_all_rates():
    """
    One-time migration: re-apply canonicalize() + Holdur name cleaning to every
    row in the rates table. Fixes stale canonical_name values from before scraper
    and canonical.py improvements. Runs on startup; skips if already done.
    """
    import re

    # Holdur name cleaning patterns (same as scrapers/holdur.py)
    _PREFIX = re.compile(r"^[A-Z0-9]+[-–]\s*", re.UNICODE)
    _SUFFIX = re.compile(r"\s*-\s*eða\s+sambærilegur\s*$", re.IGNORECASE | re.UNICODE)
    _TRANS  = re.compile(
        r"\s+(?:sjálfskiptur|sjálfskipti|handskiptur|handskipti)\b.*$",
        re.IGNORECASE | re.UNICODE,
    )

    def _clean(raw: str) -> str:
        name = _PREFIX.sub("", raw.strip())
        name = _SUFFIX.sub("", name).strip()
        name = _TRANS.sub("", name).strip()
        return name

    async with aiosqlite.connect(DB_PATH) as db:
        # Check if migration already ran
        db.row_factory = aiosqlite.Row
        row = await db.execute_fetchall(
            "SELECT value FROM config WHERE key = 'canonical_migration_v2'"
        )
        if row:
            return  # already done

        cursor = await db.execute("SELECT rowid AS rid, car_model, canonical_name FROM rates")
        rows = await cursor.fetchall()

        updates = []
        for r in rows:
            old_canonical = r["canonical_name"] or ""
            raw_model     = r["car_model"] or ""

            # Step 1: clean Holdur-style names from the car_model
            cleaned = _clean(raw_model)
            # Step 2: re-canonicalize
            new_canonical = canonicalize(cleaned)
            # Also re-canonicalize whatever was in canonical_name (it may already be clean)
            alt_canonical = canonicalize(_clean(old_canonical))

            # Pick whichever gives a shorter/cleaner result (a mapped name is always better)
            best = new_canonical if len(new_canonical) <= len(alt_canonical) else alt_canonical

            if best != old_canonical:
                updates.append((best, cleaned, r["rid"]))

        if updates:
            await db.executemany(
                "UPDATE rates SET canonical_name = ?, car_model = ? WHERE rowid = ?",
                updates,
            )

        # Mark migration as done
        await db.execute(
            "INSERT OR REPLACE INTO config (key, value, updated_at) VALUES (?, ?, ?)",
            ("canonical_migration_v2", str(len(updates)), datetime.now(timezone.utc).isoformat()),
        )
        await db.commit()

    if updates:
        print(f"[migration] Re-canonicalized {len(updates)} rates rows.")


async def recategorize_all_rates():
    """
    Migration v3: apply CANONICAL_CATEGORIES to every row in the rates table.
    Fixes historical data where scrapers assigned wrong categories.
    """
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        row = await db.execute_fetchall(
            "SELECT value FROM config WHERE key = 'category_migration_v1'"
        )
        if row:
            return

        cursor = await db.execute(
            "SELECT rowid AS rid, canonical_name, car_category FROM rates"
        )
        rows = await cursor.fetchall()

        updates = []
        for r in rows:
            canonical = r["canonical_name"] or ""
            old_cat = r["car_category"] or ""
            new_cat = canonicalize_category(canonical, old_cat)
            if new_cat != old_cat:
                updates.append((new_cat, r["rid"]))

        if updates:
            await db.executemany(
                "UPDATE rates SET car_category = ? WHERE rowid = ?",
                updates,
            )

        await db.execute(
            "INSERT OR REPLACE INTO config (key, value, updated_at) VALUES (?, ?, ?)",
            ("category_migration_v1", str(len(updates)), datetime.now(timezone.utc).isoformat()),
        )
        await db.commit()

    if updates:
        print(f"[migration] Re-categorized {len(updates)} rates rows.")


async def get_category_audit():
    """
    Return category audit data: every canonical name, its assigned category,
    the row count, and whether it conflicts with the canonical category map.
    """
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute("""
            SELECT canonical_name, car_category, COUNT(*) as cnt
            FROM rates
            GROUP BY canonical_name, car_category
            ORDER BY canonical_name, car_category
        """)
        rows = await cursor.fetchall()

    from canonical import CANONICAL_CATEGORIES

    results = []
    for r in rows:
        canonical = r["canonical_name"]
        db_cat = r["car_category"]
        correct_cat = CANONICAL_CATEGORIES.get(canonical)
        results.append({
            "canonical_name": canonical,
            "db_category": db_cat,
            "correct_category": correct_cat,
            "count": r["cnt"],
            "is_mapped": correct_cat is not None,
            "is_correct": correct_cat == db_cat if correct_cat else True,
        })

    return results


async def get_config(key: str, default=None):
    """Retrieve a config value by key."""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT value FROM config WHERE key = ?", (key,)) as cursor:
            row = await cursor.fetchone()
            if row:
                return row["value"]
            return default


async def set_config(key: str, value: str):
    """Upsert a config value."""
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            """
            INSERT INTO config (key, value, updated_at)
            VALUES (?, ?, ?)
            ON CONFLICT(key) DO UPDATE SET value = excluded.value, updated_at = excluded.updated_at
            """,
            (key, value, datetime.now(timezone.utc).isoformat()),
        )
        await db.commit()


async def insert_rates(rates: list[dict]):
    """
    Bulk insert rate records, normalising canonical_name via canonicalize()
    so that name variants from different scrapers are unified before storage.
    """
    normalised = []
    for r in rates:
        row = dict(r)
        raw = row.get("canonical_name") or row.get("car_model") or ""
        row["canonical_name"] = canonicalize(raw)
        row["car_category"] = canonicalize_category(
            row["canonical_name"], row.get("car_category", "")
        )
        normalised.append(row)

    async with aiosqlite.connect(DB_PATH) as db:
        await db.executemany(
            """
            INSERT INTO rates (competitor, location, pickup_date, return_date, car_category, car_model, canonical_name, price_isk, currency, scraped_at)
            VALUES (:competitor, :location, :pickup_date, :return_date, :car_category, :car_model, :canonical_name, :price_isk, :currency, :scraped_at)
            """,
            normalised,
        )
        await db.commit()


async def insert_rankings(rankings: list[dict]):
    """Bulk insert ranking records."""
    async with aiosqlite.connect(DB_PATH) as db:
        await db.executemany(
            """
            INSERT INTO rankings (keyword, location, rank, url, serp_date, created_at)
            VALUES (:keyword, :location, :rank, :url, :serp_date, :created_at)
            """,
            rankings,
        )
        await db.commit()


async def get_latest_rates(location: str = None, pickup_date: str = None,
                            return_date: str = None, car_category: str = None,
                            car_model: str = None) -> list[dict]:
    """
    Return the most recent rate per (competitor, location, car_model) combination,
    optionally filtered.
    """
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row

        inner_conds = []
        outer_conds = []
        inner_params = []
        outer_params = []

        if location:
            inner_conds.append("location = ?")
            outer_conds.append("r.location = ?")
            inner_params.append(location)
            outer_params.append(location)
        if pickup_date:
            inner_conds.append("pickup_date = ?")
            outer_conds.append("r.pickup_date = ?")
            inner_params.append(pickup_date)
            outer_params.append(pickup_date)
        if return_date:
            inner_conds.append("return_date = ?")
            outer_conds.append("r.return_date = ?")
            inner_params.append(return_date)
            outer_params.append(return_date)
        if car_category:
            inner_conds.append("car_category = ?")
            outer_conds.append("r.car_category = ?")
            inner_params.append(car_category)
            outer_params.append(car_category)
        if car_model:
            inner_conds.append("(car_model = ? OR canonical_name = ?)")
            outer_conds.append("(r.car_model = ? OR r.canonical_name = ?)")
            inner_params.extend([car_model, car_model])
            outer_params.extend([car_model, car_model])

        inner_where = ("WHERE " + " AND ".join(inner_conds)) if inner_conds else ""
        outer_where = ("WHERE " + " AND ".join(outer_conds)) if outer_conds else ""

        query = f"""
            SELECT r.*
            FROM rates r
            INNER JOIN (
                SELECT competitor, location, COALESCE(car_model, car_category) AS model_key,
                       MAX(scraped_at) AS max_scraped
                FROM rates
                {inner_where}
                GROUP BY competitor, location, model_key
            ) latest
            ON r.competitor = latest.competitor
            AND r.location = latest.location
            AND COALESCE(r.car_model, r.car_category) = latest.model_key
            AND r.scraped_at = latest.max_scraped
            {outer_where}
            ORDER BY r.car_category, r.canonical_name, r.competitor
        """
        async with db.execute(query, inner_params + outer_params) as cursor:
            rows = await cursor.fetchall()
            return [dict(row) for row in rows]


async def get_rates_matrix(
    location: str = None,
    pickup_date: str = None,
    return_date: str = None,
    category: str = None,
) -> dict:
    """
    Return a cross-competitor matrix: canonical car model → {competitor: price}.
    """
    rates = await get_latest_rates(
        location=location,
        pickup_date=pickup_date,
        return_date=return_date,
        car_category=category,
    )

    competitors = ["Blue Car Rental", "Go Car Rental", "Lava Car Rental",
                   "Hertz Iceland", "Lotus Car Rental", "Avis Iceland", "Holdur"]

    # Build map: canonical_name → {competitor: rate_dict}
    matrix: dict[str, dict] = {}
    cat_map: dict[str, str] = {}

    for r in rates:
        canonical = r.get("canonical_name") or r.get("car_model") or r.get("car_category")
        if not canonical:
            continue
        if canonical not in matrix:
            matrix[canonical] = {}
            cat_map[canonical] = r.get("car_category", "")
        comp = r["competitor"]
        if comp not in matrix[canonical] or r["price_isk"] < matrix[canonical][comp]["price_isk"]:
            matrix[canonical][comp] = {
                "price_isk": r["price_isk"],
                "car_model": r.get("car_model"),
                "scraped_at": r.get("scraped_at"),
            }

    # Sort by category order then name
    def sort_key(name):
        cat = cat_map.get(name, "")
        cat_idx = CATEGORY_ORDER.index(cat) if cat in CATEGORY_ORDER else 99
        return (cat_idx, name)

    cars = []
    for canonical_name in sorted(matrix.keys(), key=sort_key):
        prices_by_comp = matrix[canonical_name]
        available_prices = [v["price_isk"] for v in prices_by_comp.values()]
        cars.append({
            "canonical_name": canonical_name,
            "category": cat_map.get(canonical_name, ""),
            "prices": {comp: prices_by_comp.get(comp) for comp in competitors},
            "min_price": min(available_prices) if available_prices else None,
            "max_price": max(available_prices) if available_prices else None,
            "cheapest_competitor": min(prices_by_comp, key=lambda c: prices_by_comp[c]["price_isk"]) if prices_by_comp else None,
            "available_at": len(prices_by_comp),
        })

    return {"cars": cars, "competitors": competitors}


async def get_car_catalog() -> list[dict]:
    """Return all canonical car names."""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT canonical_name, category FROM car_catalog ORDER BY category, canonical_name"
        ) as cursor:
            rows = await cursor.fetchall()
            return [dict(row) for row in rows]


async def get_car_mappings() -> list[dict]:
    """Return all competitor model name mappings."""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT id, competitor, competitor_model, canonical_name FROM car_mappings ORDER BY competitor"
        ) as cursor:
            rows = await cursor.fetchall()
            return [dict(row) for row in rows]


async def add_car_mapping(competitor: str, competitor_model: str, canonical_name: str):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT OR REPLACE INTO car_mappings (competitor, competitor_model, canonical_name) VALUES (?, ?, ?)",
            (competitor, competitor_model, canonical_name),
        )
        await db.commit()


async def delete_car_mapping(mapping_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("DELETE FROM car_mappings WHERE id = ?", (mapping_id,))
        await db.commit()


async def get_rates_history(location: str = None, car_category: str = None,
                             competitor: str = None, days: int = 30) -> list[dict]:
    """Return rate history for charting."""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row

        conditions = ["scraped_at >= datetime('now', ?  )"]
        params: list = [f"-{days} days"]

        if location:
            conditions.append("location = ?")
            params.append(location)
        if car_category:
            conditions.append("car_category = ?")
            params.append(car_category)
        if competitor:
            conditions.append("competitor = ?")
            params.append(competitor)

        where = "WHERE " + " AND ".join(conditions)
        query = f"""
            SELECT competitor, location, car_category, price_isk, scraped_at
            FROM rates
            {where}
            ORDER BY scraped_at ASC
        """
        async with db.execute(query, params) as cursor:
            rows = await cursor.fetchall()
            return [dict(row) for row in rows]


async def get_price_deltas(location: str = None, category: str = None) -> dict:
    """
    Compare average price per canonical model between the two most recent scrape dates.

    Returns:
        {
          "Toyota Yaris": {
            "direction": "down",          # "up" | "down" | "same"
            "delta_pct": -4.2,
            "delta_isk": -400,
            "curr_price": 9100,
            "prev_price": 9500,
            "date_curr": "2026-03-28",
            "date_prev": "2026-03-27",
          },
          ...
        }
    """
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row

        # Find the two most recent distinct scrape dates
        async with db.execute(
            "SELECT DISTINCT DATE(scraped_at) AS d FROM rates ORDER BY d DESC LIMIT 2"
        ) as cursor:
            dates = [row["d"] for row in await cursor.fetchall()]

        if len(dates) < 2:
            return {}  # Not enough history yet

        date_curr, date_prev = dates[0], dates[1]

        extra_conditions = []
        extra_params = []
        if location:
            extra_conditions.append("location = ?")
            extra_params.append(location)
        if category:
            extra_conditions.append("car_category = ?")
            extra_params.append(category)

        extra_where = (" AND " + " AND ".join(extra_conditions)) if extra_conditions else ""

        query_tpl = f"""
            SELECT
                COALESCE(canonical_name, car_model) AS model,
                car_category,
                ROUND(AVG(price_isk)) AS avg_price
            FROM rates
            WHERE DATE(scraped_at) = ?{extra_where}
            GROUP BY model, car_category
        """

        async with db.execute(query_tpl, [date_curr] + extra_params) as cursor:
            curr_rows = {row["model"]: int(row["avg_price"]) for row in await cursor.fetchall()}

        async with db.execute(query_tpl, [date_prev] + extra_params) as cursor:
            prev_rows = {row["model"]: int(row["avg_price"]) for row in await cursor.fetchall()}

    result = {}
    for model, curr_price in curr_rows.items():
        if model not in prev_rows:
            continue
        prev_price = prev_rows[model]
        delta_isk = curr_price - prev_price
        direction = "up" if delta_isk > 100 else ("down" if delta_isk < -100 else "same")
        delta_pct = round((delta_isk / prev_price) * 100, 1) if (prev_price and direction != "same") else 0.0
        result[model] = {
            "direction":  direction,
            "delta_pct":  delta_pct,
            "delta_isk":  delta_isk,
            "curr_price": curr_price,
            "prev_price": prev_price,
            "date_curr":  date_curr,
            "date_prev":  date_prev,
        }
    return result


async def get_rates_history_by_model(
    location: str = None,
    competitor: str = None,
    days: int = 30,
) -> dict:
    """
    Return price history grouped by category → canonical_name → list of daily data points.

    Returns:
        {
          "Economy": {
            "Toyota Yaris": [
              {"date": "2026-03-01", "avg_price": 9500, "min_price": 9000, "max_price": 10000, "competitor_count": 3},
              ...
            ],
            ...
          },
          ...
        }
    """
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row

        conditions = ["scraped_at >= datetime('now', ?)"]
        params: list = [f"-{days} days"]

        if location:
            conditions.append("location = ?")
            params.append(location)
        if competitor:
            conditions.append("competitor = ?")
            params.append(competitor)

        where = "WHERE " + " AND ".join(conditions)
        query = f"""
            SELECT
                car_category,
                COALESCE(canonical_name, car_model, car_category) AS model_key,
                DATE(scraped_at) AS date,
                ROUND(AVG(price_isk))  AS avg_price,
                MIN(price_isk)         AS min_price,
                MAX(price_isk)         AS max_price,
                COUNT(DISTINCT competitor) AS competitor_count
            FROM rates
            {where}
            GROUP BY car_category, model_key, DATE(scraped_at)
            ORDER BY car_category, model_key, date ASC
        """
        async with db.execute(query, params) as cursor:
            rows = await cursor.fetchall()

    result: dict = {}
    for row in rows:
        cat = row["car_category"] or "Unknown"
        model = row["model_key"] or "Unknown"
        if cat not in result:
            result[cat] = {}
        if model not in result[cat]:
            result[cat][model] = []
        result[cat][model].append({
            "date": row["date"],
            "avg_price": int(row["avg_price"]),
            "min_price": int(row["min_price"]),
            "max_price": int(row["max_price"]),
            "competitor_count": row["competitor_count"],
        })
    return result


async def get_model_competitor_coverage(
    location: str = None,
    days: int = 30,
) -> dict:
    """
    Return which competitors carry each canonical model in the given window.

    Returns:
        {
          "Economy": {
            "Toyota Yaris": ["Avis", "Blue Rental", "Hertz"],
            ...
          },
          ...
        }
    """
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row

        conditions = ["scraped_at >= datetime('now', ?)"]
        params: list = [f"-{days} days"]
        if location:
            conditions.append("location = ?")
            params.append(location)

        where = "WHERE " + " AND ".join(conditions)
        query = f"""
            SELECT
                car_category,
                COALESCE(canonical_name, car_model, car_category) AS model_key,
                competitor
            FROM rates
            {where}
            GROUP BY car_category, model_key, competitor
            ORDER BY car_category, model_key, competitor ASC
        """
        async with db.execute(query, params) as cursor:
            rows = await cursor.fetchall()

    result: dict = {}
    for row in rows:
        cat   = row["car_category"] or "Unknown"
        model = row["model_key"]    or "Unknown"
        comp  = row["competitor"]
        result.setdefault(cat, {}).setdefault(model, [])
        if comp not in result[cat][model]:
            result[cat][model].append(comp)
    return result


async def get_latest_rankings(keyword: str = None, location: str = None) -> list[dict]:
    """Return the most recent ranking per (keyword, location)."""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row

        conditions = []
        params = []
        if keyword:
            conditions.append("keyword = ?")
            params.append(keyword)
        if location:
            conditions.append("location = ?")
            params.append(location)

        where = ("WHERE " + " AND ".join(conditions)) if conditions else ""

        query = f"""
            SELECT r.*
            FROM rankings r
            INNER JOIN (
                SELECT keyword, location, MAX(created_at) AS max_created
                FROM rankings
                {where}
                GROUP BY keyword, location
            ) latest
            ON r.keyword = latest.keyword
            AND r.location = latest.location
            AND r.created_at = latest.max_created
            {where}
            ORDER BY r.keyword
        """
        async with db.execute(query, params + params) as cursor:
            rows = await cursor.fetchall()
            return [dict(row) for row in rows]


async def get_rankings_history(keyword: str = None, location: str = None, days: int = 30) -> list[dict]:
    """Return ranking history for charting."""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row

        conditions = ["created_at >= datetime('now', ?)"]
        params: list = [f"-{days} days"]

        if keyword:
            conditions.append("keyword = ?")
            params.append(keyword)
        if location:
            conditions.append("location = ?")
            params.append(location)

        where = "WHERE " + " AND ".join(conditions)
        query = f"""
            SELECT keyword, location, rank, url, serp_date, created_at
            FROM rankings
            {where}
            ORDER BY created_at ASC
        """
        async with db.execute(query, params) as cursor:
            rows = await cursor.fetchall()
            return [dict(row) for row in rows]


async def get_previous_rankings() -> dict:
    """
    Return the second-most-recent ranking per keyword for comparison (previous rank).
    Uses a window function to find the 2nd-newest row per keyword independently,
    so keywords checked at different times are handled correctly.
    Returns a dict: {keyword: rank}
    """
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        # ROW_NUMBER() OVER (PARTITION BY keyword ORDER BY created_at DESC) gives
        # rn=1 for the most recent check, rn=2 for the previous one.
        query = """
            SELECT keyword, rank
            FROM (
                SELECT keyword, rank,
                       ROW_NUMBER() OVER (PARTITION BY keyword ORDER BY created_at DESC) AS rn
                FROM rankings
            )
            WHERE rn = 2
        """
        async with db.execute(query) as cursor:
            rows = await cursor.fetchall()
        return {row["keyword"]: row["rank"] for row in rows}


async def delete_rankings_for_keywords(keywords: list[str]) -> int:
    """Delete all ranking records for the given keywords. Returns rows deleted."""
    if not keywords:
        return 0
    placeholders = ",".join("?" * len(keywords))
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            f"DELETE FROM rankings WHERE keyword IN ({placeholders})",
            keywords,
        )
        await db.commit()
        return cursor.rowcount


async def get_seasonal_cache(cache_key: str, max_age_hours: int = 6):
    """Return (data_dict, cached_at_iso) if cache exists and is fresh, else None."""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT data_json, cached_at FROM seasonal_cache WHERE cache_key = ?",
            (cache_key,),
        ) as cursor:
            row = await cursor.fetchone()
        if not row:
            return None
        cached_at = datetime.fromisoformat(row["cached_at"]).replace(tzinfo=timezone.utc)
        age_hours = (datetime.now(timezone.utc) - cached_at).total_seconds() / 3600
        if age_hours > max_age_hours:
            return None
        return json.loads(row["data_json"]), row["cached_at"]


async def set_seasonal_cache(cache_key: str, data: dict):
    """Upsert the seasonal cache for the given key."""
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            """
            INSERT INTO seasonal_cache (cache_key, cached_at, data_json)
            VALUES (?, ?, ?)
            ON CONFLICT(cache_key) DO UPDATE SET
                cached_at = excluded.cached_at,
                data_json = excluded.data_json
            """,
            (cache_key, datetime.now(timezone.utc).isoformat(), json.dumps(data)),
        )
        await db.commit()


async def clear_seasonal_cache() -> None:
    """Delete all seasonal response-cache entries so the next GET re-aggregates from DB."""
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("DELETE FROM seasonal_cache")
        await db.commit()


async def get_seasonal_anchor_history(
    pickup_date: str,
    return_date: str,
    location: str = "Keflavik Airport",
    competitor: str = None,
    category: str = None,
) -> list[dict]:
    """
    Return a time series for a specific anchor pickup month, showing how
    prices changed across multiple scrape dates.
    Groups by DATE(scraped_at), competitor, and car_category.
    """
    params: list = [location, pickup_date, return_date]
    extra = ""
    if competitor:
        extra += " AND competitor = ?"
        params.append(competitor)
    if category:
        extra += " AND car_category = ?"
        params.append(category)

    query = f"""
        SELECT
            DATE(scraped_at)                           AS scrape_date,
            competitor,
            car_category,
            ROUND(AVG(CAST(price_isk AS FLOAT) / 7))  AS avg_per_day,
            COUNT(*)                                   AS car_count
        FROM rates
        WHERE location = ? AND pickup_date = ? AND return_date = ?
        {extra}
        GROUP BY DATE(scraped_at), competitor, car_category
        ORDER BY scrape_date, competitor, car_category
    """
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(query, params) as cursor:
            rows = await cursor.fetchall()
            return [dict(row) for row in rows]


async def get_per_competitor_price_changes(
    location: str = None,
    category: str = None,
) -> dict:
    """
    Compare each competitor's avg price per canonical model between the two
    most recent scrape dates.

    Returns a dict keyed by "{competitor}::{location}::{canonical_name}":
        {
          "Blue Car Rental::Keflavik Airport::Toyota Yaris": {
            "direction": "down",
            "delta_pct": -4.2,
            "delta_isk": -400,
            "curr_price": 9100,
            "prev_price": 9500,
          },
          ...
        }
    """
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row

        # Find the two most recent distinct scrape dates
        async with db.execute(
            "SELECT DISTINCT DATE(scraped_at) AS d FROM rates ORDER BY d DESC LIMIT 2"
        ) as cursor:
            dates = [row["d"] for row in await cursor.fetchall()]

        if len(dates) < 2:
            return {}

        date_curr, date_prev = dates[0], dates[1]

        extra_conditions = []
        extra_params: list = []
        if location:
            extra_conditions.append("location = ?")
            extra_params.append(location)
        if category:
            extra_conditions.append("car_category = ?")
            extra_params.append(category)

        extra_where = (" AND " + " AND ".join(extra_conditions)) if extra_conditions else ""

        query_tpl = f"""
            SELECT
                competitor,
                location,
                COALESCE(canonical_name, car_model) AS model,
                ROUND(AVG(price_isk)) AS avg_price
            FROM rates
            WHERE DATE(scraped_at) = ?{extra_where}
            GROUP BY competitor, location, model
        """

        async with db.execute(query_tpl, [date_curr] + extra_params) as cursor:
            curr_rows = {
                f"{r['competitor']}::{r['location']}::{r['model']}": int(r["avg_price"])
                for r in await cursor.fetchall()
            }

        async with db.execute(query_tpl, [date_prev] + extra_params) as cursor:
            prev_rows = {
                f"{r['competitor']}::{r['location']}::{r['model']}": int(r["avg_price"])
                for r in await cursor.fetchall()
            }

    result = {}
    for key, curr_price in curr_rows.items():
        if key not in prev_rows:
            continue
        prev_price = prev_rows[key]
        delta_isk = curr_price - prev_price
        direction = "up" if delta_isk > 100 else ("down" if delta_isk < -100 else "same")
        delta_pct = round((delta_isk / prev_price) * 100, 1) if (prev_price and direction != "same") else 0.0
        result[key] = {
            "direction":  direction,
            "delta_pct":  delta_pct,
            "delta_isk":  delta_isk,
            "curr_price": curr_price,
            "prev_price": prev_price,
            "date_curr":  date_curr,
            "date_prev":  date_prev,
        }
    return result


async def log_scrape(
    location: str | None,
    total_rates: int,
    competitors: int,
    errors: list[str],
    duration_seconds: float,
    trigger: str = "manual",
) -> None:
    """Insert a row into scrape_log recording a completed scrape run."""
    errors_json = json.dumps(errors) if errors else None
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            """
            INSERT INTO scrape_log
                (scraped_at, location, total_rates, competitors, errors, duration_seconds, trigger)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                datetime.now(timezone.utc).isoformat(),
                location,
                total_rates,
                competitors,
                errors_json,
                round(duration_seconds, 2),
                trigger,
            ),
        )
        await db.commit()


async def get_scrape_log(limit: int = 20) -> list[dict]:
    """Return the most recent scrape log entries."""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            """
            SELECT id, scraped_at, location, total_rates, competitors,
                   errors, duration_seconds, trigger
            FROM scrape_log
            ORDER BY scraped_at DESC
            LIMIT ?
            """,
            (limit,),
        ) as cursor:
            rows = await cursor.fetchall()
    result = []
    for row in rows:
        d = dict(row)
        if d["errors"]:
            try:
                d["errors"] = json.loads(d["errors"])
            except (json.JSONDecodeError, TypeError):
                d["errors"] = [d["errors"]]
        else:
            d["errors"] = []
        result.append(d)
    return result


async def log_insurance_review(reviewer: str = "", notes: str = "", companies: list[str] | None = None) -> dict:
    """Record a manual insurance data verification event. Returns the new row."""
    companies_json = json.dumps(companies) if companies else None
    now = datetime.now(timezone.utc).isoformat()
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            """
            INSERT INTO insurance_reviews (reviewed_at, reviewer, notes, companies_verified)
            VALUES (?, ?, ?, ?)
            """,
            (now, reviewer or None, notes or None, companies_json),
        )
        await db.commit()
        row_id = cursor.lastrowid
    return {"id": row_id, "reviewed_at": now, "reviewer": reviewer, "notes": notes}


async def get_insurance_price_overrides() -> dict:
    """
    Return all stored price overrides as a nested dict:
        { company: { category: { price_isk, price_note, updated_at } } }
    """
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT company, category, price_isk, price_note, updated_at FROM insurance_price_overrides"
        ) as cursor:
            rows = await cursor.fetchall()
    result: dict = {}
    for row in rows:
        result.setdefault(row["company"], {})[row["category"]] = {
            "price_isk":   row["price_isk"],
            "price_note":  row["price_note"],
            "updated_at":  row["updated_at"],
        }
    return result


async def set_insurance_price_override(
    company: str,
    category: str,
    price_isk: int | None,
    price_note: str | None = None,
) -> dict:
    """Upsert a price override for one company+category cell. Returns the saved row."""
    now = datetime.now(timezone.utc).isoformat()
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            """
            INSERT INTO insurance_price_overrides (company, category, price_isk, price_note, updated_at)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(company, category) DO UPDATE SET
                price_isk  = excluded.price_isk,
                price_note = excluded.price_note,
                updated_at = excluded.updated_at
            """,
            (company, category, price_isk, price_note or None, now),
        )
        await db.commit()
    return {"company": company, "category": category, "price_isk": price_isk, "price_note": price_note, "updated_at": now}


async def get_model_horizon(canonical_name: str, location: str = None) -> dict:
    """
    Return all future scraped per-day prices for a specific canonical model,
    grouped by competitor. Covers both weekly horizon and monthly seasonal anchors.
    Returns {competitor: [{pickup_date, per_day, car_model}]} sorted by pickup_date.
    """
    from datetime import date as _date

    today = _date.today().isoformat()

    inner_conds = ["canonical_name = ?", "pickup_date >= ?"]
    inner_params: list = [canonical_name, today]
    if location:
        inner_conds.append("location = ?")
        inner_params.append(location)

    outer_conds = ["r.canonical_name = ?", "r.pickup_date >= ?"]
    outer_params: list = [canonical_name, today]
    if location:
        outer_conds.append("r.location = ?")
        outer_params.append(location)

    inner_where = "WHERE " + " AND ".join(inner_conds)
    outer_where = "WHERE " + " AND ".join(outer_conds)

    query = f"""
        SELECT r.competitor, r.pickup_date, r.return_date, r.price_isk, r.car_model
        FROM rates r
        INNER JOIN (
            SELECT competitor, location, pickup_date, MAX(scraped_at) AS max_scraped
            FROM rates
            {inner_where}
            GROUP BY competitor, location, pickup_date
        ) latest
        ON  r.competitor  = latest.competitor
        AND r.location    = latest.location
        AND r.pickup_date = latest.pickup_date
        AND r.scraped_at  = latest.max_scraped
        {outer_where}
        ORDER BY r.pickup_date, r.competitor
    """

    all_params = inner_params + outer_params

    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(query, all_params) as cursor:
            rows = await cursor.fetchall()

    series: dict = {}
    for row in rows:
        comp = row["competitor"]
        try:
            rental_days = (
                _date.fromisoformat(row["return_date"]) - _date.fromisoformat(row["pickup_date"])
            ).days
        except Exception:
            rental_days = 0
        per_day = round(row["price_isk"] / rental_days) if rental_days > 0 else row["price_isk"]
        series.setdefault(comp, []).append({
            "pickup_date": row["pickup_date"],
            "per_day":     per_day,
            "car_model":   row["car_model"],
        })

    return series


async def get_horizon_rates(
    location: str = None,
    category: str = None,
    weeks: int = 12,
) -> list[dict]:
    """
    For each of the next N weeks, return the latest avg per-day price by competitor and category.
    Anchor pickup dates: today + 7*w days, 7-night rental window.
    Returns list of {pickup_date, week, week_label, days_out, has_data,
                     competitors: {name: {cat: avg_per_day, _overall: avg}}}
    """
    from datetime import date, timedelta

    today = date.today()
    anchor_dates = [(today + timedelta(weeks=w)).isoformat() for w in range(1, weeks + 1)]
    placeholders = ",".join("?" * len(anchor_dates))

    inner_conds = [f"pickup_date IN ({placeholders})"]
    inner_params: list = list(anchor_dates)
    if location:
        inner_conds.append("location = ?")
        inner_params.append(location)

    outer_conds = [f"r.pickup_date IN ({placeholders})"]
    outer_params: list = list(anchor_dates)
    if location:
        outer_conds.append("r.location = ?")
        outer_params.append(location)
    if category:
        outer_conds.append("r.car_category = ?")
        outer_params.append(category)

    inner_where = "WHERE " + " AND ".join(inner_conds)
    outer_where = "WHERE " + " AND ".join(outer_conds)

    query = f"""
        SELECT r.competitor, r.pickup_date, r.return_date, r.car_category, r.price_isk
        FROM rates r
        INNER JOIN (
            SELECT competitor, location, pickup_date, MAX(scraped_at) AS max_scraped
            FROM rates
            {inner_where}
            GROUP BY competitor, location, pickup_date
        ) latest
        ON  r.competitor   = latest.competitor
        AND r.location     = latest.location
        AND r.pickup_date  = latest.pickup_date
        AND r.scraped_at   = latest.max_scraped
        {outer_where}
        ORDER BY r.pickup_date, r.competitor, r.car_category
    """

    all_params = inner_params + outer_params

    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(query, all_params) as cursor:
            rows = await cursor.fetchall()

    # Aggregate: {pickup_date: {competitor: {category: [per_day_prices]}}}
    # Use actual rental duration (return_date - pickup_date) so 3-night and 7-night
    # scrapes both produce correct per-day values.
    buckets: dict = {}
    for row in rows:
        pd_key     = row["pickup_date"]
        comp       = row["competitor"]
        cat        = row["car_category"]
        price      = row["price_isk"]
        try:
            from datetime import date as _date
            rental_days = (_date.fromisoformat(row["return_date"]) - _date.fromisoformat(pd_key)).days
        except Exception:
            rental_days = 0
        per_day = price / rental_days if rental_days > 0 else price / 7.0
        buckets.setdefault(pd_key, {}).setdefault(comp, {}).setdefault(cat, []).append(per_day)

    result = []
    for w, pickup in enumerate(anchor_dates, 1):
        pickup_d  = date.fromisoformat(pickup)
        week_data = buckets.get(pickup, {})

        avg_by_comp: dict = {}
        for comp, cats in week_data.items():
            avg_by_comp[comp] = {}
            all_prices: list = []
            for cat, per_day_prices in cats.items():
                avg_by_comp[comp][cat] = round(sum(per_day_prices) / len(per_day_prices))
                all_prices.extend(per_day_prices)
            avg_by_comp[comp]["_overall"] = round(sum(all_prices) / len(all_prices)) if all_prices else None

        result.append({
            "pickup_date": pickup,
            "week":        w,
            "week_label":  pickup_d.strftime("%d %b"),
            "days_out":    w * 7,
            "has_data":    bool(week_data),
            "competitors": avg_by_comp,
        })

    return result


async def get_insurance_reviews(limit: int = 10) -> list[dict]:
    """Return the most recent insurance review log entries."""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            """
            SELECT id, reviewed_at, reviewer, notes, companies_verified
            FROM insurance_reviews
            ORDER BY reviewed_at DESC
            LIMIT ?
            """,
            (limit,),
        ) as cursor:
            rows = await cursor.fetchall()
    result = []
    for row in rows:
        d = dict(row)
        if d["companies_verified"]:
            try:
                d["companies_verified"] = json.loads(d["companies_verified"])
            except (json.JSONDecodeError, TypeError):
                d["companies_verified"] = []
        else:
            d["companies_verified"] = []
        result.append(d)
    return result


async def get_price_timeline(
    days: int = 30,
    min_change_pct: float = 5.0,
    category: str = None,
    location: str = None,
    model: str = None,
) -> list[dict]:
    """
    Return all meaningful price changes across competitors within the lookback window.
    Compares consecutive scrape snapshots per competitor × canonical_name × location.
    Returns events sorted by scraped_at DESC.
    """
    from datetime import date as _date, timedelta
    cutoff = (_date.today() - timedelta(days=days)).isoformat()

    conds = ["scraped_at >= ?"]
    params: list = [cutoff]
    if category:
        conds.append("car_category = ?")
        params.append(category)
    if location:
        conds.append("location = ?")
        params.append(location)
    if model:
        conds.append("canonical_name = ?")
        params.append(model)

    where = "WHERE " + " AND ".join(conds)

    # Get per-competitor × canonical_name × scrape-day avg per-day price
    query = f"""
        SELECT
            competitor,
            location,
            canonical_name,
            car_category,
            DATE(scraped_at) AS scrape_date,
            MAX(scraped_at)  AS scraped_at,
            AVG(CAST(price_isk AS REAL) / (julianday(return_date) - julianday(pickup_date))) AS per_day
        FROM rates
        {where}
          AND julianday(return_date) > julianday(pickup_date)
        GROUP BY competitor, location, canonical_name, car_category, DATE(scraped_at)
        ORDER BY competitor, location, canonical_name, scrape_date ASC
    """

    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(query, params) as cur:
            rows = [dict(r) for r in await cur.fetchall()]

    if not rows:
        return []

    # Group into time series per competitor × model × location
    from collections import defaultdict
    series: dict = defaultdict(list)
    for r in rows:
        key = (r["competitor"], r["location"], r["canonical_name"], r["car_category"])
        series[key].append(r)

    events = []
    for key, snapshots in series.items():
        competitor, loc, model, cat = key
        for i in range(1, len(snapshots)):
            prev = snapshots[i - 1]
            curr = snapshots[i]
            if not prev["per_day"] or not curr["per_day"] or prev["per_day"] == 0:
                continue
            change_pct = (curr["per_day"] / prev["per_day"] - 1) * 100
            if abs(change_pct) < min_change_pct:
                continue
            events.append({
                "competitor":     competitor,
                "location":       loc,
                "canonical_name": model,
                "car_category":   cat,
                "scraped_at":     curr["scraped_at"],
                "prev_per_day":   round(prev["per_day"]),
                "curr_per_day":   round(curr["per_day"]),
                "change_pct":     round(change_pct, 1),
                "direction":      "up" if change_pct > 0 else "down",
            })

    # Sort by most recent first
    events.sort(key=lambda e: e["scraped_at"], reverse=True)
    return events


async def get_booking_window(
    pickup_date: str,
    category: str = None,
    location: str = None,
    model: str = None,
) -> dict:
    """
    For a specific future pickup date, return how per-day prices have changed
    across successive scrape snapshots — one entry per competitor per scrape date.
    Optionally filtered to a specific canonical model name.
    """
    conds = ["pickup_date = ?"]
    params: list = [pickup_date]
    if model:
        conds.append("canonical_name = ?")
        params.append(model)
    elif category:
        conds.append("car_category = ?")
        params.append(category)
    if location:
        conds.append("location = ?")
        params.append(location)

    where = "WHERE " + " AND ".join(conds)

    query = f"""
        SELECT
            competitor,
            DATE(scraped_at)  AS scrape_date,
            MAX(scraped_at)   AS scraped_at,
            AVG(CAST(price_isk AS REAL) / (julianday(return_date) - julianday(pickup_date))) AS per_day
        FROM rates
        {where}
          AND julianday(return_date) > julianday(pickup_date)
        GROUP BY competitor, DATE(scraped_at)
        ORDER BY competitor, scrape_date ASC
    """

    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(query, params) as cur:
            rows = [dict(r) for r in await cur.fetchall()]

    # Group by competitor → list of {scraped_at, per_day}
    series: dict = {}
    for r in rows:
        comp = r["competitor"]
        series.setdefault(comp, []).append({
            "scraped_at": r["scraped_at"],
            "per_day":    round(r["per_day"]) if r["per_day"] else None,
        })

    return {"pickup_date": pickup_date, "series": series}
