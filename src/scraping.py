import random
import sqlite3
import csv
import ast
import time
import requests
import concurrent.futures
import lxml.html, lxml.etree
import sys

from requests_html import HTML
from bs4 import BeautifulSoup
from multiprocessing import Pool
from itertools import product


MAIN_URL = "https://www.hepsiburada.com/"
MAX_REQUESTS = 50
TIMEOUT = 3
LIMIT = 10
HEADERS = {
    "Accept-Language": "en-US,en;q=0.5",
    "Connection": "keep-alive",
    "Referer": "https://www.hepsiburada.com/",
    "User-Agent": "Mozilla/5.0 (X11; Ubuntu; Linux x86_64; rv:85.0) Gecko/20100101 Firefox/85.0"
}


class Scraper(object):

    def __init__(self, database: str):
        self.database = database

        self.session = requests.session()
        self.queries = []
        self.products = []
    
    def add_products(self) -> None:
        """Adds product if it is not already in the table"""

        with sqlite3.connect(self.database) as conn:
            c = conn.cursor()

            products = self.products.copy()
            self.products = []

            for product in products:
                product_id, listing_id, product_name, product_price, product_url, seller, subcategory_id = product

                c.execute("SELECT * FROM products WHERE product_id = ?", (product_id, ))
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
                            subcategory_id
                    ))
            
            conn.commit()

    def get_categories(self) -> dict:
        """Gets the possible categories in the main url"""

        response = requests.get(MAIN_URL, headers=HEADERS)
        soup = BeautifulSoup(response.content, "html.parser")

        section_elements = soup.find_all("section")

        if len(section_elements) == 0:
            return None
        
        categories = {}
        for section_element in section_elements:
            h5_elements = section_element.find_all("h5")
            
            if len(h5_elements) == 0:
                continue 
        
            if h5_elements[0].text == "Kategoriler":
                # Finds the h5 element with text "Categories" and gets the URLs
                category_section = section_element

                ul_element = category_section.find_all("ul")[0]
                li_elements = ul_element.find_all("li")
                for li_element in li_elements:
                    a_elements = li_element.find_all("a")
                    for a_element in a_elements:
                        if "href" in a_element.attrs and len(a_element.attrs["href"]) > 0:
                            categories[a_element.attrs["title"]] = a_element.attrs["href"]

        
        return categories

    def create_subcategories(self) -> None:
        """Finds subcategories based on each category URL."""

        with sqlite3.connect(self.database) as conn:
            c = conn.cursor()

            index = 1
            for name, url in self.get_categories().items():
                c.execute("INSERT INTO categories VALUES (?, ?)", (name, url))

                response = requests.get(url, headers=HEADERS)
                html = lxml.html.fromstring(response.content)

                a_elements = html.xpath("//div[@class='categories']/div/div/ul[@class='items']/li/a")
                li_elements = html.xpath("//ul[@class='items']/li[@class='main-item noSub']")
                for a_el, li_el in zip(a_elements, li_elements):
                    sub_name = li_el.get("title")
                    sub_url = MAIN_URL[:-1] + a_el.get("href")

                    c.execute("INSERT INTO subcategories VALUES (?, ?, ?, ?)", (sub_name, sub_url, index, 0))
                    
                index += 1
                
            conn.commit()

    def subcategory_scraping(self, args):
        try:
            row = args[0]
            brands = args[1]
            products = []

            subcategory_id = row[0]
            subcategory_name = row[1]
            subcategory_url = row[2]

            print(f"[Scraper] Subcategory \"{subcategory_name}\" is being scraped...")

            # Is the URL with the selected brands added
            brand_url = MAIN_URL + "-".join(brands) + "/" + subcategory_url.split("/")[-1]

            response = requests.get(brand_url, headers=HEADERS)

            if response is not None:
                if response.status_code == 200:
                    html = lxml.html.fromstring(response.content)
                else:
                    print(f"[Scraper] HTTP error {response.status_code} in subcategory {subcategory_name}")
                    return
            else:
                print("[Scraper] ERROR -> Response is None")
                return

            pages_el = html.xpath("//div[@id='pagination']/ul/li/a")
            if len(pages_el) > 0:
                page_limit = int(pages_el[-1].text) # The number of different product pages
            else:
                page_limit = 1

            for i in range(1, page_limit+1):
                url = brand_url + f"?sayfa={i}"

                response = requests.get(url, headers=HEADERS)

                if not response is None:
                    if response.status_code == 200:
                        html = lxml.html.fromstring(response.content)
                    else:
                        print(f"[Scraper] HTTP error {response.status_code} in subcategory {subcategory_name}")
                        continue
                else:
                    print("[Scraper] ERROR -> Response is None")

                # Get the product name
                p_names = html.xpath(".//h3[@class='product-title title']")

                # Get the product info
                a_els = html.xpath(".//a[@data-isinstock='True']")

                button_els = html.xpath(".//button[@class='add-to-basket button small']")
                
                j = 0
                for p_name, a_el in zip(p_names, a_els):
                    if len(button_els) == len(a_els) == len(p_names):
                        product_info = ast.literal_eval(button_els[j].get("data-product"))
                        seller = product_info["merchantName"]
                        product_price = float(product_info["price"])
                    else:
                        seller = None
                        product_price = float(a_el.get("data-price").replace(",", "."))

                    listing_id = a_el.get("data-listing_id").lower()
                    product_id = a_el.get("data-productid").lower()

                    product_url = MAIN_URL + a_el.get("href")
                    product_name = p_name.get("title")

                    self.products.append((
                        product_id, 
                        listing_id,
                        product_name, 
                        product_price, 
                        product_url, 
                        seller, 
                        subcategory_id
                    ))

                    j += 1
                
            print(f"[Scraper] Subcategory \"{subcategory_name}\" was successfuly scraped...")
                
            return products

        except Exception as e:
            print(f"[Scraper] Error while scraping subcategory -> \"{e}\"")

    def get_products(self, unused) -> None:
        """Add products from a subcategory to the db"""

        # Argument `unused` has no real value
        start = time.time()

        with sqlite3.connect(self.database) as conn:
            c = conn.cursor()

            c.execute("SELECT rowid, * FROM subcategories WHERE ADDED = 1;")
            subc_rows = c.fetchall()

            c.execute("SELECT * FROM brands")
            brand_rows = c.fetchall()

            if len(subc_rows) == 0:
                return
        
        required_brands = [row[0] for row in brand_rows]
        args = zip(subc_rows, [required_brands for _ in range(len(subc_rows))])


        with concurrent.futures.ThreadPoolExecutor() as executor:
            executor.map(self.subcategory_scraping, args)

        end = time.time()
        print(f"[Scraper] Cycle completed successfuly in {end - start} seconds.")

    def get_product_info(self, url: str) -> dict:
        response = requests.get(url, headers=HEADERS)

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

    def add_subcategories(self, subcategory_ids: list) -> None:
        with sqlite3.connect(self.database) as conn:
            c = conn.cursor()

            q_marks = ", ".join(["?" for _ in range(len(subcategory_ids))])
            c.execute(f"UPDATE subcategories SET added = 1 WHERE rowid IN ({q_marks});", subcategory_ids)

            conn.commit()

    def delete_subcategories(self, subcategory_ids: list) -> None:
        with sqlite3.connect(self.database) as conn:
            c = conn.cursor()

            q_marks = ", ".join(["?" for _ in range(len(subcategory_ids))])
            c.execute(f"DELETE FROM products WHERE subcategory_id IN ({q_marks});", subcategory_ids)
            c.execute(f"UPDATE subcategories SET added = 0 WHERE rowid IN ({q_marks});", subcategory_ids)

            conn.commit()


if __name__ == "__main__":
    scraper = Scraper("./data/database.db")
    # scraper.add_subcategories([i for i in range(1, 31)])
    # scraper.delete_subcategories([i for i in range(1, 150)])
    # scraper.create_subcategories()