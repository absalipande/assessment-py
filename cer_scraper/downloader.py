from __future__ import annotations

from pathlib import Path

import httpx
from playwright.async_api import Browser, TimeoutError as PlaywrightTimeoutError

from cer_scraper.models import DocumentRecord
from cer_scraper.retry import with_retries
from cer_scraper.utils import filename_from_url


class DocumentDownloader:
    def __init__(self, output_dir: Path, timeout_seconds: float = 90.0) -> None:
        self.output_dir = output_dir
        self.timeout_seconds = timeout_seconds
        self.output_dir.mkdir(parents=True, exist_ok=True)

    async def download(self, record: DocumentRecord, browser: Browser) -> DocumentRecord:
        filename = filename_from_url(record.document_url)
        target = self.output_dir / filename
        record.filename = filename
        record.local_path = str(target)

        try:
            if record.document_url.lower().split("?", 1)[0].endswith(".pdf"):
                await self._download_pdf(record.document_url, target)
            else:
                await self._save_html_as_pdf(record.document_url, target, browser)
            record.status = "downloaded"
        except Exception as exc:  # noqa: BLE001
            record.status = "failed"
            record.error = str(exc)

        return record

    async def _download_pdf(self, url: str, target: Path) -> None:
        async def fetch() -> None:
            async with httpx.AsyncClient(
                follow_redirects=True,
                timeout=httpx.Timeout(self.timeout_seconds),
                headers={"User-Agent": "cer-regdocs-monthly-review/0.1"},
            ) as client:
                response = await client.get(url)
                response.raise_for_status()
                target.write_bytes(response.content)

        await with_retries(fetch)

    async def _save_html_as_pdf(self, url: str, target: Path, browser: Browser) -> None:
        page = await browser.new_page()
        try:
            await page.goto(url, wait_until="domcontentloaded", timeout=int(self.timeout_seconds * 1000))
            await page.pdf(path=str(target), format="Letter", print_background=True)
        except PlaywrightTimeoutError as exc:
            raise RuntimeError(f"Timed out saving HTML page as PDF: {url}") from exc
        finally:
            await page.close()
