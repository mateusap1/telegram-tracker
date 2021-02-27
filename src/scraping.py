import random
import sqlite3
import ast
import time
import requests
import concurrent.futures
import lxml.html

from bs4 import BeautifulSoup


MAIN_URL = "https://www.hepsiburada.com/"
TIMEOUT = 10
TIMEOUT_THREADS = 70
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
    
    def random_proxy(self):
        with sqlite3.connect(self.database) as conn:
            c = conn.cursor()

            c.execute("SELECT url FROM proxies")
            proxies = [row[0] for row in c.fetchall()]

            if len(proxies) == 0:
                return None

            proxy = random.choice(proxies)

            return proxy
  
    def add_products(self) -> None:
        """Adds product if it is not already in the table"""

        with sqlite3.connect(self.database) as conn:
            c = conn.cursor()

            products = self.products.copy()
            self.products = []

            for product in products:
                product_id, listing_id, product_name, product_price, \
                    product_url, seller, url_id = product

                c.execute("SELECT * FROM products WHERE listing_id = ?", (listing_id, ))
                if len(c.fetchall()) > 0:
                    c.execute(
                        "UPDATE products SET current_price = ? WHERE listing_id = ?", 
                        (product_price, listing_id)
                    )
                else:
                    c.execute(
                        "INSERT INTO products VALUES (?, ?, ?, ?, ?, ?, ?, ?)", (
                            product_id, 
                            listing_id, 
                            product_name,
                            product_price,
                            product_price,
                            seller,
                            product_url,
                            url_id
                    ))
            
            conn.commit()

    def url_scraping(self, row):
        products = []
        url_id = row[0]
        url = row[1]

        try:
            start = time.time()

            print(f"[Scraper] URL {url} is being scraped...")

            proxy = self.random_proxy()
            if proxy is not None:
                proxies = {
                    "http": proxy,
                    "https": proxy
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
            if len(pages_el) <= 0 or "sayfa=" in url:
                page_limit = 1
            else:
                page_limit = int(pages_el[-1].text) # The number of different product pages

            for i in range(1, page_limit+1):
                if time.time() - start > TIMEOUT_THREADS:
                    print(f"[Debugging] Timeout reached on URL {url}")
                    return

                if page_limit == 1:
                    current_url = url
                    pass
                elif "?" in url:
                    current_url = url + f"&sayfa={i}"
                else:
                    current_url = url + f"?sayfa={i}"

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

                # Get the product name
                p_names = html.xpath(".//h3[@class='product-title title']")

                # Get the product info
                a_els = html.xpath(".//a[@data-isinstock='True']")

                button_els = html.xpath(".//button[@class='add-to-basket button small']")
                
                j = 0
                for p_name, a_el in zip(p_names, a_els):
                    if len(button_els) == len(a_els) == len(p_names):
                        try:
                            product_info = ast.literal_eval(button_els[j].get("data-product"))
                            seller = product_info["merchantName"]
                            product_price = float(product_info["price"])
                        except ValueError:
                            seller = None
                            product_price = float(a_el.get("data-price").replace(",", "."))
                    else:
                        seller = None
                        product_price = float(a_el.get("data-price").replace(",", "."))

                    listing_id = a_el.get("data-listing_id").lower()
                    product_id = a_el.get("data-productid").lower()

                    product_url = MAIN_URL[:-1] + a_el.get("href")
                    product_name = p_name.get("title")

                    self.products.append((
                        product_id, 
                        listing_id,
                        product_name, 
                        product_price, 
                        product_url, 
                        seller,
                        url_id
                    ))

                    j += 1
                
            print(f"[Scraper] URL {url} was successfuly scraped")
                
            return products

        except Exception as e:
            print(f"[Debugging] Error while scraping subcategory in URL {url} -> \"{e}\"")

    def get_products(self, unused) -> None:
        """Add products from a subcategory to the db"""

        # Argument `unused` has no real value
        start = time.time()

        with sqlite3.connect(self.database) as conn:
            c = conn.cursor()

            c.execute("SELECT rowid, * FROM urls;")
            url_rows = c.fetchall()

            if len(url_rows) == 0:
                return

        with concurrent.futures.ThreadPoolExecutor() as executor:
            executor.map(self.url_scraping, url_rows)

        end = time.time()
        print(f"[Scraper] Cycle completed successfuly in {end - start} seconds.")

    def get_product_info(self, url: str) -> dict:
        proxy = self.random_proxy()
        if proxy is not None:
            proxies = {
                "http": proxy,
                "https": proxy
            }
        else:
            proxies = None

        response = requests.get(url, headers=HEADERS, proxies=proxies)

        if response is not None:
            if response.status_code == 200:
                html = lxml.html.fromstring(response.content)
            else:
                print(f"[Scraper] HTTP error {response.status_code} in subcategory {subcategory_name}")
                return
        else:
            print("[Scraper] ERROR -> Response is None")
            return
        
        price_els = html.xpath("//span[@id='offering-price']")
        if len(price_els) > 0:
            price = price_els[0].get("content")
        else:
            print("[Scraper] Price not found")
            return None

        seller_els = html.xpath("//span[@class='seller']/span/a/text()")
        if len(seller_els) > 0:
            seller = seller_els[0].replace(" ", "").replace("\n", "").replace("\r", "")
        else:
            print("[Scraper] Seller not found")
            return None
        
        return {
            "price": float(price),
            "seller": seller
        }

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
        result = input("Are you sure you want to clean the database? (Y/n)")
        while not result[0].lower() in ["y", "n"]:
            result = input("Are you sure you want to clean the database? (Y/n)")
        
        if result[0].lower() == "n":
            return

        with sqlite3.connect(self.database) as conn:
            c = conn.cursor()

            c.execute(f"DELETE FROM urls;")
            c.execute(f"DELETE FROM brands;")
            c.execute(f"DELETE FROM proxies;")
            c.execute(f"DELETE FROM products;")

            conn.commit()

if __name__ == "__main__":
    scraper = Scraper("./data/database.db")
    scraper.clean_db()