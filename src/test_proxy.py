import requests
import sys

proxy = sys.argv[0]
print(f"Testing proxy {proxy}")

PROXIES = {
    "http": proxy
}

HEADERS = {
    "Accept-Language": "en-US,en;q=0.5",
    "Connection": "keep-alive",
    "Referer": "https://www.hepsiburada.com/",
    "User-Agent": "Mozilla/5.0 (X11; Ubuntu; Linux x86_64; rv:85.0) Gecko/20100101 Firefox/85.0",
    "cache-control": "private, max-age=0, no-cache"
}

r = requests.get("https://www.hepsiburada.com/", proxies=PROXIES, headers=HEADERS)
s = r.status_code
print(s)

if s == 200:
    print("Proxy was successful")
else:
    print("Proxy was failed")