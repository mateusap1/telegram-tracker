from requests_html import HTMLSession, AsyncHTMLSession
from requests import Response

import random
import sqlite3
import requests
import csv
import ast
import time
import asyncio


proxy_list = []
with open("./input/proxylist.csv", "r") as f:
    reader = csv.reader(f)
    for row in reader:
        proxy_list.append(row[0])


MAIN_URL = "https://www.hepsiburada.com/"
MAX_THREADS = 15
TIMEOUT = 3
LIMIT = 10


class Scraper(object):

    def __init__(self, database: str):
        self.session = requests.session()
        self.database = database

        self.queries = []
        self.products = []
        self.use_proxy = False
    
    def execute_queries(self):
        """Executes the queries added to the queue in order."""

        with sqlite3.connect(self.database) as conn:
            c = conn.cursor()
            for query in self.queries:
                c.execute(*query)
            conn.commit()
    
    def add_products(self):
        """Adds product if it is not already in the table"""

        with sqlite3.connect(self.database) as conn:
            c = conn.cursor()
            for product in self.products:
                product_id, product_price, product_url, subcategory_id = product

                c.execute("SELECT * FROM product WHERE product_id = ?", (product_id, ))
                if len(c.fetchall()) > 0:
                    c.execute(
                        "UPDATE products SET current_price = ? WHERE product_id = ?", 
                        (product_price, product_id)
                    )
                else:
                    c.execute(
                        "INSERT INTO products VALUES (?, ?, ?, ?, ?)", (
                            product_id, 
                            product_price,
                            product_price,
                            product_url,
                            subcategory_id
                    ))

    async def request(self, url):
        r = await self.session.get(url)
        return r

    def random_proxy(self) -> str:
        """Returns a random proxy."""

        return random.choice(proxy_list)
    
    def set_proxy(self, proxy_candidates: list=proxy_list, verify: bool=False) -> dict:
        """
        Configure the session to use one of the proxy_candidates. If verify is
        True, then the proxy will have been verified to work.
        """

        while True:
            proxy = random.choice(proxy_candidates)
            self.session.proxies = {"https": proxy, "http": proxy}
            self.asession.proxies = {"https": proxy, "http": proxy}

            if not verify:
                return
            try:
                print(self.session.get('https://httpbin.org/ip', timeout=3).json())
                return
            except Exception:
                print("Error")
                pass

    def get_categories(self) -> dict:
        """Gets the possible categories in the main url"""

        if self.use_proxy is True:
            self.set_proxy()

        response = self.session.get(MAIN_URL)

        section_elements = response.html.find("section")

        if len(section_elements) == 0:
            return None
        
        categories = {}
        for section_element in section_elements:
            h5_elements = section_element.find("h5")
            
            if len(h5_elements) == 0:
                continue 
        
            if h5_elements[0].text == "Kategoriler":
                # Finds the h5 element with text "Categories" and gets the URLs
                category_section = section_element

                ul_element = category_section.find("ul")[0]
                li_elements = ul_element.find("li")
                for li_element in li_elements:
                    a_elements = li_element.find("a")
                    for a_element in a_elements:
                        if "href" in a_element.attrs and len(a_element.attrs["href"]) > 0:
                            categories[a_element.attrs["title"]] = a_element.attrs["href"]

        
        return categories

    def create_subcategories(self) -> None:
        """Finds subcategories based on each category URL."""

        if self.use_proxy is True:
            self.set_proxy()

        index = 1
        for name, url in self.get_categories().items():
            with sqlite3.connect(self.database) as conn:
                c = conn.cursor()
                c.execute("INSERT INTO categories VALUES (?, ?)", (name, url))

                response = self.session.get(url)

                a_elements = response.html.xpath("//div[@class='categories']/div/div/ul[@class='items']/li/a")
                for a_el in a_elements:
                    sub_name = a_el.text
                    sub_url = MAIN_URL[:-1] + a_el.attrs["href"]

                    c.execute("INSERT INTO subcategories VALUES (?, ?, ?)", (sub_name, sub_url, index))
                
                conn.commit()

            index += 1

    def get_products(self, subcategory_id: int, required_brands: list=[]) -> None:
        if self.use_proxy is True:
            self.set_proxy()
        
        print(subcategory_id)
        with sqlite3.connect(self.database) as conn:
            # Gets the subcategory based on the rowid
            c = conn.cursor()
            c.execute("SELECT * FROM subcategories where rowid = ?;", (subcategory_id,))
            row = c.fetchone()

            if row is None:
                print("ERROR")
                return

            subcategory_url = row[1]
            conn.commit()

        response = self.session.get(subcategory_url, timeout=TIMEOUT)
        seller_els = response.html.xpath("//li[@class='box-container satici']/ol/li")

        sellers = []
        for el in seller_els:
            if "title" in el.attrs:
                sellers.append(el.attrs["title"])

        brand_els = response.html.xpath("//li[@class='box-container brand']/ol/li")
        brands = []
        for el in brand_els:
            if "title" in el.attrs:
                brand = el.attrs["title"]
                if brand in required_brands:
                    brands.append(brand)

        # Is the URL with the selected brands added
        brand_url = MAIN_URL + "-".join(brands) + "/" + subcategory_url.split("/")[-1]

        async def get_seller_products(seller):
            seller_url = brand_url + "?filtreler=satici:" + seller

            response = await self.asession.get(seller_url, timeout=TIMEOUT)

            a_els = response.html.xpath("//div[@id='pagination']/ul/li/a")
            max_pages = int(a_els[-1].attrs["class"][0].lstrip("page-"))

            print(max_pages)
            for i in range(1, min(max_pages, LIMIT)+1):
                current_url = f"{seller_url}&sayfa={i}"

                response = self.asession.get(current_url, timeout=TIMEOUT)

                a_els = response.html.xpath("//ul[@class='product-list']/li/div/a")
                for el in a_els:
                    if bool(el.attrs["data-isinstock"]) is True:
                        product_id = el.attrs["data-productid"]
                        product_price = float(el.attrs["data-price"])
                        product_url = MAIN_URL + el.attrs["href"]

                        for brand in brands:
                            self.queries.append((
                                "INSERT INTO brands VALUES (?, ?)",
                                (brand, product_id)
                            ))
                        
                        self.products.append((product_id, product_price, product_url, subcategory_id))
        
        if len(sellers) == 0:
            print("ERROR")
            return

        loop = asyncio.get_event_loop()
        tasks = [get_seller_products(seller) for seller in sellers]
        loop.run_until_complete(asyncio.wait(tasks))

        self.execute_queries()
        self.add_products()

    def delete_subcategory(self, subcategory_id: int) -> None:
        with sqlite3.connect(self.database) as conn:
            c = conn.cursor()

            c.execute("DELETE FROM products WHERE subcategory_id = ?", (subcategory_id,))

            conn.commit()

def main():
    # TODO: Keep in the database url, initial price and current price. And when
    # the program is triggered, check additional information in the url

    url = "https://www.hepsiburada.com/fotograf-makinesi-aksesuarlari-c-60000190"

    scraper = Scraper("./data/data.db")
    # scraper.create_subcategories()
    
    start = time.time()
    scraper.get_products(2, ["HP"])
    print(time.time() - start)


if __name__ == "__main__":
    main()