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


class DigiKeyParserProvider(IParserProvider):
    link = "https://www.digikey.com/en/products"

    @property
    def source(self):
        return Sites.DIGIKEY

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

    async def __aenter__(self) -> DigiKeyParserProvider:
        if not self._browser:
            try:
                self._client = AsyncCamoufox(
                    persistent_context=False,
                    headless=self._headless,
                    geoip=True,
                    proxy=self._proxy,
                )
                self._browser = await self._client.__aenter__()
                logger.info("DigiKey browser started successfully.")

            except Exception as e:
                logger.error(f"Failed to start DigiKey browser: {e}")
                raise ParserException("Failed to start DigiKey browser") from e

        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self._client:
            await self._client.__aexit__(exc_type, exc_val, exc_tb)
            self._browser = None
            logger.info("DigiKey browser closed.")

    async def parse(
        self, part_number: str, min_delay: int = 2, max_delay: int = 5
    ) -> list[PostProcessingDTO]:
        if not self._browser:
            raise RuntimeError("Parser is not started.")

        page = await self._browser.new_page()

        query = urllib.parse.quote(part_number)
        search_url = f"{self.link}?keywords={query}"

        try:
            async with self._lock:
                logger.debug(f"Navigating to: {search_url}")
                await page.goto(search_url, wait_until="load", timeout=20000)

                try:
                    await page.wait_for_selector(
                        'div[data-testid="card"], table tbody tr', timeout=15000
                    )
                except Exception:
                    logger.warning(
                        f"Neither categories nor table loaded for {part_number}"
                    )
                    return []

                category_cards = page.locator('div[data-testid="card"] a')
                if await category_cards.count() > 0:
                    first_category = category_cards.first
                    category_url = await first_category.get_attribute("href")
                    if category_url:
                        full_url = (
                            category_url
                            if category_url.startswith("http")
                            else f"https://www.digikey.com{category_url}"
                        )
                        logger.debug(f"Navigating to category: {full_url}")
                        await page.goto(full_url, wait_until="load", timeout=20000)
                        await page.wait_for_selector("table tbody tr", timeout=10000)
                    else:
                        logger.warning("Failed to get category link")

                await asyncio.sleep(1)
                html = await page.content()

            offers = await asyncio.to_thread(self._parse_html_internal, html)
            return offers

        except Exception as e:
            logger.error(f"Error parsing {part_number}: {e}")
            return []
        finally:
            await page.close()
            await asyncio.sleep(random.uniform(min_delay, max_delay))

    def _parse_html_internal(self, html: str) -> list[PostProcessingDTO]:
        soup = BeautifulSoup(html, "html.parser")
        rows = soup.select("tr.tss-css-hi2p03-tr")
        if not rows:
            rows = soup.select('tr[data-testid*="product-row"]')

        offers = []
        for row in rows[:10]:
            try:
                # MPN
                mpn_tag = row.select_one(
                    'a[data-testid="data-table-product-number"]'
                ) or row.select_one(
                    "a.tss-css-41s5xv-productColExpandedPartNumber-anchor"
                )
                mpn = mpn_tag.get_text(strip=True) if mpn_tag else ""

                # URL
                url = ""
                if mpn_tag and mpn_tag.has_attr("href"):
                    href = mpn_tag["href"]
                    url = (
                        href
                        if href.startswith("http")  # type: ignore
                        else f"https://www.digikey.com{href}"
                    )

                # Manufacturer
                mfr_tag = row.select_one(
                    'a[data-testid="data-table-mfr-link"], a.tss-css-1hy0h66-productColExpandedManufacturer'
                )
                manufacture = mfr_tag.get_text(strip=True) if mfr_tag else ""

                # Description
                desc_tag = row.select_one(
                    "div.tss-css-7dp38y-productColExpandedDescription"
                )
                description = desc_tag.get_text(strip=True) if desc_tag else ""

                # Package (Supplier Device Package)
                package = ""
                package_cell = row.select_one(
                    'td[data-testid="draggable-cell-1291"] div'
                )
                if package_cell:
                    package = package_cell.get_text(strip=True)

                # Stock
                in_stock = 0
                stock_cell = row.select_one(
                    'td[data-testid="draggable-cell--102"] strong'
                )
                if stock_cell:
                    stock_text = stock_cell.get_text(strip=True).replace(",", "")
                    if stock_text.isdigit():
                        in_stock = int(stock_text)

                # Prices
                prices = []
                price_cells = row.select(
                    'td[data-testid="draggable-cell--101"] div[data-testid="HoverCell"]'
                )
                for pc in price_cells:
                    qty_price_tag = pc.select_one('div[data-testid="qty-price"]')
                    if not qty_price_tag:
                        continue
                    text = qty_price_tag.get_text(strip=True)
                    match = re.match(r"([\d,]+)\s*:\s*\$([\d.]+)", text)
                    if match:
                        qty_str = match.group(1).replace(",", "")
                        price_str = match.group(2)
                        try:
                            qty = int(qty_str)
                            price = float(price_str)
                            prices.append(PriceDTO(qty=qty, price=price))
                        except ValueError:
                            continue

                offers.append(
                    PostProcessingDTO(
                        source=self.source,
                        mpn=mpn,
                        manufacture=manufacture,
                        description=description,
                        package=package,
                        distributor="digikey",
                        in_stock=in_stock,
                        lead_time="In Stock",
                        currency="USD",
                        prices=prices,
                        condition="New & Original",
                        country="USA",
                        url=str(url),
                    )
                )
            except Exception as e:
                logger.warning(f"Error parsing DigiKey row: {e}")
                continue

        return offers
