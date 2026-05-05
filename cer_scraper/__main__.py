from __future__ import annotations

import argparse
import asyncio
import time

import httpx

from cer_scraper.config import load_application_types, load_settings
from cer_scraper.downloader import DocumentDownloader
from cer_scraper.drive import DriveUploader
from cer_scraper.manifest import Manifest
from cer_scraper.models import SearchJob
from cer_scraper.search import RegdocsSearcher


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="CER REGDOCS monthly document scraper")
    subparsers = parser.add_subparsers(dest="command", required=True)

    run = subparsers.add_parser("run", help="Run a monthly REGDOCS scrape")
    run.add_argument("--from-date", required=True, help="Start date, e.g. 2026-02-01")
    run.add_argument("--to-date", required=True, help="End date, e.g. 2026-03-01")
    run.add_argument("--limit-types", type=int, default=None, help="Limit application types for testing")
    run.add_argument("--dry-run", action="store_true", help="Discover records but do not download/upload")

    probe = subparsers.add_parser("probe", help="Check whether the REGDOCS Advanced Search URL responds")
    probe.add_argument("--timeout", type=float, default=30.0, help="HTTP timeout in seconds")

    return parser


async def probe(args: argparse.Namespace) -> None:
    settings = load_settings()
    started = time.monotonic()

    try:
        async with httpx.AsyncClient(follow_redirects=True, timeout=args.timeout) as client:
            response = await client.head(settings.base_url)
            elapsed = time.monotonic() - started
            print(f"ok status={response.status_code} elapsed={elapsed:.1f}s url={settings.base_url}")
    except Exception as exc:  # noqa: BLE001
        elapsed = time.monotonic() - started
        print(f"failed elapsed={elapsed:.1f}s url={settings.base_url} error={exc}")
        raise SystemExit(1) from exc


async def run(args: argparse.Namespace) -> None:
    settings = load_settings()
    application_types = load_application_types(settings.application_types_path)
    if args.limit_types:
        application_types = application_types[: args.limit_types]

    jobs = [
        SearchJob(
            from_date=args.from_date,
            to_date=args.to_date,
            application_type=application_type,
        )
        for application_type in application_types
    ]

    manifest = Manifest(settings.manifest_path)
    seen = manifest.seen_document_urls()
    searcher = RegdocsSearcher(settings.base_url, settings.headless, settings.timeout_ms)
    downloader = DocumentDownloader(settings.output_dir, settings.timeout_ms / 1000)
    uploader = DriveUploader(settings.drive_folder_id)
    discovered_count = 0
    skipped_count = 0

    async for record in searcher.discover(jobs):
        discovered_count += 1
        if record.document_url in seen:
            record.status = "skipped"
            manifest.append(record)
            skipped_count += 1
            continue

        if not args.dry_run:
            async with searcher_browser(settings) as browser:
                record = await downloader.download(record, browser)
                if record.status == "downloaded" and record.local_file:
                    drive_link = await uploader.upload(record.local_file)
                    if drive_link:
                        record.drive_link = drive_link
                        record.status = "uploaded"

        manifest.append(record)
        seen.add(record.document_url)
        print(f"{record.status}: {record.document_url}")

    if discovered_count == 0:
        print("No document records discovered for this date range/application type selection.")
    else:
        print(f"Done. discovered={discovered_count} skipped={skipped_count}")


class searcher_browser:
    def __init__(self, settings) -> None:  # noqa: ANN001
        self.settings = settings
        self.playwright = None
        self.browser = None

    async def __aenter__(self):  # noqa: ANN204
        from playwright.async_api import async_playwright

        self.playwright = await async_playwright().start()
        self.browser = await self.playwright.chromium.launch(headless=self.settings.headless)
        return self.browser

    async def __aexit__(self, exc_type, exc, traceback) -> None:  # noqa: ANN001
        if self.browser:
            await self.browser.close()
        if self.playwright:
            await self.playwright.stop()


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()

    if args.command == "run":
        asyncio.run(run(args))
    elif args.command == "probe":
        asyncio.run(probe(args))


if __name__ == "__main__":
    main()
