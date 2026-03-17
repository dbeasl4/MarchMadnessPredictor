import scrapy


class KenPomSpider(scrapy.Spider):
    name = "kenpom"
    start_urls = ["https://kenpom.com/index.php"]

    custom_settings = {
        'FEEDS':{
            'csv/kenpom_current.csv':{
                'format': 'csv',
                #Setting to false so it keeps new iteration of curated csv file
                'overwrite':False,
            }
        }
    }

    def parse(self, response):
        for row in response.css('table tbody tr'):
            team = row.css('td.team a::text').get()
            if team:
                yield{
                    'team':team,
                    'barthag': row.css('td:nth-child(5)::text').get(),
                    'adjOE': row.css('td:nth-child(7)::text').get(),
                    'adjDE': row.css('td:nth-child(7)::text').get(),
                }