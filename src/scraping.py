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
    
    def execute_queries(self):
        with sqlite3.connect(self.database) as conn:
            c = conn.cursor()
            for query in self.queries:
                c.execute(*query)
            conn.commit()
    
    def random_proxy(self) -> str:
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

    def create_subcategories(self) -> None:
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

    def get_product_info(self, url: str, subcategory_id: int, brand_id: int=None, repeated_product: bool=False) -> None:
        response = self.asession.get(url)
        await response.html.arender()

        els_seller_names = response.html.xpath("//a[@class='merchant-name small']")
        els_seller_prices = response.html.xpath("//span[@class='price product-price']")
        els_variant_names = response.html.xpath("//span[@class='variant-name']")
        els_variant_prices = response.html.xpath("//span[@class='variant-property-price']")
        els_current_seller = response.html.xpath("//span[@class='seller']")
        els_current_price = response.html.xpath("//span[@id='offering-price']")
        els_product_name = response.html.xpath("//h1[@id='product-name']")

        seller_names = [el.text for el in els_seller_names]
        seller_prices = [el.text for el in els_seller_prices]
        variant_names = [el.text for el in els_variant_names]
        variant_prices = [el.text for el in els_variant_prices]

        product_id = url.split("-")[-1].lower()
        
        if len(els_product_name) <= 0:
            return

        product_name = els_product_name.text[0]
            
        for seller_name, seller_price in zip(seller_names, seller_prices):
            if repeated_product is False:
                self.queries.append(
                    "INSERT INTO products VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)", (
                    product_id,
                    seller_price,
                    seller_price,
                    product_name,
                    seller_name,
                    variant_names,
                    url,
                    subcategory_id,
                    brand_id
                ))
            elif repeated_product is True:
                self.queries.append(
                    "UPDATE products SET current_price = ? WHERE product_id = ?", (
                    seller_price,
                    product_id
                ))
        
        if len(seller_names) == 0:
            if len(els_current_seller) > 0:
                current_seller = els_current_seller[0].text.lstrip("Satıcı:")
            if len(els_current_price) > 0:
                current_price = float(els_current_price[0].text. \
                    rstrip("TL").replace(".", "").replace(",", "."))
        
        if current_price is not None and current_seller is not None:
            if repeated_product is False:
                self.queries.append(
                    "INSERT INTO products VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)", (
                    product_id,
                    current_price,
                    current_price,
                    product_name,
                    current_seller,
                    variant_names,
                    url,
                    subcategory_id,
                    brand_id
                ))
            elif repeated_product is True:
                self.queries.append(
                    "UPDATE products SET current_price = ? WHERE product_id = ?", (
                    current_price,
                    product_id
                ))

    def get_product(self, url: str, subcategory_id: int, brand_id: int=None) -> None:
        response = self.session.get(url)

        xpath = "//div[@class='box-container loader']"
        div_elements = response.html.xpath(xpath)

        a_elements = []

        for div in div_elements:
            a_elements = div.find("a")
            if len(a_elements) > 0:
                break

        urls = []
        for element in a_elements:            
            if not "href" in element.attrs:
                continue

            urls.append(MAIN_URL + element.attrs["href"][1:])
        
        if len(urls) > 0:
            run = []
            for current_url in urls:
                f = lambda current_url=current_url: self.get_product_info(current_url, subcategory_id, brand_id)
                
                run.append(f)
            
            print(run)
            self.asession.run(*run)


    def get_products(self, url: str, subcategory_id: int, brand_id: int=None) -> None:
        if self.use_proxy is True:
            self.set_proxy()

        response = self.session.get(url)

        xpath = "//div[@id='pagination']/ul/li/a"
        a_elements = response.html.xpath(xpath)

        max_pages = int(a_elements[-1].attrs["class"][0].lstrip("page-"))
        print(max_pages)

        for i in range(1, max_pages+1):
            self.get_product(f"{url}?sayfa={i}", subcategory_id, brand_id)
        
        self.execute_queries()

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