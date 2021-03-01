import random
import sqlite3
import ast
import time
import requests
import concurrent.futures
import lxml.html
import re
import json
import unicodedata

from bs4 import BeautifulSoup


MAIN_URL = "https://www.hepsiburada.com/"
TIMEOUT = 10
TIMEOUT_THREADS = 360
INFINITE = 10 ** 6
HEADERS = {
    "Accept-Language": "en-US,en;q=0.5",
    "Connection": "keep-alive",
    "Referer": "https://www.hepsiburada.com/",
    "User-Agent": "Mozilla/5.0 (X11; Ubuntu; Linux x86_64; rv:85.0) Gecko/20100101 Firefox/85.0",
    "cache-control": "private, max-age=0, no-cache"
}


class Scraper(object):

    def __init__(self, database: str):
        self.database = database

        self.products = []
        self.queries = []
    
    def random_proxy(self):
        with sqlite3.connect(self.database) as conn:
            c = conn.cursor()

            c.execute("SELECT url FROM proxies")
            proxies = [row[0] for row in c.fetchall()]

            if len(proxies) == 0:
                return None

            proxy = random.choice(proxies)

            return proxy
  
    def execute_queries(self):
        with sqlite3.connect(self.database) as conn:
            c = conn.cursor()

            queries = self.queries.copy()
            self.queries = []

            for query in queries:
                c.execute(*query)

    def add_products(self) -> None:
        """Adds product if it is not already in the table"""

        with sqlite3.connect(self.database) as conn:
            c = conn.cursor()

            products = self.products.copy()
            self.products = []

            for product in products:
                product_id, product_name, product_price, product_url, seller, url_id = product

                c.execute("SELECT * FROM products WHERE product_id = ?", (product_id, ))
                if len(c.fetchall()) > 0:
                    c.execute(
                        "UPDATE products SET current_price = ? WHERE product_id = ?", 
                        (product_price, product_id)
                    )
                else:
                    c.execute(
                        "INSERT INTO products VALUES (?, ?, ?, ?, ?, ?, ?)", (
                            product_id, 
                            product_name,
                            product_price,
                            product_price,
                            seller,
                            product_url,
                            url_id
                    ))
            
            conn.commit()

    def get_sellers(self, html: str) -> None:
        """Returns all the sellers and their prices from a product"""

        regex = r"window\.HERMES\.YORUMLAR = Object.assign\(window.HERMES.YORUMLAR \|\| \{\}, \{\n\s+.*\n\s+.*"
        first_match = re.search(regex, html)
        if first_match is None:
            return None

        first_match = first_match.group()

        regex = r"window\.HERMES\.YORUMLAR = Object.assign\(window.HERMES.YORUMLAR \|\| \{\}, \{\n\s+.*\n\s+"
        final_match = re.sub(regex, "", first_match)
        if final_match is None:
            return None
        
        json_str = final_match.replace("'STATE': ", "")
        final = json.loads(json_str)

        variants = final["data"]["selectedVariant"]["variantListing"]
        sellers = {}

        for variant in variants:
            sellers[variant["merchantName"]] = variant["finalPriceOnSale"]

        return sellers

    def get_product_info(self, url: str) -> dict:
        proxy = self.random_proxy()
        if proxy is not None:
            proxies = {
                "http": proxy
            }
        else:
            proxies = None

        response = requests.get(url, headers=HEADERS, proxies=proxies)

        if response is not None:
            if response.status_code == 200:
                html = lxml.html.fromstring(response.content)
            else:
                print(f"[Debugging] HTTP error {response.status_code} in subcategory {subcategory_name}")
                return None
        else:
            print("[Debugging] ERROR -> Response is None")
            return None
        
        title = html.xpath("//h1[@id='product-name']/text()")
        if len(title) == 0 or title is None:
            print(f"[Debugging] Title not found in URL {url}")
            return None
        else:
            title = unicodedata.normalize("NFKD", title[0].strip("\r\n" + " " * 8))
        
        sellers = self.get_sellers(response.text)

        if len(sellers) == 0 or sellers is None:
            price_els = html.xpath("//span[@id='offering-price']/@content")
            if len(price_els) > 0:
                price = price_els[0].get("content")
            else:
                print(f"[Debugging] Price not found in URL {url}")
                return None

            seller_els = html.xpath("//span[@class='seller']/span/a/text()")
            if len(seller_els) > 0:
                seller = seller_els[0].strip("\r\n" + " " * 8)
            else:
                print(f"[Debugging] Seller not found in URL {url}")
                return None
        else:
            price = INFINITE
            seller = None

            for current_seller, current_price in sellers.items():
                if current_price < price:
                    price = current_price
                    seller = current_seller
        
        if seller is None:
            print(f"[Debugging] Seller not found in URL {url}")
            return None
        
        return {
            "title": title,
            "price": float(price),
            "seller": seller
        }

    def url_scraping(self, args):
        row = args[0]
        proxy = args[1]

        url_id = row[0]
        url = row[1]

        try:
            start = time.time()

            print(f"[Scraper] URL {url} is being scraped...")

            if proxy is not None:
                proxies = {
                    "http": proxy
                }
            else:
                proxies = None

            response = requests.get(
                url, 
                headers=HEADERS, 
                proxies=proxies, 
                timeout=TIMEOUT
            )

            if response is not None:
                if response.status_code == 200:
                    html = lxml.html.fromstring(response.content)
                else:
                    print(f"[Debugging] HTTP error {response.status_code} in subcategory {url}")
                    return
            else:
                print("[Debugging] ERROR -> Response is None")
                return

            pages_el = html.xpath("//div[@id='pagination']/ul/li/a")
            if len(pages_el) == 0 or pages_el is None:
                page_limit = 1
            else:
                page_limit = int(pages_el[-1].text) # The number of different product pages

            for i in range(1, page_limit+1):
                if time.time() - start > TIMEOUT_THREADS:
                    print(f"[Debugging] Timeout reached on URL {url}")
                    return

                mark = "?" if not "?" in url else "&"
                current_url = url + f"{mark}sayfa={i}"

                response = requests.get(
                    current_url, 
                    headers=HEADERS, 
                    proxies=proxies, 
                    timeout=TIMEOUT
                )

                if not response is None:
                    if response.status_code == 200:
                        html = lxml.html.fromstring(response.content)
                    else:
                        print(f"[Debugging] HTTP error {response.status_code} in subcategory {current_url}")
                        continue
                else:
                    print("[Debugging] ERROR -> Response is None")
                    continue

                # Get the product info
                a_els = html.xpath(".//a[@data-isinstock='True']")
                if a_els is None:
                    print(f"[Debugging] No products found in URL {current_url}")
                    return

                for a_el in a_els:
                    href = a_el.get("href")
                    for i, part in enumerate(href.split("-")):
                        if part == "p":
                            product_id = href.split("-")[i+1].lower()

                    if product_id is None:
                        print(f"[Debugging] No product id found in URL {current_url}")
                        continue

                    product_url = MAIN_URL[:-1] + href

                    info = self.get_product_info(product_url)
                    if info is None:
                        print(f"[Debugging] No info found in product with URL {product_url}")
                        continue

                    self.products.append((
                        product_id, 
                        info["title"], 
                        info["price"], 
                        product_url, 
                        info["seller"], 
                        url_id
                    ))
            
            self.queries.append(("UPDATE urls SET first_cycle = 1 WHERE rowid = ?", (url_id, )))
                
            print(f"[Scraper] URL {url} was successfuly scraped")

        except Exception as e:
            print(f"[Debugging] Error while scraping subcategory in URL {url} -> \"{e}\"")

    def get_products(self, unused) -> None:
        """Add products from a subcategory to the db"""

        # Argument `unused` has no real value
        start = time.time()

        # TODO: Remove sqlite3 from this method
        with sqlite3.connect(self.database) as conn:
            c = conn.cursor()

            c.execute("SELECT rowid, * FROM urls;")
            url_rows = c.fetchall()

            c.execute("SELECT * FROM products;")
            product_rows = c.fetchall()

            if len(url_rows) == 0:
                return
            
            if len(product_rows) == 0:
                self.first_cycle = True

            proxies = [self.random_proxy() for _ in range(len(url_rows))]
            with concurrent.futures.ThreadPoolExecutor(max_workers=20) as executor:
                executor.map(self.url_scraping, zip(url_rows, proxies))

            end = time.time()
            print(f"[Scraper] Cycle completed successfuly in {end - start} seconds.")

    def delete_urls(self, urls: list) -> None:
        with sqlite3.connect(self.database) as conn:
            c = conn.cursor()

            q_marks = ", ".join(["?" for _ in range(len(urls))])
            c.execute(f"SELECT rowid FROM urls WHERE url IN ({q_marks})", urls)
            url_ids = [row[0] for row in c.fetchall()]

            c.execute(f"DELETE FROM urls WHERE rowid IN ({q_marks});", url_ids)
            c.execute(f"DELETE FROM products WHERE url_id IN ({q_marks});", url_ids)

            conn.commit()

    def clean_db(self) -> None:
        result = input("Are you sure you want to clean the database? (Y/n) ")
        while not result[0].lower() in ["y", "n"]:
            result = input("Are you sure you want to clean the database? (Y/n) ")
        
        if result[0].lower() == "n":
            print("Database was not modified")
            return

        with sqlite3.connect(self.database) as conn:
            c = conn.cursor()

            c.execute(f"DELETE FROM urls;")
            c.execute(f"DELETE FROM proxies;")
            c.execute(f"DELETE FROM products;")

            conn.commit()
    
        print("Database cleaned successfuly")

if __name__ == "__main__":
    scraper = Scraper("./data/database.db")
    scraper.clean_db()
    scraper.get_product_info("https://www.hepsiburada.com/regal-nf-3020-a-300-lt-no-frost-buzdolabi-p-HBV00000ULL5K")