import grequests
from fake_useragent import UserAgent

ua = UserAgent()

headers = {
    "Accept-Language": "en-US,en;q=0.5",
    "Connection": "keep-alive",
    "Referer": "https://www.hepsiburada.com/",
    "User-Agent": "Mozilla/5.0 (X11; Ubuntu; Linux x86_64; rv:85.0) Gecko/20100101 Firefox/85.0"
}

urls = [
    "https://stackoverflow.com/questions/8692/how-to-use-xpath-in-python",
    "https://www.hepsiburada.com/canon-pg-46-siyah-murekkep-kartusu-p-BS51277",
    "https://www.hepsiburada.com/epson-103-4-renk-takim-murekkep-l3110-l3111-l3150-l3151-l4150-l6190-l6160-l4160-kutusuz-p-HBV00000IHXWD",
    "https://www.hepsiburada.com/hp-652-siyah-murekkep-kartusu-f6v25ae-p-BS52263",
    "https://www.hepsiburada.com/hp-650-siyah-murekkep-kartusu-cz101ae-p-BS300110"
]

rs = (grequests.get(u, headers=headers) for u in urls)

r = grequests.map(rs, size=20)
print(r)