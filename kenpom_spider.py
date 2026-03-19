import scrapy
from scrapy_playwright.page import PageMethod


class KenpomSpider(scrapy.Spider):
    """
    Scrapes KenPom.com main ratings table.
    REQUIRES a paid KenPom account — set your credentials in settings.py or
    pass them via environment variables KENPOM_USER / KENPOM_PASS.
    """
    name = "kenpom"

    custom_settings = {
        'TWISTED_REACTOR': 'twisted.internet.asyncioreactor.AsyncioSelectorReactor',
        'DOWNLOAD_HANDLERS': {
            "http": "scrapy_playwright.handler.ScrapyPlaywrightDownloadHandler",
            "https": "scrapy_playwright.handler.ScrapyPlaywrightDownloadHandler",
        },
        'FEEDS': {
            'csvFiles/kenpom_data.csv': {
                'format': 'csv',
                'overwrite': True,
            }
        },
        'LOG_LEVEL': 'INFO',
    }

    LOGIN_URL = "https://kenpom.com/login.php"
    RATINGS_URL = "https://kenpom.com/"

    def start_requests(self):
        yield scrapy.Request(
            url=self.LOGIN_URL,
            meta={
                "playwright": True,
                "playwright_include_page": True,
            },
            callback=self.do_login
        )

    async def do_login(self, response):
        import os
        page = response.meta["playwright_page"]

        email = os.environ.get("KENPOM_USER", "YOUR_EMAIL_HERE")
        password = os.environ.get("KENPOM_PASS", "YOUR_PASSWORD_HERE")

        await page.fill('input[name="email"]', email)
        await page.fill('input[name="password"]', password)
        await page.click('input[type="submit"]')
        await page.wait_for_url("https://kenpom.com/", timeout=15000)

        # Hand off the authenticated page to the ratings parser
        yield scrapy.Request(
            url=self.RATINGS_URL,
            meta={
                "playwright": True,
                "playwright_include_page": True,
                "playwright_page": page,
                "playwright_page_methods": [
                    PageMethod("wait_for_selector", "table#ratings-table"),
                ],
            },
            callback=self.parse_ratings,
            dont_filter=True,
        )

    async def parse_ratings(self, response):
        page = response.meta["playwright_page"]

        # KenPom table columns:
        # 1:Rank 2:Team 3:Conf 4:W-L 5:AdjEM 6:AdjO(rank) 7:AdjD(rank)
        # 8:AdjT(rank) 9:Luck(rank) 10:SOS_AdjEM(rank) 11:OppO 12:OppD 13:NCSOS
        for row in response.css('table#ratings-table tbody tr'):
            team_name = row.css('td.team a::text').get()
            if not team_name:
                continue

            tds = row.css('td')

            def td(n):
                return tds[n].css('::text').get('').strip() if n < len(tds) else ''

            yield {
                'Team':     team_name.strip(),
                'Conf':     td(2),
                'Record':   td(3),
                'AdjEM':    td(4),
                'AdjO':     td(5),
                'AdjD':     td(6),
                'AdjT':     td(7),
                'Luck':     td(8),
                'SOS_AdjEM':td(9),
                'OppO':     td(10),
                'OppD':     td(11),
                'NCSOS':    td(12),
            }

        await page.close()
