# Contributing

Contributions are welcome.

## How to contribute

1. Fork the repository (or create a branch in your workspace).
2. Make your changes.
3. Open a pull request with:
   - a clear summary of the change
   - how it was tested (manual steps are fine)

## Suggested workflow for scrapers

When adding live scraping:

- Keep `get_mock_rates()` working as a fallback.
- Fail fast (raise exceptions) when selectors break so the system falls back to mock data.
- Return only dicts that match the schema used by `database.py` / `rates` table.

