from __future__ import annotations

import re
import time
from pathlib import Path

from knowledge_core.sources.egp.downloader import failed_download_result
from knowledge_core.sources.egp.models import (
    DEFAULT_EGP_ONLINE_URL,
    DownloadResult,
    EGPCategoryConfig,
    now_utc,
)


class BrowserEGPDownloader:
    """Playwright fallback for the EGP Online Bubble UI."""

    def __init__(
        self,
        *,
        base_url: str = DEFAULT_EGP_ONLINE_URL,
        headless: bool = True,
        timeout_ms: int = 120_000,
        slow_mo_ms: int = 0,
    ) -> None:
        self.base_url = base_url
        self.headless = headless
        self.timeout_ms = timeout_ms
        self.slow_mo_ms = slow_mo_ms

    def download_category(
        self,
        category: EGPCategoryConfig,
        destination: Path,
    ) -> DownloadResult:
        try:
            from playwright.sync_api import Error as PlaywrightError
            from playwright.sync_api import TimeoutError as PlaywrightTimeoutError
            from playwright.sync_api import sync_playwright
        except ImportError as exc:
            return failed_download_result(
                category=category,
                destination=destination,
                method=self.__class__.__name__,
                source_url=self.base_url,
                error=(
                    "Playwright is not installed. Install dependencies and run "
                    "`python -m playwright install chromium`."
                ),
            )

        try:
            with sync_playwright() as playwright:
                browser = playwright.chromium.launch(
                    headless=self.headless,
                    slow_mo=self.slow_mo_ms,
                )
                context = browser.new_context(accept_downloads=True)
                page = context.new_page()
                page.set_default_timeout(self.timeout_ms)
                page.goto(self.base_url, wait_until="domcontentloaded")
                page.wait_for_load_state("networkidle")

                self._select_all_levels(page)
                initial_results_summary = self._results_summary(page)
                filters_selected = self._configure_filters(page, category)
                self._click_search(page)
                self._wait_for_search_results(
                    page,
                    category,
                    initial_results_summary=initial_results_summary,
                    filters_selected=filters_selected,
                )

                with page.expect_download() as download_info:
                    self._click_download(page)
                download = download_info.value
                destination.parent.mkdir(parents=True, exist_ok=True)
                download.save_as(str(destination))
                bytes_written = destination.stat().st_size
                if bytes_written == 0:
                    raise RuntimeError("downloaded XLSX file is empty")

                source_url = page.url
                context.close()
                browser.close()
        except (PlaywrightError, PlaywrightTimeoutError, RuntimeError) as exc:
            return failed_download_result(
                category=category,
                destination=destination,
                method=self.__class__.__name__,
                source_url=self.base_url,
                error=f"Browser EGP download failed for {category.id}: {exc}",
            )

        return DownloadResult(
            category_id=category.id,
            destination=destination,
            status="downloaded",
            method=self.__class__.__name__,
            source_url=source_url,
            retrieved_at=now_utc(),
            bytes_written=bytes_written,
        )

    def _select_all_levels(self, page: object) -> None:
        all_pattern = re.compile(r"^All$", re.IGNORECASE)
        for locator in (
            page.get_by_role("button", name=all_pattern),
            page.get_by_role("radio", name=all_pattern),
            page.get_by_label(all_pattern),
            page.get_by_text(all_pattern, exact=True),
        ):
            try:
                locator.click(timeout=2_000)
                return
            except Exception:
                continue

    def _configure_filters(self, page: object, category: EGPCategoryConfig) -> bool:
        selected_filter = False
        if category.expected_super_category or category.expected_sub_category:
            self._open_filters(page)

        if category.expected_super_category:
            selected_filter = self._select_option_by_label(
                page,
                category.expected_super_category,
                timeout_ms=5_000,
            ) or selected_filter

        subcategory_label = category.expected_sub_category or category.query
        if subcategory_label:
            selected_filter = self._select_option_by_label(
                page,
                subcategory_label,
                timeout_ms=10_000 if category.expected_sub_category else 2_000,
            ) or selected_filter

        if not selected_filter or (
            category.expected_sub_category is None
            and subcategory_label == category.query
        ):
            self._fill_search_query(page, category.query)
        return selected_filter

    def _open_filters(self, page: object) -> None:
        try:
            page.get_by_role(
                "button",
                name=re.compile("Remove filters", re.IGNORECASE),
            ).wait_for(
                state="visible",
                timeout=1_000,
            )
            self._wait_for_filter_options(page)
            return
        except Exception:
            pass

        for locator in (
            page.get_by_role("button", name=re.compile("Add Filters", re.IGNORECASE)),
            page.get_by_text(re.compile("Add Filters", re.IGNORECASE), exact=True),
        ):
            try:
                locator.click(timeout=5_000)
                self._wait_for_filter_options(page)
                return
            except Exception:
                continue
        raise RuntimeError("could not open EGP Online filters")

    def _wait_for_filter_options(self, page: object) -> None:
        page.wait_for_function(
            """
            () => Array.from(document.querySelectorAll('select')).some(
                select => (select.options || []).length > 2
            )
            """,
            timeout=5_000,
        )

    def _select_option_by_label(
        self,
        page: object,
        label: str,
        *,
        timeout_ms: int,
    ) -> bool:
        wanted = _option_key(label)
        deadline = time.monotonic() + (timeout_ms / 1000)
        while True:
            try:
                select_count = page.locator("select").count()
            except Exception:
                return False
            for index in range(select_count):
                select = page.locator("select").nth(index)
                try:
                    options = select.evaluate(
                        """
                        (select) => Array.from(select.options || [])
                            .map(option => option.text.trim())
                            .filter(Boolean)
                        """,
                    )
                except Exception:
                    continue
                actual_label = _matching_option_label(options, wanted)
                if actual_label is None:
                    continue
                try:
                    select.select_option(label=actual_label, timeout=5_000)
                    return True
                except Exception:
                    continue
            if time.monotonic() >= deadline:
                return False
            page.wait_for_timeout(250)
        return False

    def _fill_search_query(self, page: object, query: str) -> None:
        search_pattern = re.compile(r"search", re.IGNORECASE)
        candidates = (
            page.get_by_label(search_pattern),
            page.get_by_placeholder(search_pattern),
            page.locator("input[type='search']").first,
            page.locator("input[type='text']").first,
            page.locator("textarea").first,
        )
        for locator in candidates:
            try:
                locator.fill(query, timeout=5_000)
                return
            except Exception:
                continue
        raise RuntimeError("could not find a search input on EGP Online")

    def _click_search(self, page: object) -> None:
        search_pattern = re.compile(r"^Search$", re.IGNORECASE)
        for locator in (
            page.get_by_role("button", name=search_pattern),
            page.get_by_text(search_pattern, exact=True),
        ):
            try:
                locator.click(timeout=5_000)
                return
            except Exception:
                continue
        raise RuntimeError("could not find the Search control on EGP Online")

    def _wait_for_search_results(
        self,
        page: object,
        category: EGPCategoryConfig,
        *,
        initial_results_summary: str | None,
        filters_selected: bool,
    ) -> None:
        if filters_selected and initial_results_summary:
            self._wait_for_results_summary_change(
                page,
                initial_results_summary,
                timeout_ms=self.timeout_ms,
                required=True,
                category_id=category.id,
            )
        else:
            try:
                page.get_by_text("Searching...", exact=True).wait_for(
                    state="hidden",
                    timeout=self.timeout_ms,
                )
            except Exception:
                raise RuntimeError(
                    f"EGP Online did not finish searching for {category.id}"
                ) from None

        expected_label = category.expected_sub_category or category.expected_super_category
        if expected_label:
            try:
                body_text = page.locator("body").inner_text(timeout=5_000)
            except Exception:
                body_text = ""
            if expected_label.lower() not in body_text.lower():
                raise RuntimeError(
                    "EGP Online search completed, but the expected source "
                    f"category text was not visible for {category.id}: "
                    f"{expected_label!r}"
                )

    def _click_download(self, page: object) -> None:
        download_pattern = re.compile(r"Download XLSX", re.IGNORECASE)
        for locator in (
            page.get_by_role("button", name=download_pattern),
            page.get_by_text(download_pattern),
        ):
            try:
                locator.click(timeout=5_000)
                return
            except Exception:
                continue
        raise RuntimeError("could not find the Download XLSX control on EGP Online")

    def _results_summary(self, page: object) -> str | None:
        try:
            text = page.locator("body").inner_text(timeout=5_000)
        except Exception:
            return None
        index = text.find("Results:")
        if index < 0:
            return None
        return text[index : index + 120]

    def _wait_for_results_summary_change(
        self,
        page: object,
        initial_results_summary: str,
        *,
        timeout_ms: int,
        required: bool,
        category_id: str | None = None,
    ) -> bool:
        if self._results_summary(page) != initial_results_summary:
            return True
        try:
            page.wait_for_function(
                """
                initial => {
                    const text = document.body.innerText || '';
                    const idx = text.indexOf('Results:');
                    if (idx < 0) {
                        return false;
                    }
                    const summary = text.slice(idx, idx + 120);
                    return summary !== initial;
                }
                """,
                arg=initial_results_summary,
                timeout=timeout_ms,
            )
            return True
        except Exception:
            if not required:
                return False
            label = f" for filtered category {category_id}" if category_id else ""
            raise RuntimeError(
                f"EGP Online search completed, but the result summary did not change{label}"
            ) from None


def _matching_option_label(options: list[str], wanted: str) -> str | None:
    for option in options:
        if _option_key(option) == wanted:
            return option
    return None


def _option_key(value: str) -> str:
    return " ".join(re.sub(r"[()]", " ", value).strip().lower().split())
