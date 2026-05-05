from __future__ import annotations

import asyncio
import time
from typing import AsyncIterator, Dict, List, Optional
from urllib.parse import urlencode, urljoin

import httpx
from bs4 import BeautifulSoup
from playwright.async_api import Page, TimeoutError as PlaywrightTimeoutError, async_playwright

from cer_scraper.models import DocumentRecord, SearchJob
from cer_scraper.retry import with_retries


class RegdocsSearcher:
    def __init__(
        self,
        base_url: str,
        headless: bool,
        timeout_ms: int,
        http_timeout_seconds: Optional[float] = None,
        application_type_values: Optional[Dict[str, str]] = None,
    ) -> None:
        self.base_url = base_url
        self.headless = headless
        self.timeout_ms = timeout_ms
        self.http_timeout_seconds = http_timeout_seconds or min(timeout_ms / 1000, 30.0)
        self.application_type_values = application_type_values or {}

    async def discover(self, jobs: List[SearchJob]) -> AsyncIterator[DocumentRecord]:
        async for record in self._discover_with_http(jobs):
            yield record

    async def _discover_with_http(self, jobs: List[SearchJob]) -> AsyncIterator[DocumentRecord]:
        yielded_urls = set()
        async with httpx.AsyncClient(
            follow_redirects=True,
            timeout=httpx.Timeout(self.http_timeout_seconds),
            headers={"User-Agent": "cer-regdocs-monthly-review/0.1"},
        ) as client:
            application_type_values = self.application_type_values
            if application_type_values:
                print("Using cached REGDOCS application-type filter IDs", flush=True)
            else:
                print(f"Loading REGDOCS filter metadata: {self.base_url}", flush=True)
                advanced_html = await self._fetch_text(client, self.base_url)
                application_type_values = self._parse_application_type_values(advanced_html)

            for index, job in enumerate(jobs, start=1):
                print(
                    f"[{index}/{len(jobs)}] Searching {job.application_type} "
                    f"({job.from_date} to {job.to_date})",
                    flush=True,
                )
                filter_value = application_type_values.get(job.application_type)
                if not filter_value:
                    raise ValueError(f"Application type not found on REGDOCS page: {job.application_type}")

                params = {"sd": job.from_date, "ed": job.to_date, "rds": filter_value}
                result_url = urljoin(
                    self.base_url,
                    f"/REGDOCS/Search/SearchAdvancedResults?{urlencode(params)}",
                )

                visited_urls = set()
                page_number = 1
                while result_url:
                    if result_url in visited_urls:
                        print(f"  stopping pagination loop at {result_url}", flush=True)
                        break
                    visited_urls.add(result_url)
                    print(f"  fetching results page {page_number}: {result_url}", flush=True)
                    started = time.monotonic()
                    try:
                        html = await self._fetch_text(client, result_url)
                    except Exception as exc:  # noqa: BLE001
                        print(f"  failed: {result_url} ({exc})", flush=True)
                        break
                    records = self._parse_result_page(html, result_url, job)
                    elapsed = time.monotonic() - started
                    if not records:
                        print(f"  no records ({elapsed:.1f}s)", flush=True)
                    else:
                        print(f"  records: {len(records)} ({elapsed:.1f}s)", flush=True)
                    for record in records:
                        if record.document_url in yielded_urls:
                            continue
                        yielded_urls.add(record.document_url)
                        yield record
                    result_url = self._next_results_page(html, result_url)
                    page_number += 1

    async def _fetch_text(self, client: httpx.AsyncClient, url: str) -> str:
        async def fetch() -> str:
            response = await client.get(url)
            response.raise_for_status()
            return response.text

        async def bounded_fetch() -> str:
            return await asyncio.wait_for(fetch(), timeout=self.http_timeout_seconds)

        return await with_retries(bounded_fetch, attempts=2, base_delay_seconds=3.0)

    def _parse_application_type_values(self, html: str) -> dict:
        soup = BeautifulSoup(html, "html.parser")
        values = {}
        for option in soup.select("#selectFilter1 option[value]"):
            label = option.get_text(" ", strip=True)
            value = option.get("value")
            if label and value:
                values[label] = value
        return values

    def _next_results_page(self, html: str, current_url: str) -> str:
        soup = BeautifulSoup(html, "html.parser")
        next_anchor = soup.find("a", string=lambda text: text and text.strip().lower() == "next")
        if not next_anchor:
            next_anchor = soup.select_one('a[rel="next"], a[href*="page="], a[href*="Page="]')
        if not next_anchor or not next_anchor.get("href"):
            return ""
        return urljoin(current_url, next_anchor["href"])

    async def discover_with_browser(self, jobs: List[SearchJob]) -> AsyncIterator[DocumentRecord]:
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
            lambda: page.goto(self.base_url, wait_until="commit", timeout=self.timeout_ms)
        )
        await page.locator("#selectDateSelector").wait_for(state="attached", timeout=self.timeout_ms)

    async def _fill_date_range(self, page: Page, from_date: str, to_date: str) -> None:
        await page.locator("#selectDateSelector").evaluate(
            "(element) => { element.value = '-1'; element.dispatchEvent(new Event('change', { bubbles: true })); }"
        )
        await page.locator("#advanced-date-range").evaluate(
            "element => element.classList.remove('hide')"
        )
        await page.locator("#StartDate").evaluate(
            "(element, value) => { element.value = value; element.dispatchEvent(new Event('change', { bubbles: true })); }",
            from_date,
        )
        await page.locator("#EndDate").evaluate(
            "(element, value) => { element.value = value; element.dispatchEvent(new Event('change', { bubbles: true })); }",
            to_date,
        )

    async def _select_application_type(self, page: Page, application_type: str) -> None:
        await page.locator("#selectFilter1").wait_for(state="attached", timeout=self.timeout_ms)
        selected_filter_value = await page.locator("#selectFilter1").evaluate(
            """(select, label) => {
                const option = Array.from(select.options).find((item) => item.text.trim() === label);
                if (!option) {
                    throw new Error(`Application type not found: ${label}`);
                }
                return option.value;
            }""",
            application_type,
        )
        await page.locator("form").evaluate(
            """(form, value) => {
                for (const existing of form.querySelectorAll('input[name="SelectedFilters"]')) {
                    if (existing.value === value) {
                        return;
                    }
                }

                const input = document.createElement('input');
                input.type = 'hidden';
                input.name = 'SelectedFilters';
                input.value = value;
                form.appendChild(input);
            }""",
            selected_filter_value,
        )

    async def _submit_search(self, page: Page) -> None:
        async def submit() -> None:
            await page.locator("#btnSearch2").click()
            await page.wait_for_load_state("domcontentloaded", timeout=self.timeout_ms)

        await with_retries(submit)

    def _parse_result_page(
        self,
        html: str,
        result_url: str,
        job: SearchJob,
    ) -> List[DocumentRecord]:
        soup = BeautifulSoup(html, "html.parser")
        anchors = soup.select(
            'a[href*=".pdf"], '
            'a[href*="/REGDOCS/Item/View"], '
            'a[href*="/REGDOCS/File/Download"], '
            'a[href*="/REGDOCS/File/View"]'
        )
        records: List[DocumentRecord] = []

        for anchor in anchors:
            href = anchor.get("href")
            if not href:
                continue
            document_url = href if href.startswith("http") else f"https://apps.cer-rec.gc.ca{href}"
            if not self._looks_like_document_url(document_url):
                continue
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

    def _looks_like_document_url(self, url: str) -> bool:
        lowered = url.lower()
        return any(
            marker in lowered
            for marker in (
                ".pdf",
                "/regdocs/item/view",
                "/regdocs/file/download",
                "/regdocs/file/view",
            )
        )
