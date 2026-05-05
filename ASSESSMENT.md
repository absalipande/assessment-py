# CER REGDOCS Assessment

## Summary

The requested work is a scraping and document-harvesting pipeline for Canada Energy Regulator
REGDOCS. The scraper should run monthly, search the Advanced Search page for a date range and a
fixed list of CERA application types, download all matching documents, convert rare HTML-only
records to PDF, and upload the output to Google Drive.

The source website was initially timing out, but a later probe succeeded. The browser-rendered page
remains slow and intermittent, so the scraper now uses REGDOCS' direct HTTP results endpoint for
discovery instead of relying on Playwright UI rendering.

URL:

```text
https://apps.cer-rec.gc.ca/REGDOCS/Search/Advanced
```

## Recommended Stack

- Python for orchestration
- Playwright for JS-heavy REGDOCS search pages and HTML-to-PDF conversion
- httpx for direct PDF downloads and endpoint probes
- BeautifulSoup/lxml for HTML parsing
- Google Drive API or rclone for upload
- JSONL manifest for checkpointing, audit logs, and resumability

## What Was Built

The scaffold in this repository includes:

- `config/application_types.txt`: the full application-type list from the scope document
- `cer_scraper/search.py`: Playwright-based discovery layer with retries
- `cer_scraper/downloader.py`: PDF downloader plus HTML-to-PDF fallback
- `cer_scraper/manifest.py`: JSONL checkpoint/audit manifest
- `cer_scraper/drive.py`: Drive upload interface placeholder
- `cer_scraper/__main__.py`: CLI entry point with `run` and `probe` commands

## Live-Site Test Result

The endpoint probe was rerun after the initial timeout and returned successfully:

```text
ok status=200 elapsed=14.9s url=https://apps.cer-rec.gc.ca/REGDOCS/Search/Advanced
```

The dry run was attempted with:

```bash
PYTHONPATH=. .venv/bin/python -m cer_scraper run \
  --from-date 2026-02-01 \
  --to-date 2026-03-01 \
  --limit-types 1 \
  --dry-run
```

Initial result:

```text
Page.goto: net::ERR_CONNECTION_TIMED_OUT
https://apps.cer-rec.gc.ca/REGDOCS/Search/Advanced
```

A direct HTTP check also timed out:

```bash
curl -I --max-time 30 https://apps.cer-rec.gc.ca/REGDOCS/Search/Advanced
```

After the site became reachable, the scraper reached the form but hit hidden/slow-rendered UI fields.
REGDOCS exposes a direct AJAX results endpoint:

```text
/REGDOCS/Search/SearchAdvancedResults?sd=<from-date>&ed=<to-date>&rds=<application-type-id>
```

The scraper was updated to fetch the Advanced Search page once, map application-type labels to their
REGDOCS filter IDs, then query this results endpoint directly. This avoids most Playwright page-load
fragility. Playwright remains useful later for HTML-to-PDF conversion.

The one-type dry run now completes successfully through the direct HTTP path. For the first
application type in the requested date range, REGDOCS returned no document records:

```text
No document records discovered for this date range/application type selection.
```

## Next Implementation Steps

1. Re-run the endpoint probe:

   ```bash
   PYTHONPATH=. .venv/bin/python -m cer_scraper probe --timeout 30
   ```

2. Re-run the one-application-type dry run:

   ```bash
   PYTHONPATH=. .venv/bin/python -m cer_scraper run \
     --from-date 2026-02-01 \
     --to-date 2026-03-01 \
     --limit-types 1 \
     --dry-run
   ```

3. Expand the dry run beyond one application type once the one-type proof stays stable.

4. Enable downloads after discovery succeeds.

5. Wire Google Drive upload last, after local download and manifest generation are reliable.

## Risk Handling

The production scraper should assume REGDOCS will be slow or intermittently unavailable. It should:

- Split work by month and application type
- Use long but bounded timeouts
- Retry with backoff
- Persist manifest entries after each discovered/downloaded/uploaded document
- Resume from the manifest instead of starting over
- Record failed links for manual review

## Recommendation

Proceed with the assessment as a resilient scraping pipeline. Note explicitly that the provided
REGDOCS Advanced Search link is slow and intermittent, and that final selector/API work should be
validated against the live site when it responds consistently.
