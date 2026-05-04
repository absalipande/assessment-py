# CER REGDOCS Assessment

## Summary

The requested work is a scraping and document-harvesting pipeline for Canada Energy Regulator
REGDOCS. The scraper should run monthly, search the Advanced Search page for a date range and a
fixed list of CERA application types, download all matching documents, convert rare HTML-only
records to PDF, and upload the output to Google Drive.

The current blocker is the source website, not the scraper scaffold. From this environment, the
provided Advanced Search URL times out before returning a response.

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

The dry run was attempted with:

```bash
PYTHONPATH=. .venv/bin/python -m cer_scraper run \
  --from-date 2026-02-01 \
  --to-date 2026-03-01 \
  --limit-types 1 \
  --dry-run
```

Result:

```text
Page.goto: net::ERR_CONNECTION_TIMED_OUT
https://apps.cer-rec.gc.ca/REGDOCS/Search/Advanced
```

A direct HTTP check also timed out:

```bash
curl -I --max-time 30 https://apps.cer-rec.gc.ca/REGDOCS/Search/Advanced
```

This indicates the endpoint is currently unreachable or too slow from the test environment. The
failure happens before DOM inspection or selector interaction, so it is not currently a selector bug.

## Next Implementation Steps

1. Re-run the endpoint probe when REGDOCS is reachable:

   ```bash
   PYTHONPATH=. .venv/bin/python -m cer_scraper probe --timeout 30
   ```

2. If the page loads, inspect the live DOM and replace placeholder selectors in
   `cer_scraper/search.py`.

3. Check the browser Network tab for backend search requests. If REGDOCS exposes a stable search
   endpoint, use direct HTTP calls instead of UI automation.

4. Run a narrow proof of concept:

   ```bash
   PYTHONPATH=. .venv/bin/python -m cer_scraper run \
     --from-date 2026-02-01 \
     --to-date 2026-03-01 \
     --limit-types 1 \
     --dry-run
   ```

5. Enable downloads after discovery succeeds.

6. Wire Google Drive upload last, after local download and manifest generation are reliable.

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
REGDOCS Advanced Search link timed out during testing, and that final selector/API work depends on
the source site becoming reachable.
