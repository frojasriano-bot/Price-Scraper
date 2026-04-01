# Development

## Environment variables

See `.env.example`:
- `SERPAPI_KEY` (optional)
- `APP_HOST` (default `0.0.0.0`)
- `APP_PORT` (default `8000`)
- `DEBUG` (default `true`)

## Running locally

```bash
python main.py
```

Open `http://localhost:8000`.

## Common API testing commands

Health:

```bash
curl http://localhost:8000/api/health
```

Rates (latest):

```bash
curl "http://localhost:8000/api/rates"
```

Trigger scrape:

```bash
curl -X POST "http://localhost:8000/api/rates/scrape"
```

SEO keywords:

```bash
curl "http://localhost:8000/api/seo/keywords"
```

## Extending the project

### Add a new scraper

1. Create a new file in `scrapers/` (for example `mycompetitor.py`)
2. Implement a new scraper class inheriting from `BaseScraper`
3. Add the scraper to `scrapers/__init__.py`:
   - import the class
   - add it to `ALL_SCRAPERS`

### Update mock data

If you’re not ready for live scraping, update:
- the scraper’s `FLEET` price ranges

Mock pricing uses:
- deterministic competitor personality based on `competitor_name`
- seasonal multipliers based on pickup month

## Code quality

The repo currently has no automated tests configured.

For PRs, validate:
- server starts cleanly (`python main.py`)
- `/api/health` returns `ok`
- the dashboard loads `http://localhost:8000/`

