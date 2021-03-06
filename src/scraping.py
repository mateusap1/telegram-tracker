import random
import sqlite3
import ast
import time
import requests
import concurrent.futures
import lxml.html
import datetime
import configparser

from bs4 import BeautifulSoup

config = configparser.ConfigParser()
config.read("./config.ini")

TIMEOUT = config.getfloat("DEFAULT", "timeout_requests")
TIMEOUT_THREADS = config.getfloat("DEFAULT", "timeout_thread")

PROXY_ADDR = config.get("PROXY", "address")
PROXY_PORT = config.get("PROXY", "port")
PROXY_USER = config.get("PROXY", "username")
PROXY_PASSWORD = config.get("PROXY", "password")

if not PROXY_ADDR.strip() == "" and not PROXY_PORT.strip() == "":
    if PROXY_USER.strip() == "" or PROXY_PASSWORD.strip() == "":
        PROXY = PROXY_ADDR + ":" + PROXY_PORT
    else:
        PROXY = "http://" + PROXY_USER + ":" + PROXY_PASSWORD + "@" + PROXY_ADDR + ":" + PROXY_PORT + "/"
else:
    PROXY = None

user_agent_list = [
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_5) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/13.1.1 Safari/605.1.15',
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:77.0) Gecko/20100101 Firefox/77.0',
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_5) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/83.0.4103.97 Safari/537.36',
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:77.0) Gecko/20100101 Firefox/77.0',
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/83.0.4103.97 Safari/537.36',
]

MAIN_URL = "http://www.hepsiburada.com/"
INFINIT = 10 ** 6


class Scraper(object):

    def __init__(self, database: str):
        self.database = database

        self.mode = None
        self.products = []
        self.new_products = []
        self.queries = []
        self.url_rows = []
    
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

            c.execute(f"SELECT product_id FROM products;")
            old_products_ids = [row[0] for row in c.fetchall()]

            c.execute("SELECT rowid FROM urls WHERE first_cycle = 1;")
            first_ids = [row[0] for row in c.fetchall()]

            for product in products:
                date, product_id, product_name, price, product_url, url_id = product

                if self.mode == "warn" or self.mode == "warn-track":
                    if not (product_id in old_products_ids) and not (url_id in first_ids):
                        info = self.get_product_info(product_url)
                        if info is not None:
                            seller = info["seller"]
                            product = date, product_id, product_name, price, product_url, url_id

                            if seller.lower() == "hepsiburada":
                                self.new_products.append(product)
                
                c.execute(
                    "INSERT INTO products VALUES (?, ?, ?, ?, ?, ?);", (
                    date,
                    product_id, 
                    product_name,
                    price,
                    product_url,
                    url_id
                ))

                repetitions = old_products_ids.count(product_id) + 1
                if repetitions >= 3:
                    c.execute(
                        "DELETE FROM products WHERE product_id = ? ORDER BY date ASC LIMIT ?", 
                        (product_id, repetitions - 2)
                    )
            
            conn.commit()

    def get_product_info(self, url: str) -> dict:
        if PROXY is not None:
            proxies = {
                "http": PROXY,
                "https": PROXY
            }
        else:
            proxies = None

        headers = {
            "User-Agent": random.choice(user_agent_list),
            "Cache-Control": "no-cache"
        }

        url = url.replace("https", "http")

        response = requests.get(url, headers=headers, proxies=proxies)

        if response is not None:
            if response.status_code == 200:
                html = lxml.html.fromstring(response.content)
            else:
                print(f"[Debugging] HTTP error {response.status_code} in URL {URL_name}")
                return None
        else:
            print("[Debugging] ERROR -> Response is None")
            return None

        price_els = html.xpath("//span[@id='offering-price']")
        if price_els is not None and len(price_els) > 0:
            price = price_els[0].get("content")
        else:
            return None

        seller_els = html.xpath("//span[@class='seller']/span/a/text()")
        if seller_els is not None and len(seller_els) > 0:
            seller = seller_els[0].strip("\r\n" + " " * 8)
        else:
            return None
        
        return {
            "price": float(price),
            "seller": seller
        }

    def url_scraping(self, row):
        url_id = row[0]
        url = row[1].replace("https", "http")

        try:
            start = time.time()

            print(f"[Scraper] URL {url} is being scraped...")

            if PROXY is not None:
                proxies = {
                    "http": PROXY,
                    "https": PROXY
                }
            else:
                proxies = None

            headers = {
                "User-Agent": random.choice(user_agent_list),
                "Cache-Control": "no-cache"
            }

            response = requests.get(
                url, 
                headers=headers, 
                proxies=proxies, 
                timeout=TIMEOUT
            )

            if response is not None:
                if response.status_code == 200:
                    html = lxml.html.fromstring(response.content)
                else:
                    print(f"[Debugging] HTTP error {response.status_code} in URL {url}")
                    return
            else:
                print("[Debugging] ERROR -> Response is None")
                return

            pages_el = html.xpath("//div[@id='pagination']/ul/li/a")
            if pages_el is None or len(pages_el) == 0:
                page_limit = 1
            else:
                page_limit = int(pages_el[-1].text) # The number of different product pages

            for i in range(1, page_limit+1):
                if (time.time() - start) > (TIMEOUT_THREADS * page_limit):
                    print(f"[Debugging] Timeout reached on URL {url}")
                    return

                mark = "?" if not "?" in url else "&"
                current_url = url + f"{mark}sayfa={i}"

                response = requests.get(
                    current_url, 
                    headers=headers, 
                    proxies=proxies, 
                    timeout=TIMEOUT
                )

                if not response is None:
                    if response.status_code == 200:
                        html = lxml.html.fromstring(response.content)
                    else:
                        print(f"[Debugging] HTTP error {response.status_code} in URL {current_url}")
                        continue
                else:
                    print("[Debugging] ERROR -> Response is None")
                    continue

                # Get the product name
                p_names = html.xpath("//h3[@class='product-title title']")

                # Get the product info
                a_els = html.xpath("//a[@data-isinstock='True']")

                for a_el, p_name in zip(a_els, p_names):
                    product_id = a_el.get("data-sku").lower()
                    product_price = float(a_el.get("data-price").replace(",", "."))
                    product_url = MAIN_URL[:-1] + a_el.get("href")
                    product_name = p_name.get("title")

                    self.products.append((
                        str(datetime.datetime.now()),
                        product_id, 
                        product_name, 
                        product_price, 
                        product_url, 
                        url_id
                    ))
            
            self.queries.append(("UPDATE urls SET first_cycle = 0 WHERE rowid = ?", (url_id, )))
                
            print(f"[Scraper] URL {url} was successfuly scraped")

        except Exception as e:
            print(f"[Debugging] Error while scraping URL {url} -> \"{e}\"")

    def get_products(self, _) -> None:
        """Add products from an URL to the db"""

        start = time.time()

        if len(self.url_rows) == 0:
            return
        

        if PROXY is not None:
            print(f"[Debugging] Scraping with proxy {PROXY}...")
        else:
            print(f"[Debugging] Scraping with no proxy...")

        with concurrent.futures.ThreadPoolExecutor() as executor:
            executor.map(self.url_scraping, self.url_rows)

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
            c.execute(f"DELETE FROM products;")

            conn.commit()
    
        print("Database cleaned successfuly")

if __name__ == "__main__":
    scraper = Scraper("./data/database.db")
    scraper.clean_db()