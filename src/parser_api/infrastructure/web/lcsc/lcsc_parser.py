import asyncio
import logging
import random
import urllib.parse

from bs4 import BeautifulSoup
from camoufox.async_api import AsyncCamoufox

from parser_api.application.dto.enums.sites import Sites
from parser_api.application.dto.parsing.process import PostProcessingDTO, PriceDTO
from parser_api.application.port.parser.parser import IParserProvider
from parser_api.infrastructure.web.exeptions import ParserException

logger = logging.getLogger(__name__)


class LCSCParserProvider(IParserProvider):
    link = "https://www.lcsc.com/search"

    @property
    def source(self):
        return Sites.LCSC

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
        self._proxy = None
        self._lock = asyncio.Lock()

    async def __aenter__(self) -> LCSCParserProvider:
        if not self._browser:
            try:
                self._client = AsyncCamoufox(
                    persistent_context=False,
                    headless=self._headless,
                    geoip=True,
                    proxy=self._proxy,
                )
                self._browser = await self._client.__aenter__()
                logger.info("LCSC browser started successfully.")

            except Exception as e:
                logger.error(f"Failed to start LCSC browser: {e}")
                raise ParserException("Failed to start LCSC browser") from e

        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self._client:
            await self._client.__aexit__(exc_type, exc_val, exc_tb)
            self._browser = None
            logger.info("LCSC browser closed.")

    async def parse(
        self, part_number: str, min_delay: int = 2, max_delay: int = 5
    ) -> list[PostProcessingDTO]:
        if not self._browser:
            raise RuntimeError("Parser is not started.")

        page = await self._browser.new_page()

        url = f"{self.link}?q={urllib.parse.quote(part_number)}&s_z=n_{urllib.parse.quote(part_number)}"

        try:
            async with self._lock:
                logger.debug(f"Navigating to: {url}")
                await page.goto(url, wait_until="load", timeout=10000)

                try:
                    await page.wait_for_selector(
                        "div.productTableListWrap, div.otherSuppliersTableBox",
                        timeout=10000,
                    )
                except Exception:
                    logger.warning(f"Table did not appear for {part_number}")
                    return []

                # Expand "More" buttons to reveal all prices
                for table_sel in [
                    'div.productTableListWrap[data-spm="bg"]',
                    "div.otherSuppliersTableBox",
                ]:
                    try:
                        table = page.locator(table_sel)
                        if not await table.is_visible(timeout=5000):
                            continue

                        rows = table.locator("tr[data-v-2314c346]")
                        count = await rows.count()
                        for row_idx in range(min(count, 5)):
                            row = rows.nth(row_idx)
                            row_id = await row.get_attribute("id") or ""
                            if "flashSaleProduct" in row_id or "thirdPartyStock" in row_id:
                                continue

                            tds = row.locator("td")
                            if await tds.count() > 4:
                                price_td = tds.nth(4)
                                more_btns = price_td.locator('span.v2-a:has-text("More")')
                                btn_count = await more_btns.count()
                                for j in range(btn_count):
                                    btn = more_btns.nth(j)
                                    if await btn.is_visible(timeout=2000):
                                        try:
                                            await btn.click(timeout=4000)
                                            await page.wait_for_timeout(1000)
                                        except Exception:
                                            pass
                    except Exception as e:
                        logger.debug(f"Error expanding More in {table_sel}: {e}")

                await asyncio.sleep(1.5)
                html = await page.content()

            offers = await asyncio.to_thread(
                self._parse_html_internal, html, part_number
            )
            return offers

        except Exception as e:
            logger.error(f"Error parsing {part_number}: {e}")
            return []
        finally:
            await page.close()
            await asyncio.sleep(random.uniform(min_delay, max_delay))

    def _parse_html_internal(
        self, html: str, part_for_json: str
    ) -> list[PostProcessingDTO]:
        soup = BeautifulSoup(html, "html.parser")
        offers = []

        def parse_single_row(row):
            tds = row.find_all("td", recursive=False)
            if len(tds) < 8:
                return None

            # MPN
            mpn = ""
            mpn_a = tds[1].find(
                "a",
                attrs={
                    "class": lambda c: c
                    and "font-Bold-600" in str(c)
                    and "v2-a" in str(c)
                },
            )
            if mpn_a:
                mpn = mpn_a.get_text(strip=True)
            else:
                mpn_span = tds[1].find("span", class_="font-Bold-600")
                if mpn_span:
                    mpn = mpn_span.get_text(strip=True)

            # Manufacturer
            manuf_a = tds[2].find("a")
            manufacture = manuf_a.get_text(strip=True) if manuf_a else ""

            # Stock
            in_stock = 0
            for span in tds[3].find_all("span", class_="font-Bold-600"):
                txt = span.get_text(strip=True).replace(",", "").strip()
                if txt.isdigit():
                    in_stock = int(txt)
                    break

            # Lead time
            lead_time = "In Stock"
            if len(tds) > 3:
                avail_td = tds[3]
                for div in reversed(avail_td.find_all("div", class_="major--text")):
                    text = div.get_text(separator=" ", strip=True)
                    if "business days" in text.lower():
                        lead_time = text
                        break
                if lead_time == "In Stock":
                    avail_text = avail_td.get_text(separator=" ", strip=True)
                    if "business days" in avail_text.lower():
                        parts = avail_text.split()
                        for k in range(len(parts) - 2):
                            if (
                                "-" in parts[k]
                                and parts[k].replace("-", "").replace(",", "").isdigit()
                                and parts[k + 1].lower() == "business"
                                and parts[k + 2].lower() == "days"
                            ):
                                lead_time = f"{parts[k]} {parts[k + 1]} {parts[k + 2]}"
                                break
                lead_time = " ".join(lead_time.split()).strip()

            # Prices
            prices = []
            price_table = tds[4].find("table")
            if price_table:
                for tr in price_table.find_all("tr"):
                    qty_td = tr.find("td", class_="text-right")
                    if not qty_td:
                        continue
                    qty_text = (
                        qty_td.get_text(strip=True)
                        .replace("+", "")
                        .replace(",", "")
                        .strip()
                    )
                    for span in tr.find_all("span"):
                        if "$" in span.get_text(strip=True):
                            classes = " ".join(span.get("class", [])).lower()
                            if "text-decoration-line-through" not in classes:
                                try:
                                    qty = int(qty_text) if qty_text.isdigit() else 1
                                    price = float(
                                        span.get_text(strip=True)
                                        .replace("$", "")
                                        .replace(",", ".")
                                    )
                                    prices.append(PriceDTO(qty=qty, price=price))
                                except ValueError:
                                    pass
                                break

            # Description
            description = ""
            if len(tds) > 6:
                desc_td = tds[6]
                desc_div = desc_td.find("div", class_="ellipsis-6") or desc_td.find(
                    "div", attrs={"title": True}
                )
                description = (
                    (desc_div.get("title", "") or desc_div.get_text(strip=True))
                    if desc_div
                    else desc_td.get_text(strip=True)
                )

            # Package
            package = ""
            if len(tds) > 7:
                package_td = tds[7]
                package_span = package_td.find("span")
                package = (
                    package_span.get_text(strip=True)
                    if package_span
                    else package_td.get_text(strip=True)
                )

            # URL
            link = row.find("a", href=True)
            href = link["href"] if link else ""
            url = href if href.startswith("http") else f"https://www.lcsc.com{href}"
            if not url or "search" in url:
                url = f"https://www.lcsc.com/search?q={part_for_json}"

            return PostProcessingDTO(
                source=self.source,
                mpn=mpn,
                manufacture=manufacture,
                description=description,
                package=package,
                distributor="lcsc",
                in_stock=in_stock,
                lead_time=lead_time,
                currency="USD",
                prices=prices,
                condition="New & Original",
                country="China",
                url=url,
            )

        # Main table
        main_wrap = soup.find("div", class_="productTableListWrap")
        if main_wrap:
            rows = main_wrap.find_all("tr", {"data-v-2314c346": True})
            real_rows = [
                r
                for r in rows
                if "flashSaleProduct" not in r.get("id", "")  # type: ignore
                and "thirdPartyStock" not in r.get("id", "")  # type: ignore
            ]
            for row in real_rows[:5]:
                offer = parse_single_row(row)
                if offer:
                    offers.append(offer)

        # Other Suppliers
        other_wrap = soup.find("div", class_="otherSuppliersTableBox")
        if other_wrap:
            rows = other_wrap.find_all("tr", {"data-v-2314c346": True})
            for row in rows[:5]:
                offer = parse_single_row(row)
                if offer:
                    offers.append(offer)

        return offers
