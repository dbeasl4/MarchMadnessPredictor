import scrapy
from scrapy_playwright.page import PageMethod


class EvanMiyaSpider(scrapy.Spider):
    """
    Scrapes evanmiya.com for Bayesian Performance Ratings (BPR).
    The site renders via React so we use Playwright to wait for the table.
    """
    name = "evanmiya"

    custom_settings = {
        'TWISTED_REACTOR': 'twisted.internet.asyncioreactor.AsyncioSelectorReactor',
        'DOWNLOAD_HANDLERS': {
            "http": "scrapy_playwright.handler.ScrapyPlaywrightDownloadHandler",
            "https": "scrapy_playwright.handler.ScrapyPlaywrightDownloadHandler",
        },
        'FEEDS': {
            'csvFiles/evanmiya_data.csv': {
                'format': 'csv',
                'overwrite': True,
            }
        },
        'LOG_LEVEL': 'INFO',
        'PLAYWRIGHT_DEFAULT_NAVIGATION_TIMEOUT': 60000,
    }

    def start_requests(self):
        yield scrapy.Request(
            url="https://evanmiya.com/",
            meta={
                "playwright": True,
                "playwright_include_page": True,
                "playwright_page_methods": [
                    # Wait for at least one data row to render
                    PageMethod("wait_for_selector", "div[role='rowgroup'] div[role='row']"),
                ],
            },
            callback=self.parse
        )

    async def parse(self, response):
        page = response.meta["playwright_page"]

        # evanmiya uses a virtualized table — scroll to load all rows first
        await page.evaluate("""
            async () => {
                const grid = document.querySelector("div[role='rowgroup']");
                if (!grid) return;
                let prev = -1;
                while (grid.scrollTop !== prev) {
                    prev = grid.scrollTop;
                    grid.scrollBy(0, 2000);
                    await new Promise(r => setTimeout(r, 400));
                }
            }
        """)

        # Re-grab the fully rendered HTML after scroll
        content = await page.content()
        from scrapy import Selector
        sel = Selector(text=content)

        rows = sel.css("div[role='rowgroup'] div[role='row']")
        for row in rows:
            cells = row.css("div[role='gridcell']")
            if len(cells) < 8:
                continue

            def cell(n):
                return cells[n].css("::text").getall()
            
            # Flatten any nested text nodes
            def flat(n):
                return ' '.join(cell(n)).strip()

            team = flat(1)
            if not team:
                continue

            yield {
                'Team':         team,
                'BPR':          flat(2),   # Overall Bayesian Performance Rating
                'OBPR':         flat(3),   # Offensive BPR
                'DBPR':         flat(4),   # Defensive BPR
                'Rank':         flat(0),
                'Conf':         flat(5),
                'Record':       flat(6),
                'Pace':         flat(7),   # Possessions per 40 min
            }

        await page.close()
