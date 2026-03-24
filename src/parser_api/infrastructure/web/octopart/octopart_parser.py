import asyncio
import logging
import random
import urllib.parse

from bs4 import BeautifulSoup
from camoufox.async_api import AsyncCamoufox
from playwright.async_api import Page

from parser_api.application.dto.enums.sites import Sites
from parser_api.application.dto.parsing.process import PostProcessingDTO, PriceDTO
from parser_api.application.port.parser.parser import IParserProvider
from parser_api.infrastructure.web.exeptions import ParserException

logger = logging.getLogger(__name__)


class OctopartParserProvider(IParserProvider):
    link = "https://octopart.com/search"

    @property
    def source(self):
        return Sites.OCTOPART

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

    async def __aenter__(self) -> OctopartParserProvider:
        if not self._browser:
            try:
                self._client = AsyncCamoufox(
                    user_data_dir=self._user_data_dir,
                    persistent_context=True,
                    headless=self._headless,
                    geoip=True,
                    proxy=self._proxy,
                )
                logger.info("Octopart browser started successfully.")

            except Exception as e:
                logger.error(f"Failed to start Octopart browser: {e}")
                raise ParserException("Failed to start Octopart browser") from e
            self._browser = await self._client.__aenter__()

        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self._client:
            await self._client.__aexit__(exc_type, exc_val, exc_tb)
            self._browser = None
            logger.info("Octopart browser closed.")

    async def parse(
        self, part_number: str, min_delay: int = 2, max_delay: int = 5
    ) -> list[PostProcessingDTO]:
        if not self._browser:
            raise RuntimeError("Parser is not started.")

        page = await self._browser.new_page()

        params = {"q": part_number, "currency": "USD", "specs": "0"}
        search_url = f"{self.link}?{urllib.parse.urlencode(params)}"

        try:
            async with self._lock:
                logger.debug(f"Navigating to: {search_url}")
                await page.goto(search_url, wait_until="load", timeout=10000)

                solved = False
                try:
                    await page.wait_for_selector(
                        'tbody[data-testid="offer-table-body"]', timeout=10000
                    )
                except Exception:
                    html_lower = (await page.content()).lower()
                    if any(
                        x in html_lower
                        for x in ["px-captcha", "one more step", "security check"]
                    ):
                        solved = await self._solve_px_challenge(page)
                        if solved:
                            try:  # noqa: SIM105
                                await page.wait_for_selector(
                                    'tbody[data-testid="offer-table-body"]', timeout=10000
                                )
                            except Exception:
                                pass

                html = await page.content()

            offers = await asyncio.to_thread(self._parse_html_internal, html)
            return offers

        except Exception as e:
            logger.error(f"Error parsing {part_number}: {e}")
            return []
        finally:
            await asyncio.sleep(random.uniform(min_delay, max_delay))

    async def _solve_px_challenge(self, page: Page) -> bool:
        logger.info("Trying to solve PX challenge")

        for attempt in range(3):
            try:
                await page.wait_for_selector(
                    "#px-captcha", state="visible", timeout=15000
                )
                captcha_div = page.locator("#px-captcha")
                await captcha_div.scroll_into_view_if_needed()
                await asyncio.sleep(2.3)

                box = await captcha_div.bounding_box()
                if not box or box["width"] < 50:
                    box = {"x": 520, "y": 360, "width": 340, "height": 120}

                center_x = box["x"] + box["width"] / 2 + random.uniform(-30, 30)
                center_y = box["y"] + box["height"] / 2 + random.uniform(-20, 20)

                await page.mouse.move(center_x, center_y, steps=random.randint(12, 20))
                await asyncio.sleep(random.uniform(0.8, 1.5))

                await page.mouse.down()
                hold_seconds = random.uniform(6.2, 11.8)
                logger.info(
                    "Holding for %s sec (attempt %s/3)",
                    hold_seconds,
                    attempt + 1,
                )

                for _ in range(5):
                    await page.mouse.move(
                        center_x + random.uniform(-12, 12),
                        center_y + random.uniform(-6, 6),
                        steps=3,
                    )
                    await asyncio.sleep(hold_seconds / 6)

                await page.mouse.up()

                for _ in range(3):
                    await page.mouse.move(
                        center_x + random.randint(-80, 80),
                        center_y + random.randint(-40, 40),
                        steps=random.randint(8, 16),
                    )
                    await asyncio.sleep(random.uniform(0.3, 0.9))

                await page.wait_for_load_state("networkidle", timeout=10000)
                await asyncio.sleep(random.uniform(2.0, 4.5))

                content = await page.content()
                if (
                    "pxchallenge" not in page.url.lower()
                    and "one more step" not in content.lower()
                ):
                    logger.info("Challenge solved successfully!")
                    return True

                await page.reload(wait_until="networkidle", timeout=10000)

            except Exception as e:
                logger.error(f"Attempt {attempt + 1} failed: {e}")
                try:
                    await page.reload(wait_until="networkidle", timeout=5000)
                except Exception as e:
                    logger.error(f"Page reload failed: {e}")

        return False

    def _parse_html_internal(self, html: str) -> list[PostProcessingDTO]:
        soup = BeautifulSoup(html, "html.parser")
        tbody = soup.find("tbody", {"data-testid": "offer-table-body"})
        if not tbody:
            return []

        offers = []
        rows = tbody.find_all("tr", {"data-testid": "offer-row"})

        for tr in rows:
            mpn = ""
            sku_url = ""
            sku_td = tr.find("td", {"data-sentry-component": "Sku"})
            if sku_td:
                a = sku_td.find("a")
                if a:
                    mpn = a.get_text(strip=True)
                    sku_url = a.get("href", "")

            distributor = ""
            manuf_td = tr.find("td", {"data-sentry-component": "Distributor"})
            if manuf_td:
                distributor = manuf_td.get_text(strip=True)

            in_stock = 0
            stock_td = tr.find("td", {"data-sentry-component": "Stock"})
            if stock_td:
                text = stock_td.get_text(strip=True)
                cleaned = "".join(c for c in text if c.isdigit())
                if cleaned:
                    in_stock = int(cleaned)

            price_tds = tr.find_all("td", {"data-sentry-component": "PriceAtQty"})
            prices_clean = []
            for td in price_tds:
                a = td.find("a")
                val = a.get_text(strip=True) if a else ""
                cleaned = (
                    val.replace("$", "")
                    .replace("*", "")
                    .replace(" ", "")
                    .strip()
                    .replace(",", ".")
                )
                prices_clean.append(cleaned if cleaned else "")

            while len(prices_clean) < 5:
                prices_clean.append("")

            tiers = [1, 10, 100, 1000, 10000]
            prices = []
            for idx, val in enumerate(prices_clean):
                if val:
                    try:
                        price = float(val)
                        prices.append(PriceDTO(qty=tiers[idx], price=price))
                    except Exception:
                        pass

            offers.append(
                PostProcessingDTO(
                    source=self.source,
                    mpn=mpn,
                    manufacture="",
                    description="",
                    package="",
                    distributor=distributor,
                    in_stock=in_stock,
                    lead_time="In Stock",
                    currency="USD",
                    prices=prices,
                    condition="New & Original",
                    country="China",
                    url=str(sku_url) if sku_url else "",
                )
            )

        return offers
