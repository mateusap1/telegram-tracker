from requests_html import AsyncHTMLSession, HTMLSession
from requests import Response

import random
import sqlite3
import requests
import csv
import ast
import time

proxy_list = []
with open("./input/proxylist.csv", "r") as f:
    reader = csv.reader(f)
    for row in reader:
        proxy_list.append(row[0])


MAIN_URL = "https://www.hepsiburada.com/"
MAX_THREADS = 10
TIMEOUT = 3


class Scraper(object):

    def __init__(self, database: str):
        self.session = HTMLSession()
        self.asession = AsyncHTMLSession()
        self.database = database

        self.queries = []
        self.use_proxy = False
    
    def random_proxy(self):
        return random.choice(proxy_list)
    
    def set_proxy(self, proxy_candidates: list=proxy_list, verify: bool=False) -> None:
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
        if self.use_proxy is True:
            self.set_proxy()

        response = self.session.get(MAIN_URL)

        section_elements = response.html.find("section")

        if len(section_elements) == 0:
            return
        
        categories = {}
        for section_element in section_elements:
            h5_elements = section_element.find("h5")
            
            if len(h5_elements) == 0:
                continue 
        
            if h5_elements[0].text == "Kategoriler":
                category_section = section_element
                ul_element = category_section.find("ul")[0]
                li_elements = ul_element.find("li")
                for li_element in li_elements:
                    a_elements = li_element.find("a")
                    for a_element in a_elements:
                        if "href" in a_element.attrs and len(a_element.attrs["href"]) > 0:
                            categories[a_element.attrs["title"]] = a_element.attrs["href"]

        
        return categories

    def create_subcategories(self):
        if self.proxy_request is True:
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

    async def get_product(self, url: str, subcategory_id: int, brand_id: int=None) -> None:
        response = await self.asession.get(url)
        print(response.html)

        # Searching for the button that have almost all info we need
        xpath = '//button[@class="add-to-basket button small"]'
        basket_button_elements = response.html.xpath(xpath)

        if len(basket_button_elements) == 0:
            return
            
        xpath = '//div[@class="box-container loader"]'
        div_elements = response.html.xpath(xpath)

        a_elements = []

        for div in div_elements:
            a_elements = div.find("a")
            if len(a_elements) > 0:
                break

        urls = {}
        for element in a_elements:
            if not "data-productid" in element.attrs:
                continue
            
            if not "href" in element.attrs:
                continue

            urls[element.attrs["data-productid"].lower()] = MAIN_URL + element.attrs["href"][1:]
        
        for element in basket_button_elements:
            if not "data-product" in element.attrs:
                continue

            product = ast.literal_eval(element.attrs["data-product"])

            p_id = product["productId"].lower()
            p_name = product["productName"]
            p_merchant = product["merchantName"]
            p_price = product["price"]
            
            if not p_id in urls:
                continue

            p_url = urls[p_id]

            with sqlite3.connect(self.database) as conn:
                c = conn.cursor()

                query = "SELECT * FROM products WHERE product_id = ?;"
                c.execute(query, (p_id,))
                last_product = c.fetchone()
                if last_product is None:
                    self.queries.append((
                        "INSERT INTO products VALUES (?, ?, ?, ?, ?, ?, ?, ?)", (
                            p_id,
                            p_price,
                            p_price,
                            p_name,
                            p_merchant,
                            p_url,
                            subcategory_id,
                            brand_id
                    )))
                else:
                    self.queries.append((
                        "UPDATE products SET current_price = ? WHERE product_id = ?", 
                        (p_price, p_id)
                    ))

    def get_products(self, url: str, subcategory_id: int, brand_id: int=None) -> None:
        if self.use_proxy is True:
            self.set_proxy()

        response = self.session.get(url)

        xpath = "//div[@id='pagination']/ul/li/a"
        a_elements = response.html.xpath(xpath)

        max_pages = int(a_elements[-1].attrs["class"][0].lstrip("page-"))
        print(max_pages)

        run = []
        for i in range(1, max_pages+1):
            function = lambda i=i: self.get_product(f"{url}?sayfa={i}", subcategory_id, brand_id)
            
            run.append(function)
            print(function, f"{url}?sayfa={i}")

        print(run)
        self.asession.run(*run)
        
        with sqlite3.connect(self.database) as conn:
            c = conn.cursor()

            for query in self.queries:
                print(query)
                c.execute(*query)
            
            self.queries = []
            conn.commit()

    def delete_subcategory(self, subcategory_id: int) -> None:
        with sqlite3.connect(self.database) as conn:
            c = conn.cursor()

            c.execute("DELETE FROM products WHERE subcategory_id = ?", (subcategory_id,))

            conn.commit()

if __name__ == "__main__":
    # The soultion to all my problems 
    # https://stackoverflow.com/questions/452610/how-do-i-create-a-list-of-python-lambdas-in-a-list-comprehension-for-loop

    scraper = Scraper("./data/data.db")
    scraper.get_products("https://www.hepsiburada.com/iphone-ios-telefonlar-c-60005202", 6)