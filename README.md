# CER REGDOCS Scraper

Python scraper for the monthly Canada Energy Regulator REGDOCS review.

The first production run should target:

- Date range: `2026-02-01` to `2026-03-01`
- Application types: see `config/application_types.txt`
- Scope: download all documents in the filtered results and upload them to Google Drive

## Setup

```bash
python -m venv .venv
source .venv/bin/activate
pip install ".[drive]"
python -m playwright install chromium
cp .env.example .env
```

The scraper uses cached REGDOCS application-type IDs from
`config/application_type_ids.csv` so it can avoid the slow Advanced Search UI during discovery.

## Site Probe

```bash
PYTHONPATH=. python -m cer_scraper probe --timeout 30
```

## Dry Run

Run one application type:

```bash
PYTHONPATH=. python -m cer_scraper run \
  --from-date 2026-02-01 \
  --to-date 2026-03-01 \
  --limit-types 1 \
  --http-timeout 10 \
  --dry-run
```

Run all scoped application types:

```bash
PYTHONPATH=. python -m cer_scraper run \
  --from-date 2026-02-01 \
  --to-date 2026-03-01 \
  --http-timeout 10 \
  --dry-run
```

Validated dry-run result for `2026-02-01` to `2026-03-01`:

```text
Done. discovered=153 skipped=0
```

## Local Download Run

After the dry run is stable, run without `--dry-run`:

```bash
PYTHONPATH=. python -m cer_scraper run \
  --from-date 2026-02-01 \
  --to-date 2026-03-01 \
  --http-timeout 10
```

Downloaded files are written to `data/downloads/`. The manifest is written to
`data/manifests/manifest.jsonl`, one JSON record per discovered document.

## Notes

- Discovery uses REGDOCS' direct results endpoint:
  `/REGDOCS/Search/SearchAdvancedResults?sd=<from-date>&ed=<to-date>&rds=<application-type-id>`.
- Direct PDF downloads use `httpx`.
- HTML-only results can be saved to PDF through Playwright.
- Google Drive upload is intentionally isolated in `cer_scraper/drive.py` so credentials and folder
  mapping can be added without touching the scraping logic.
