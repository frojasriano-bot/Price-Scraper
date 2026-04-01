"""
Database initialization and helpers for Blue Rental Intelligence.
Uses aiosqlite for async SQLite access.
"""

import aiosqlite
import json
from datetime import datetime
from pathlib import Path

DB_PATH = Path(__file__).parent / "blue_rental.db"

# Canonical car catalog: (canonical_name, category)
CAR_CATALOG = [
    # Economy
    ("Toyota Aygo", "Economy"),
    ("Toyota Yaris", "Economy"),
    ("Kia Rio", "Economy"),
    ("Hyundai i10", "Economy"),
    ("Hyundai i20", "Economy"),
    ("Suzuki Swift", "Economy"),
    ("VW Polo", "Economy"),
    ("Dacia Sandero", "Economy"),
    ("Dacia Jogger", "Economy"),
    ("Renault Zoe", "Economy"),
    # Compact
    ("VW Golf", "Compact"),
    ("Toyota Corolla", "Compact"),
    ("Hyundai i30", "Compact"),
    ("Kia Ceed", "Compact"),
    ("Kia Ceed Sportswagon", "Compact"),
    ("Kia Stonic", "Compact"),
    ("Kia XCeed", "Compact"),
    ("Skoda Octavia", "Compact"),
    ("Toyota Yaris Cross", "Compact"),
    ("Mazda CX-30", "Compact"),
    # SUV
    ("Dacia Duster", "SUV"),
    ("Dacia Bigster", "SUV"),
    ("Suzuki Vitara", "SUV"),
    ("Suzuki Jimny", "SUV"),
    ("Kia Sportage", "SUV"),
    ("Toyota RAV4", "SUV"),
    ("Hyundai Tucson", "SUV"),
    ("Nissan Qashqai", "SUV"),
    ("Jeep Renegade", "SUV"),
    ("Jeep Compass", "SUV"),
    ("Subaru Forester", "SUV"),
    ("Mitsubishi Eclipse Cross", "SUV"),
    ("Renault Koleos", "SUV"),
    ("Tesla Model Y", "SUV"),
    # 4x4
    ("Toyota Land Cruiser 150", "4x4"),
    ("Toyota Land Cruiser 250", "4x4"),
    ("Toyota Hilux", "4x4"),
    ("Toyota Highlander", "4x4"),
    ("Kia Sorento", "4x4"),
    ("Hyundai Santa Fe", "4x4"),
    ("Nissan X-Trail", "4x4"),
    ("Land Rover Defender", "4x4"),
    ("Land Rover Discovery", "4x4"),
    ("Land Rover Discovery Sport", "4x4"),
    ("Honda CR-V", "4x4"),
    ("Jeep Wrangler", "4x4"),
    ("Skoda Kodiaq", "4x4"),
    ("BMW X3", "4x4"),
    ("BMW X5", "4x4"),
    ("Mitsubishi Outlander", "4x4"),
    # Minivan
    ("VW Caravelle", "Minivan"),
    ("VW Caddy Maxi", "Minivan"),
    ("Ford Tourneo", "Minivan"),
    ("Toyota Proace", "Minivan"),
    ("Renault Trafic", "Minivan"),
    ("Mercedes Vito", "Minivan"),
    ("Mercedes Sprinter", "Minivan"),
]

# Maps (competitor, competitor_model_name) → canonical_name
CAR_NAME_MAPPINGS = [
    ("Lava Car Rental", "Dacia Sandero Stepway", "Dacia Sandero"),
    ("Lotus Car Rental", "Toyota Land Cruiser 150 4x4", "Toyota Land Cruiser 150"),
    ("Lotus Car Rental", "Toyota Land Cruiser 250 4x4", "Toyota Land Cruiser 250"),
    ("Holdur", "Toyota Landcruiser 150", "Toyota Land Cruiser 150"),
    ("Holdur", "Toyota Landcruiser 250", "Toyota Land Cruiser 250"),
    ("Holdur", "Mercedes Benz 350 GLE PHEV", "Mitsubishi Outlander"),
    ("Hertz Iceland", "Toyota Corolla Wagon", "Toyota Corolla"),
    ("Hertz Iceland", "Hyundai i30 Wagon", "Hyundai i30"),
    ("Blue Car Rental", "Toyota Land Cruiser 150 (7 seater)", "Toyota Land Cruiser 150"),
    ("Blue Car Rental", "Toyota Land Cruiser Adventure", "Toyota Land Cruiser 250"),
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

        await db.commit()

        # Seed car catalog
        for canonical_name, category in CAR_CATALOG:
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
            "locations": json.dumps([
                {"name": "Keflavik Airport", "address": "Keflavíkurflugvöllur, 235 Reykjanesbær, Iceland"},
                {"name": "Reykjavik", "address": "Reykjavík, Iceland"},
                {"name": "Akureyri", "address": "Akureyri, Iceland"},
                {"name": "Egilsstaðir", "address": "Egilsstaðir, Iceland"},
            ]),
        }
        for key, value in defaults.items():
            await db.execute(
                """
                INSERT OR IGNORE INTO config (key, value, updated_at)
                VALUES (?, ?, ?)
                """,
                (key, value, datetime.utcnow().isoformat()),
            )
        await db.commit()


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
            (key, value, datetime.utcnow().isoformat()),
        )
        await db.commit()


async def insert_rates(rates: list[dict]):
    """Bulk insert rate records."""
    async with aiosqlite.connect(DB_PATH) as db:
        await db.executemany(
            """
            INSERT INTO rates (competitor, location, pickup_date, return_date, car_category, car_model, canonical_name, price_isk, currency, scraped_at)
            VALUES (:competitor, :location, :pickup_date, :return_date, :car_category, :car_model, :canonical_name, :price_isk, :currency, :scraped_at)
            """,
            rates,
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
    Returns a dict: {keyword: rank}
    """
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        query = """
            SELECT keyword, rank, created_at
            FROM rankings
            WHERE created_at IN (
                SELECT DISTINCT created_at FROM rankings ORDER BY created_at DESC LIMIT 2
            )
            ORDER BY keyword, created_at DESC
        """
        async with db.execute(query) as cursor:
            rows = await cursor.fetchall()

        # Group by keyword, take second entry
        seen: dict[str, list] = {}
        for row in rows:
            kw = row["keyword"]
            if kw not in seen:
                seen[kw] = []
            seen[kw].append(row["rank"])

        previous = {}
        for kw, ranks in seen.items():
            if len(ranks) >= 2:
                previous[kw] = ranks[1]
        return previous


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
