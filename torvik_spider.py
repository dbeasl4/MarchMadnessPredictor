import scrapy
from scrapy_playwright.page import PageMethod


class TorvikSpider(scrapy.Spider):
    name = "torvik"

    custom_settings = {
        'TWISTED_REACTOR': 'twisted.internet.asyncioreactor.AsyncioSelectorReactor',
        'DOWNLOAD_HANDLERS': {
            "http": "scrapy_playwright.handler.ScrapyPlaywrightDownloadHandler",
            "https": "scrapy_playwright.handler.ScrapyPlaywrightDownloadHandler",
        },
        'FEEDS': {
            'csvFiles/torvik_data.csv': {
                'format': 'csv',
                'overwrite': True,
            }
        },
        'LOG_LEVEL': 'INFO'
    }

    def start_requests(self):
        yield scrapy.Request(
            url="https://barttorvik.com/trank.php#",
            meta={
                "playwright": True,
                "playwright_include_page": True,
                "playwright_page_methods": [
                    PageMethod("wait_for_selector", "tr.highlighted"),
                ],
            },
            callback=self.parse
        )

    async def parse(self, response):
        page = response.meta["playwright_page"]

        # Column indices based on barttorvik.com table layout
        # 1:Rank 2:Team 3:Conf 4:Record 5:AdjOE 6:AdjDE 7:AdjEM 8:AdjT 9:Luck
        # 10:SOS_AdjEM 11:OppO 12:OppD 13:NCSOS
        for row in response.css('tr.highlighted'):
            team_name = row.css('td:nth-child(2) a::text').get()
            if not team_name:
                continue

            yield {
                'Team':     team_name.strip(),
                'Conf':     row.css('td:nth-child(3)::text').get('').strip(),
                'Record':   row.css('td:nth-child(4)::text').get('').strip(),
                'AdjOE':    row.css('td:nth-child(5)::text').get('').strip(),
                'AdjDE':    row.css('td:nth-child(6)::text').get('').strip(),
                'AdjEM':    row.css('td:nth-child(7)::text').get('').strip(),  # Net efficiency margin
                'AdjT':     row.css('td:nth-child(8)::text').get('').strip(),  # Tempo
                'Luck':     row.css('td:nth-child(9)::text').get('').strip(),
                'SOS_AdjEM':row.css('td:nth-child(10)::text').get('').strip(), # Strength of schedule
                'OppO':     row.css('td:nth-child(11)::text').get('').strip(),
                'OppD':     row.css('td:nth-child(12)::text').get('').strip(),
                'NCSOS':    row.css('td:nth-child(13)::text').get('').strip(),
            }

        await page.close()
