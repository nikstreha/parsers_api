import asyncio
import logging
import random
import re
import urllib.parse

from bs4 import BeautifulSoup
from camoufox.async_api import AsyncCamoufox

from parser_api.application.dto.enums.sites import Sites
from parser_api.application.dto.parsing.process import PostProcessingDTO, PriceDTO
from parser_api.application.port.parser.parser import IParserProvider
from parser_api.infrastructure.web.exeptions import ParserException

logger = logging.getLogger(__name__)


class MouserParserProvider(IParserProvider):
    link = "https://www.mouser.com"

    @property
    def source(self):
        return Sites.MOUSER

    def __init__(
        self,
        user_data_dir: str,
        headless: bool = False,
        proxy: dict | None = None,
    ):
        self._user_data_dir = user_data_dir
        self._headless = headless
        self._client: AsyncCamoufox | None = None
        self._browser = None
        self._proxy = proxy
        self._lock = asyncio.Lock()

    async def __aenter__(self) -> MouserParserProvider:
        if not self._browser:
            try:
                self._client = AsyncCamoufox(
                    persistent_context=False,
                    headless=self._headless,
                    geoip=True,
                    proxy=self._proxy,
                )
                self._browser = await self._client.__aenter__()
                logger.info("Mouser browser started successfully.")

            except Exception as e:
                logger.error(f"Failed to start Mouser browser: {e}")
                raise ParserException("Failed to start Mouser browser") from e
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self._client:
            await self._client.__aexit__(exc_type, exc_val, exc_tb)
            self._browser = None
            logger.info("Mouser browser closed.")

    async def parse(
        self, part_number: str, min_delay: int = 2, max_delay: int = 5
    ) -> list[PostProcessingDTO]:
        if not self._browser:
            raise RuntimeError("Parser is not started.")

        page = await self._browser.new_page()

        url = f"{self.link}/c/?q={urllib.parse.quote(part_number)}"

        try:
            async with self._lock:
                # First navigate to the homepage to avoid cookie/redirect issues
                await page.goto(self.link, wait_until="networkidle")

                logger.debug(f"Navigating to: {url}")
                await page.goto(url, wait_until="networkidle", timeout=10000)

                try:
                    await page.wait_for_selector("table tbody tr", timeout=10000)
                except Exception:
                    logger.warning(f"Table did not load for {part_number}")
                    return []

                html = await page.content()

            offers = await asyncio.to_thread(self._parse_html_internal, html)
            return offers

        except Exception as e:
            logger.error(f"Error parsing {part_number}: {e}")
            # Retry once
            try:
                async with self._lock:
                    await asyncio.sleep(3)
                    await page.goto(url, wait_until="networkidle", timeout=10000)
                    await page.wait_for_selector("table tbody tr", timeout=10000)
                    html = await page.content()

                offers = await asyncio.to_thread(self._parse_html_internal, html)
                return offers
            except Exception as e2:
                logger.error(f"Retry failed: {e2}")
                return []
        finally:
            await page.close()
            await asyncio.sleep(random.uniform(min_delay, max_delay))

    def _parse_html_internal(self, html: str) -> list[PostProcessingDTO]:
        soup = BeautifulSoup(html, "html.parser")
        offers = []

        rows = soup.select("tr[data-partnumber]")
        if not rows:
            rows = soup.select("table tbody tr")

        for row in rows[:10]:
            try:
                mpn_tag = row.select_one("td.part-column a.text-nowrap")
                mpn = mpn_tag.get_text(strip=True) if mpn_tag else ""

                mfr_tag = row.select_one("td.mfr-column a, td.mfr-column span")
                manufacture = mfr_tag.get_text(strip=True) if mfr_tag else ""

                desc_tag = row.select_one("td.desc-column span")
                description = desc_tag.get_text(strip=True) if desc_tag else ""

                package = ""

                avail_td = row.select_one(
                    "td.availability-column, td.text-center.hide-xsmall"
                )
                in_stock = 0
                lead_time = "In Stock"
                if avail_td:
                    stock_span = avail_td.find("span", class_="available-amount")
                    if stock_span:
                        stock_text = (
                            stock_span.get_text(strip=True)
                            .replace(".", "")
                            .replace(",", "")
                        )
                        if stock_text.isdigit():
                            in_stock = int(stock_text)

                prices = []
                pricing_td = row.select_one(
                    "td.pricing-column, td.text-center.hide-xsmall table.search-pricing-table"
                )
                if pricing_td and pricing_td.name == "td":
                    price_table = pricing_td.find(
                        "table", class_="search-pricing-table"
                    )
                else:
                    price_table = pricing_td

                currency = "EUR"

                if price_table:
                    price_rows = price_table.find_all("tr", attrs={"data-qty": True})
                    for pr in price_rows:
                        if pr.get("data-qty") == "-1":
                            continue
                        qty_th = pr.find("th", class_="PriceBreakQuantity")
                        if not qty_th:
                            continue
                        qty_text = (
                            qty_th.get_text(strip=True)
                            .replace(".", "")
                            .replace(",", "")
                        )
                        try:
                            qty = int(qty_text) if qty_text.isdigit() else 1
                        except ValueError:
                            continue

                        price_td = pr.find("td", class_="PriceBreakPrice")
                        if not price_td:
                            continue
                        price_span = price_td.find("span", class_="text-nowrap")
                        if not price_span:
                            continue

                        price_str = price_span.get_text(strip=True)
                        if "€" in price_str:
                            currency = "EUR"
                        elif "$" in price_str:
                            currency = "USD"

                        price_clean = (
                            re.sub(r"[^\d,.-]", "", price_str)
                            .replace(",", ".")
                            .replace(" ", "")
                        )
                        try:
                            price = float(price_clean)
                            prices.append(PriceDTO(qty=qty, price=price))
                        except ValueError:
                            continue

                link = row.select_one('td.part-column a[id^="lnkMfrPartNumber"]')
                url = ""
                if link and link.has_attr("href"):
                    href = link["href"]
                    url = (
                        href
                        if href.startswith("http")  # type: ignore
                        else f"https://www.mouser.com{href}"
                    )

                offers.append(
                    PostProcessingDTO(
                        source=self.source,
                        mpn=mpn,
                        manufacture=manufacture,
                        description=description,
                        package=package,
                        distributor="mouser",
                        in_stock=in_stock,
                        lead_time=lead_time,
                        currency=currency,
                        prices=prices,
                        condition="New & Original",
                        country="China",
                        url=str(url),
                    )
                )
            except Exception as e:
                logger.warning(f"Error parsing Mouser row: {e}")
                continue

        return offers
