import random
import urllib
import math
import sys
import os
import re
import time
import json
import requests
import concurrent.futures
import lxml.html
import datetime
import configparser
import mysql.connector

config = configparser.ConfigParser()
config.read("./config.ini")

MAX_THREADS = config.getint("DEFAULT", "threads")
BOT_MODE = config.get("DEFAULT", "mode").lower()

if not BOT_MODE in ("scrape", "compare", "scrape-compare"):
    print("[Error] You must provide a valid mode")
    print("Valid modes: \"scrape\", \"compare\" and \"scrape-compare\"")
    sys.exit(1)

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
DB_NAME = config.get("DATABASE", "name")

if DB_PASSWORD[0] == "$":
    DB_PASSWORD = os.getenv(DB_PASSWORD[1:])

MAIN_URL = "http://www.hepsiburada.com/"
INFINIT = 10 ** 6

with open("./ua.txt", "r") as f:
    user_agent_list = f.read().split("\n")


class Scraper(object):

    def __init__(self):
        self.mode = None
        self.new_products = []
        self.url_rows = []

        self.update_headers()
        self.proxies = None

        if PROXY is not None:
            self.proxies = {
                "http": PROXY,
                "https": PROXY
            }

    def update_headers(self):
        """Update or add the headers in such a way that the website thinks we're 
        in a Browser and that it doesn't return cached data"""

        self.headers = {
            "User-Agent": random.choice(user_agent_list),
            "cache-control": "private, max-age=0, no-cache",
            "Pragma": "no-cache"
        }

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

    def parse_data(self, response):
        """Parse the data into an lxml.html object. 
        Returns None, if there was any error"""

        if response is not None:  # If the response is valid
            if response.status_code == 200:  # If we received a success status
                return lxml.html.fromstring(response.content)
            else:  # If not, display an error in the terminal and return None
                print(
                    f"[Debugging] HTTP error {response.status_code}")
                return None
        else:  # If there was no response given, display an error and return None
            print("[Debugging] Error while parsing data -> Response is None")
            return None

    def get_product_info(self, url: str) -> dict:
        """Returns the price and the seller name of a product based on the URL given"""

        self.update_headers()
        response = requests.get(
            url, headers=self.headers, proxies=self.proxies)
        html = self.parse_data(response)
        if html is None:
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

    def page_scraping(self, url: str, page_type: str, url_id: int) -> list:
        """Get all products in the URL specified and save it 
        into the DB, as well as, return it's information"""

        if page_type is None:
            print(
                f"[Debugging] Error while scraping the page {url} -> No page type provided")
            return None

        response = requests.get(
            url,
            headers=self.headers,
            proxies=self.proxies,
            timeout=TIMEOUT
        )

        html = self.parse_data(response)
        if html is None:
            print(
                f"[Debugging] Error while scraping the page {url} -> HTML parisng failed")
            return None

        # Get the product name
        p_names = html.xpath("//h3[@class='product-title title']")

        # Get the product info
        a_els = html.xpath("//a[@data-isinstock='True']")

        products = []  # The list containing all products information

        if page_type == "AJAX":
            # Get the <script /> element that has all products data stored
            els = html.xpath(
                "//div[@class='product-list']/div[@class='voltran-fragment']\
                    /div/div/script[@type='text/javascript']")

            if len(els) == 0:  # If no products were found, return an empty list
                return []

            # Filter the data inside <script />
            data = els[0].text_content()
            data = data.strip()
            data = data.lstrip("window.MORIA = window.MORIA || \{\};")
            data = data.strip()
            data = data.lstrip(
                "window.MORIA = window.MORIA.ProductList = ")
            data = data.replace("'", "\"", 2)

            # Transform the filtered data into a JSON string
            data = json.loads(data.strip())

            db = self.connect_db()
            c = db.cursor()

            # Access `products` inside the JSON string
            products = data["STATE"]["data"]["products"]

            for product in products:  # For each dictionary containing a product information
                # For each variant of this product
                for variant in product["variantList"]:
                    # The dictionary where this variants information will be stored
                    info = {}

                    # Get the current date, so we can know when this price was scraped
                    info["date"] = str(datetime.datetime.now())

                    # Get this variants listing ID
                    info["listing_id"] = variant["listing"]["listingId"].lower()

                    # The rowid should be unique to each product, because of this,
                    # it's a concatanation between the date and the listing_id
                    info["rowid"] = hash(info["date"] + info["listing_id"])

                    # Get the product ID
                    info["product_id"] = variant["sku"].lower()

                    # Get the name of this product
                    info["name"] = variant["name"]

                    # Get the seller of this variation name
                    info["seller"] = variant["listing"]["merchantName"]

                    # Get the URL of this product
                    info["product_url"] = variant["url"]

                    # Get the price of this variation
                    info["price"] = float(
                        variant["listing"]["priceInfo"]["price"])
                    
                    info["url_id"] = url_id

                    db = self.connect_db()
                    c = db.cursor()

                    c.execute("""
                        INSERT INTO temp_products 
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s);
                    """, (
                        info["rowid"],
                        info["date"],
                        info["listing_id"],
                        info["product_id"],
                        info["name"],
                        info["seller"],
                        info["price"],
                        info["product_url"],
                        info["url_id"]
                    ))

                    products.append(info)

                    c.close()
                    self.save_db(db)

        elif page_type == "normal":
            # Get all possible <script /> elements
            script_els = html.xpath("//script[@type='text/javascript']")

            # If no <script /> elements were found, return an empty list
            if len(script_els) == 0:
                return []

            data = None  # The json string that will contain the products data

            # Go over each of the script elements and try to find the JS variable there
            for el in script_els:
                # If we can find the variable, get store the information
                if "var utagData" in el.text_content():
                    # Filter the data inside <script />
                    data = el.text_content()
                    data = data.strip()
                    data = data.split("\n")[0]
                    data = data.strip()
                    data = data.lstrip("var utagData = ")
                    data = data.rstrip(";")

                    # Transform the filtered data into a JSON string
                    data = json.loads(data.strip())

                    break

            if data is None:  # If no variable was found, return None
                print(
                    f"[Debugging] Error while scraping the page {url} ->" +
                    "No variable \"utagData\" was found"
                )

                return None

            names = data["product_names"]
            prices = data["product_prices"]
            sellers = data["merchant_names"]
            listing_ids = data["listing_ids"]

            # Product skus is what we call "product_id" in the database
            product_skus = data["product_skus"]

            # We need this info so we can get the product URL
            product_ids = data["product_ids"]

            for i in range(len(names)):
                # The dictionary where this variants information will be stored
                info = {}

                # Get the current date, so we can know when this price was scraped
                info["date"] = str(datetime.datetime.now())

                # Get this variants listing ID
                info["listing_id"] = listing_ids[i].lower()

                # The rowid should be unique to each product, because of this,
                # it's a concatanation between the date and the listing_id
                info["rowid"] = hash(info["date"] + info["listing_id"])

                # Get the product ID
                info["product_id"] = product_skus[i].lower()

                # Get the name of this product
                info["name"] = names[i]

                info["price"] = float(prices[i])

                # Get the seller of this variation name
                info["seller"] = sellers[i]

                # Get the URL of this product, which is: the hepsiburada main URL plus
                # the name of the product in lowercase with hifens instead of spaces plus
                # "-p-<product_id>" in the end
                info["product_url"] = "https://www.hepsiburada.com/"
                
                info["url_id"] = url_id

                db = self.connect_db()
                c = db.cursor()

                c.execute("""
                    INSERT INTO temp_products 
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s);
                """, (
                    info["rowid"],
                    info["date"],
                    info["listing_id"],
                    info["product_id"],
                    info["name"],
                    info["seller"],
                    info["price"],
                    info["product_url"],
                    info["url_id"]
                ))

                products.append(info)

                c.close()
                self.save_db(db)

        # If the page type is neither "AJAX" nor "normal", return None indicating an error
        else:
            print(
                f"[Debugging] Error while scraping the page {url} -> Page type invalid")
            return None

        return products

    def url_scraping(self, row):
        """Based on a given URL, adds the products data to the database of every page it can find"""

        url_id = row[0]
        url = row[1]

        try:
            start = time.time()

            print(f"[Scraper] URL {url} is being scraped...")

            self.update_headers()

            # Get the content of the URL we were given
            response = requests.get(
                url,
                headers=self.headers,
                proxies=self.proxies,
                timeout=TIMEOUT
            )

            html = self.parse_data(response)
            if html is None:
                return None

            # NUmber of products in total if we are in an AJAX page
            pages_els = html.xpath(
                "//div[@class='paginatorStyle-root']/div[@class='paginatorStyle-label']")

            page_type = None  # If our page type AJAX or normal

            if len(pages_els) > 0:  # If we are in an AJAX page
                # Change our page type
                page_type = "AJAX"

                # Filter the content to get only two number
                el = pages_els[0].text_content().strip()
                el = el.lstrip("Toplam")
                el = el.replace("<!---->", "")
                el = el.rstrip("ürün")
                el = el.strip()

                # The first number is the number of products in the
                # first page and the second, the number of products in total
                nums = [int(i) for i in el.split("/")]

                # Get the page limit by dividing the number of
                # products in the first page by the total number
                page_limit = math.ceil(nums[1]/nums[0])
            else:  # If we are in a normal page
                # Change our page type
                page_type = "normal"

                # Gets all the possible pages in the catalog
                pages_el = html.xpath("//div[@id='pagination']/ul/li/a")

                # If there's no such element, we are in a single page catalog
                if len(pages_el) == 0:
                    page_limit = 1
                else:  # Otherwise, get the number of different pages
                    page_limit = int(pages_el[-1].text)

            # For each of the possible pages, get the products info and add them to the db
            for i in range(1, page_limit+1):
                # If we've reached our timeout, return
                if (time.time() - start) > (TIMEOUT_THREADS * page_limit):
                    print(f"[Debugging] Timeout reached on URL {url}")
                    return

                # If we already have an argument in the URL,
                # we should use '&', otherwise use '?'
                mark = "?" if not "?" in url else "&"

                # The current page URL
                current_url = url + f"{mark}sayfa={i}"

                info = self.page_scraping(current_url, url_id, page_type)

            db = self.connect_db()
            c = db.cursor()

            # Make the db know that we completed one more cycle with this URL
            c.execute(
                "UPDATE urls SET cycle = cycle + 1 WHERE rowid = %s;", (url_id, ))

            c.close()
            self.save_db(db)

            print(f"[Scraper] URL {url} was successfully scraped")

        except Exception as e:
            print(
                f"[Debugging] Error {e.__class__} while scraping URL {url} -> \"{e}\"")

    def get_products(self, _=None) -> None:
        """Add products from an URL to the db"""

        try:
            start = time.time()

            db = self.connect_db()
            c = db.cursor()

            c.execute("SELECT * FROM urls;")
            url_rows = c.fetchall()

            c.close()
            self.save_db(db)

            if len(url_rows) == 0:
                print("[Debugging] No URLs to scrape")
                return

            if PROXY is not None:
                print(f"[Debugging] Scraping with proxy {PROXY}...")
            else:
                print(f"[Debugging] Scraping with no proxy...")

            if BOT_MODE == "scrape":
                threads = MAX_THREADS
            else:
                threads = max(int((3 * MAX_THREADS) / 4), 1)

            with concurrent.futures.ThreadPoolExecutor(max_workers=threads) as executor:
                executor.map(self.url_scraping, url_rows)

            # self.delete_repeated()

            end = time.time()
            print(
                f"[Scraper] Cycle completed successfully in {end - start} seconds")
        except Exception as e:
            print(f"[Debugging] Error while scraping URLs -> {e}")

    def delete_repeated(self) -> None:
        print("[Bot] Deleting repeated rows...")

        try:
            db = self.connect_db()
            c = db.cursor()

            c.execute("""
                DELETE FROM products 
                WHERE rowid IN (
                    SELECT product_rowid 
                    FROM deleted
                    WHERE table_name = 'products'
                );
            """)

            c.execute("""
                DELETE FROM temp_products 
                WHERE rowid IN (
                    SELECT product_rowid 
                    FROM deleted
                    WHERE table_name = 'temp_products'
                );
            """)

            c.execute("""
                DELETE FROM deleted;
            """)

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
        c.execute(f"""
            DELETE FROM deleted 
            WHERE product_rowid IN (
                SELECT rowid 
                FROM products 
                WHERE url_id IN (
                    {q_marks}
                )
            );
        """, url_ids)
        c.execute(
            f"DELETE FROM products WHERE url_id IN ({q_marks});", url_ids)
        c.execute(
            f"DELETE FROM temp_products WHERE url_id IN ({q_marks});", url_ids)

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

        c.execute("DELETE FROM urls;")
        c.execute("DELETE FROM products;")
        c.execute("DELETE FROM temp_products;")
        c.execute("DELETE FROM deleted;")

        c.close()
        self.save_db(db)

        print("Database cleaned successfully")


if __name__ == "__main__":
    scraper = Scraper()
    # scraper.clean_db()

    url = "https://www.hepsiburada.com/jbl/bluetooth-hoparlorler-c-60004557"
    print(scraper.page_scraping(url, "normal", 1))
