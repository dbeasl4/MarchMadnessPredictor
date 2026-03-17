import scrapy
from scrapy_playwright.page import PageMethod

class TorvikSpider(scrapy.Spider):
    name = "torvik"
    
    # We must start the request manually to enable Playwright
    def start_requests(self):
        yield scrapy.Request(
            url="https://barttorvik.com/trank.php",
            meta={
                "playwright": True,
                "playwright_include_page": True,
                "playwright_page_methods": [
                    # Wait for the table rows to actually appear in the browser
                    PageMethod("wait_for_selector", "tr.highlighted"),
                ],
            },
            callback=self.parse
        )

    custom_settings = {
        # Playwright specific settings
        'TWISTED_REACTOR': 'twisted.internet.asyncioreactor.AsyncioSelectorReactor',
        'DOWNLOAD_HANDLERS': {
            "http": "scrapy_playwright.handler.ScrapyPlaywrightDownloadHandler",
            "https": "scrapy_playwright.handler.ScrapyPlaywrightDownloadHandler",
        },
        'FEEDS': {
            'torvik_playwright_data.csv': {
                'format': 'csv',
                'overwrite': True,
            }
        },
        'LOG_LEVEL': 'INFO'
    }

    async def parse(self, response):
        # We need to close the page manually when using playwright_include_page
        page = response.meta["playwright_page"]
        
        # Now we can use standard CSS selectors on the rendered HTML
        for row in response.css('tr.highlighted'):
            team_name = row.css('a::text').get()
            if team_name:
                yield {
                    'Team': team_name.strip(),
                    'AdjOE': row.css('td:nth-child(4)::text').get(),
                    'AdjDE': row.css('td:nth-child(5)::text').get(),
                }
        
        await page.close()