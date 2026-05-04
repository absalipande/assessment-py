from __future__ import annotations

from typing import AsyncIterator, List

from bs4 import BeautifulSoup
from playwright.async_api import Page, TimeoutError as PlaywrightTimeoutError, async_playwright

from cer_scraper.models import DocumentRecord, SearchJob
from cer_scraper.retry import with_retries


class RegdocsSearcher:
    def __init__(self, base_url: str, headless: bool, timeout_ms: int) -> None:
        self.base_url = base_url
        self.headless = headless
        self.timeout_ms = timeout_ms

    async def discover(self, jobs: List[SearchJob]) -> AsyncIterator[DocumentRecord]:
        async with async_playwright() as playwright:
            browser = await playwright.chromium.launch(headless=self.headless)
            try:
                page = await browser.new_page()
                page.set_default_timeout(self.timeout_ms)

                for job in jobs:
                    async for record in self._discover_for_job(page, job):
                        yield record
            finally:
                await browser.close()

    async def _discover_for_job(
        self,
        page: Page,
        job: SearchJob,
    ) -> AsyncIterator[DocumentRecord]:
        await self._open_advanced_search(page)

        # TODO: Replace these selectors after inspecting the live REGDOCS DOM.
        # The names are intentionally centralized so the first browser-debug pass has one obvious place
        # to tighten the implementation.
        await self._fill_date_range(page, job.from_date, job.to_date)
        await self._select_application_type(page, job.application_type)
        await self._submit_search(page)

        while True:
            html = await page.content()
            for record in self._parse_result_page(html, page.url, job):
                yield record

            next_link = page.get_by_role("link", name="Next")
            if await next_link.count() == 0:
                break
            try:
                await next_link.first.click()
                await page.wait_for_load_state("domcontentloaded", timeout=self.timeout_ms)
            except PlaywrightTimeoutError:
                break

    async def _open_advanced_search(self, page: Page) -> None:
        await with_retries(
            lambda: page.goto(self.base_url, wait_until="domcontentloaded", timeout=self.timeout_ms)
        )

    async def _fill_date_range(self, page: Page, from_date: str, to_date: str) -> None:
        await page.get_by_label("From").fill(from_date)
        await page.get_by_label("To").fill(to_date)

    async def _select_application_type(self, page: Page, application_type: str) -> None:
        await page.get_by_label("Application Type").select_option(label=application_type)
        await page.get_by_role("button", name="+").click()

    async def _submit_search(self, page: Page) -> None:
        async def submit() -> None:
            await page.get_by_role("button", name="Search").click()
            await page.wait_for_load_state("domcontentloaded", timeout=self.timeout_ms)

        await with_retries(submit)

    def _parse_result_page(
        self,
        html: str,
        result_url: str,
        job: SearchJob,
    ) -> List[DocumentRecord]:
        soup = BeautifulSoup(html, "html.parser")
        anchors = soup.select('a[href*=".pdf"], a[href*="/REGDOCS/"]')
        records: List[DocumentRecord] = []

        for anchor in anchors:
            href = anchor.get("href")
            if not href:
                continue
            document_url = href if href.startswith("http") else f"https://apps.cer-rec.gc.ca{href}"
            records.append(
                DocumentRecord(
                    application_type=job.application_type,
                    date_range=f"{job.from_date}_to_{job.to_date}",
                    result_url=result_url,
                    document_url=document_url,
                    title=anchor.get_text(" ", strip=True) or None,
                )
            )

        return records
