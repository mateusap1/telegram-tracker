import random
import sys
import time
import requests
import concurrent.futures
import lxml.html
import datetime
import configparser
import mysql.connector

# Testing SSH

config = configparser.ConfigParser()
config.read("./config.ini")

max_threads = config.getint("DEFAULT", "threads")

TIMEOUT = config.getfloat("TIME", "timeout_requests")
TIMEOUT_THREADS = config.getfloat("TIME", "timeout_thread")
EXPIRE_PRODUCTS = config.getfloat("TIME", "expire_products")

PROXY_ADDR = config.get("PROXY", "address")
PROXY_PORT = config.get("PROXY", "port")
PROXY_USER = config.get("PROXY", "username")
PROXY_PASSWORD = config.get("PROXY", "password")

if not PROXY_ADDR.strip() == "" and not PROXY_PORT.strip() == "":
    if PROXY_USER.strip() == "" or PROXY_PASSWORD.strip() == "":
        PROXY = PROXY_ADDR + ":" + PROXY_PORT
    else:
        PROXY = "http://" + PROXY_USER + ":" + \
            PROXY_PASSWORD + "@" + PROXY_ADDR + ":" + PROXY_PORT
else:
    PROXY = None

DB_HOST = config.get("DATABASE", "host")
DB_USER = config.get("DATABASE", "user")
DB_PASSWORD = config.get("DATABASE", "password")
DB_NAME = "telegram_tracker"

MAIN_URL = "http://www.hepsiburada.com/"
INFINIT = 10 ** 6

with open("./ua.txt", "r") as f:
    user_agent_list = f.read().split("\n")


class Scraper(object):

    def __init__(self):
        self.mode = None
        self.new_products = []
        self.deleted = []
        self.url_rows = []

    def connect_db(self) -> None:
        return mysql.connector.connect(
            host=DB_HOST,
            user=DB_USER,
            password=DB_PASSWORD,
            database=DB_NAME
        )

    def save_db(self, db) -> None:
        """Commit the changes to the database"""

        db.commit()
        db.close()

    def get_product_info(self, url: str) -> dict:
        """Returns the price and the seller name of a product based on the URL given"""

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
                print(
                    f"[Debugging] HTTP error {response.status_code} in URL {URL_name}")
                return None
        else:
            print("[Debugging] ERROR -> Response is None")
            return None

        # Gets the price from the product page
        price_els = html.xpath("//span[@id='offering-price']")
        if price_els is not None and len(price_els) > 0:
            price = price_els[0].get("content")
        else:
            return None

        # Gets the seller name from the product page
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
        """Based on a given URL, adds the products data to the database of every page it can find"""

        url_id = row[0]
        url = row[1].replace("https", "http")

        db = self.connect_db()
        c = db.cursor()

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
                    print(
                        f"[Debugging] HTTP error {response.status_code} in URL {url}")
                    return
            else:
                print("[Debugging] ERROR -> Response is None")
                return

            # Gets all the possible pages in the catalog
            pages_el = html.xpath("//div[@id='pagination']/ul/li/a")
            if pages_el is None or len(pages_el) == 0:
                page_limit = 1
            else:
                # The number of different product pages
                page_limit = int(pages_el[-1].text)

            if self.mode == "warn" or self.mode == "warn-track":
                c.execute(f"SELECT listing_id FROM products;")
                old_listing_ids = [row[0] for row in c.fetchall()]

                c.execute("SELECT rowid FROM urls WHERE cycle > 0;")
                first_ids = [row[0] for row in c.fetchall()]

            # For each of the possible pages, get the products info and add them to the db
            for i in range(1, page_limit+1):
                # If we've reached our timeout, return
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
                        print(
                            f"[Debugging] HTTP error {response.status_code} in URL {current_url}")
                        continue
                else:
                    print("[Debugging] ERROR -> Response is None")
                    continue

                c.close()
                self.save_db(db)

                db = self.connect_db()
                c = db.cursor()

                # Get the product name
                p_names = html.xpath("//h3[@class='product-title title']")

                # Get the product info
                a_els = html.xpath("//a[@data-isinstock='True']")

                # Adds all products from this page to the db
                for a_el, p_name in zip(a_els, p_names):
                    product_id = a_el.get("data-sku").lower()
                    listing_id = a_el.get("data-listing_id").lower()
                    product_price = float(
                        a_el.get("data-price").replace(",", "."))
                    product_url = MAIN_URL[:-1] + a_el.get("href")
                    product_name = p_name.get("title")
                    date = str(datetime.datetime.now())

                    c.execute(
                        "INSERT INTO products VALUES (%s, %s, %s, %s, %s, %s, %s, %s);", (
                            date + " |X| " + listing_id,
                            date,
                            listing_id,
                            product_id,
                            product_name,
                            product_price,
                            product_url,
                            url_id
                        )
                    )

                    if self.mode == "warn" or self.mode == "warn-track":
                        # If this wasn't in the database before, append to the new_products list
                        if not (listing_id in old_listing_ids) and not (url_id in first_ids):
                            product = (
                                date + " |X| " + listing_id,
                                date,
                                listing_id,
                                product_id,
                                product_name,
                                product_price,
                                product_url,
                                url_id
                            )

                            self.new_products.append(product)

            # Make the db know that we completed one more cycle with this URL
            c.execute(
                "UPDATE urls SET cycle = cycle + 1 WHERE rowid = %s;", (url_id, ))
            c.close()
            self.save_db(db)

            print(f"[Scraper] URL {url} was successfully scraped")

        except Exception as e:
            c.close()
            self.save_db(db)

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

        with concurrent.futures.ThreadPoolExecutor(max_workers=max_threads) as executor:
            executor.map(self.url_scraping, self.url_rows)

        self.delete_repeated()

        end = time.time()
        print(
            f"[Scraper] Cycle completed successfully in {end - start} seconds")

    def delete_repeated(self) -> None:
        print("[Bot] Deleting repeated rows...")

        try:
            db = self.connect_db()
            c = db.cursor()

            deleted = self.deleted.copy()

            if len(deleted) > 0:
                marks = ", ".join(["%s" for _ in range(len(deleted))])
                c.execute(
                    f"DELETE FROM products WHERE rowid IN ({marks});", deleted)

            self.deleted = []

            time = str(datetime.datetime.now() -
                       datetime.timedelta(minutes=EXPIRE_PRODUCTS))
            c.execute("DELETE FROM products WHERE date < %s;", (time, ))

            c.close()
            self.save_db(db)

            print("[Bot] Repeated rows deleted successfully")
        except Exception as e:
            print(f"[Debugging] Error while deleting repeated products -> {e}")

    def delete_urls(self, urls: list) -> None:
        db = self.connect_db()
        c = db.cursor()

        if len(urls) == 0:
            return

        q_marks = ", ".join(["%s" for _ in range(len(urls))])
        c.execute(f"SELECT rowid FROM urls WHERE url IN ({q_marks});", urls)
        url_ids = [row[0] for row in c.fetchall()]

        c.execute(f"DELETE FROM urls WHERE rowid IN ({q_marks});", url_ids)
        c.execute(
            f"DELETE FROM products WHERE url_id IN ({q_marks});", url_ids)

        c.close()
        self.save_db(db)

    def clean_db(self) -> None:
        result = input("Are you sure you want to clean the database? (Y/n) ")
        while not result[0].lower() in ["y", "n"]:
            result = input(
                "Are you sure you want to clean the database? (Y/n) ")

        if result[0].lower() == "n":
            print("Database was not modified")
            return

        db = self.connect_db()
        c = db.cursor()

        c.execute(f"DELETE FROM urls;")
        c.execute(f"DELETE FROM products;")

        c.close()
        self.save_db(db)

        print("Database cleaned successfully")


if __name__ == "__main__":
    scraper = Scraper()
    scraper.clean_db()
