# Deployment

## Production recommendation

For production, run `uvicorn` without reload:

```bash
uvicorn main:app --host 0.0.0.0 --port 8000 --log-level info
```

## Environment

At minimum, configure:
- `APP_HOST`
- `APP_PORT`
- (optional) `SERPAPI_KEY` for live SEO checks

## Persistent storage

The app stores data in a local SQLite file:
- `blue_rental.db`

For deployments, ensure the container/VM has a persistent volume mapped to the repo directory (or change `DB_PATH` in `database.py`).

## Security notes

- The app enables permissive CORS for local development (`allow_origins=["*"]`).
- If exposing publicly, tighten CORS origins and review authentication needs for the scrape/SEO endpoints.

