from __future__ import annotations
import asyncio

from pathlib import Path

import httpx
import requests
from playwright.async_api import Browser, TimeoutError as PlaywrightTimeoutError

from cer_scraper.models import DocumentRecord
from cer_scraper.retry import with_retries
from cer_scraper.utils import filename_from_url


DOWNLOAD_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept": "application/pdf,text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
    "Referer": "https://apps.cer-rec.gc.ca/REGDOCS/",
}


class DocumentDownloader:
    def __init__(self, output_dir: Path, timeout_seconds: float = 90.0) -> None:
        self.output_dir = output_dir
        self.timeout_seconds = timeout_seconds
        self.output_dir.mkdir(parents=True, exist_ok=True)

    async def download(self, record: DocumentRecord, browser: Browser) -> DocumentRecord:
        filename = filename_from_url(record.document_url)
        target = self.output_dir / filename

        if target.suffix.lower() != ".pdf":
            target = target.with_suffix(".pdf")
            filename = target.name

        record.filename = filename
        record.local_path = str(target)

        try:
            downloaded_as_pdf = await self._try_download_pdf(record.document_url, target)

            if not downloaded_as_pdf:
                await self._save_html_as_pdf(record.document_url, target, browser)

            record.status = "downloaded"
        except Exception as exc:  # noqa: BLE001
            record.status = "failed"
            record.error = str(exc)
            print(f"download failed: {record.document_url} -> {record.error}")

        return record

    async def _try_download_pdf(self, url: str, target: Path) -> bool:
        async def fetch() -> bool:
            return await asyncio.to_thread(self._try_download_pdf_sync, url, target)

        return await with_retries(fetch)

    def _try_download_pdf_sync(self, url: str, target: Path) -> bool:
        response = requests.get(
            url,
            timeout=(min(15.0, self.timeout_seconds), self.timeout_seconds),
            allow_redirects=True,
            stream=True,
            headers=DOWNLOAD_HEADERS,
        )
        response.raise_for_status()

        content_type = response.headers.get("content-type", "").lower()
        chunks: list[bytes] = []

        for chunk in response.iter_content(chunk_size=1024 * 256):
            if chunk:
                chunks.append(chunk)

        content = b"".join(chunks)
        is_pdf = "application/pdf" in content_type or content.startswith(b"%PDF")

        if not is_pdf:
            return False

        target.write_bytes(content)
        return True

    async def _save_html_as_pdf(self, url: str, target: Path, browser: Browser) -> None:
        page = await browser.new_page()
        try:
            await page.set_extra_http_headers(DOWNLOAD_HEADERS)
            await page.goto(url, wait_until="domcontentloaded", timeout=int(self.timeout_seconds * 1000))
            await page.pdf(path=str(target), format="Letter", print_background=True)
        except PlaywrightTimeoutError as exc:
            raise RuntimeError(f"Timed out saving HTML page as PDF: {url}") from exc
        finally:
            await page.close()
