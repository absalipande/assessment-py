# CER REGDOCS Scraper

Python + Playwright scaffold for the monthly Canada Energy Regulator REGDOCS review.

The first production run should target:

- Date range: `2026-02-01` to `2026-03-01`
- Application types: see `config/application_types.txt`
- Scope: download all documents in the filtered results and upload them to Google Drive

## Setup

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e ".[drive]"
python -m playwright install chromium
cp .env.example .env
```

## Dry Run

```bash
PYTHONPATH=. python -m cer_scraper run --from-date 2026-02-01 --to-date 2026-03-01 --limit-types 1 --dry-run
```

## Real Run

```bash
PYTHONPATH=. python -m cer_scraper run --from-date 2026-02-01 --to-date 2026-03-01
```

## Site Probe

```bash
PYTHONPATH=. python -m cer_scraper probe --timeout 30
```

Downloaded files are written to `data/downloads/`. The manifest is written to
`data/manifests/manifest.jsonl`, one JSON record per discovered document.

## Notes

- Playwright is used for the REGDOCS UI because the page is slow and likely dynamic.
- Direct PDF downloads use `httpx` once document URLs are discovered.
- HTML-only results are saved to PDF through Playwright.
- Google Drive upload is intentionally isolated in `cer_scraper/drive.py` so credentials and folder
  mapping can be added without touching the scraping logic.
