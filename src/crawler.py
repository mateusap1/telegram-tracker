from fake_useragent import UserAgent
from time import sleep
from urllib.parse import urlparse
from requests_html import AsyncHTMLSession

import random
import sqlite3
import requests
from requests import Response
import re
import csv
import ast
import time

proxy_list = []
with open("./input/proxylist.csv", "r") as f:
    reader = csv.reader(f)
    for row in reader:
        proxy_list.append(row[0])

ua = UserAgent()
MAIN_URL = "https://www.hepsiburada.com/"
MAX_THREADS = 10


class Crawler(object):

    def __init__(self, database: str):
        self.session = AsyncHTMLSession
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

            if not verify:
                return
            try:
                print(self.session.get('https://httpbin.org/ip', timeout=3).json())
                return
            except Exception:
                print("Error")
                pass

    async def crawl(self, url: str) -> Response:
        if self.use_proxy is True:
            self.session.headers = {"User-Agent", ua.random}
            self.set_proxy()

            while True:
                try:
                    response = await self.session.get(url, timeout=3)
                    break
                except requests.exceptions.RequestException as e:
                    print(e)

                    # self.session.headers = {'User-Agent': ua.random}
                    self.set_proxy(verify=True)
                    sleep(0.1)
        else:
            try:
                response = self.session.get(url, timeout=3)
            except requests.exceptions.RequestException as e:
                print(e)
                return None
        
        if response.status_code == 200:
            return response
        else:
            print(response.status_code)
            return None
        
    async def get_categories(self) -> dict:
        response = await self.crawl(MAIN_URL)

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
    
    async def create_subcategory(self, name: str, url: str, index: int) -> None:
        self.queries.append(("INSERT INTO categories VALUES (?, ?)", (name, url)))

        response = await self.crawl(url)

        a_elements = response.html.xpath("//div[@class='categories']/div/div/ul[@class='items']/li/a")
        for a_el in a_elements:
            sub_name = a_el.text
            sub_url = MAIN_URL[:-1] + a_el.attrs["href"]

            self.queries.append(("INSERT INTO subcategories VALUES (?, ?, ?)", (sub_name, sub_url, index)))

    def create_subcategories(self):
        threads = []
        index = 1
        for name, url in self.get_categories().items():
            if len(threads) == MAX_THREADS:
                for t in threads:
                    t.join()
                threads = []

            thread = threading.Thread(
                target = self.create_subcategory, 
                args=(name, url, index)
            )
            thread.start()
            threads.append(thread)

            index += 1
        
        # Wait for the remaining threads
        for t in threads:
            t.join()
        
        with sqlite3.connect(self.database) as conn:
            c = conn.cursor()

            for query in self.queries:
                c.execute(*query)
            
            self.queries = []
            conn.commit()

    def get_product(self, url: str, subcategory_id: int, brand_id: int=None) -> None:
        # Getting the response from the url
        response = self.crawl(url)

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

    def get_products(self, url: str, subcategory_id: int, brand_id: int=None, limit: int=10) -> None:
        # Getting the response from the url
        response = self.crawl(url)

        xpath = "//div[@id='pagination']/ul/li/a"
        a_elements = response.html.xpath(xpath)

        max_pages = int(a_elements[-1].attrs["class"][0].lstrip("page-"))

        threads = []
        for i in range(1, max_pages+1):
            if i > 1:
                current_url = f"{url}?sayfa={i}"
            else:
                current_url = url

            print(current_url)
            if len(threads) == MAX_THREADS:
                for t in threads:
                    t.join()
                threads = []

            thread = threading.Thread(
                target = self.get_product, 
                args=(current_url, subcategory_id, brand_id)
            )
            thread.start()
            threads.append(thread)
        
        # Wait for the remaining threads
        for t in threads:
            t.join()
        
        with sqlite3.connect(self.database) as conn:
            c = conn.cursor()

            for query in self.queries:
                c.execute(*query)
                
            self.queries = []
            conn.commit()

    def delete_subcategory(self, subcategory_id: int) -> None:
        with sqlite3.connect(self.database) as conn:
            c = conn.cursor()

            c.execute("DELETE FROM products WHERE subcategory_id = ?", (subcategory_id,))

            conn.commit()

def main():
    # TODO: Keep in the database url, initial price and current price. And when
    # the program is triggered, check additional information in the url

    url = "https://www.hepsiburada.com/fotograf-makinesi-aksesuarlari-c-60000190"

    crawler = Crawler("./data/data.db")
    crawler.delete_subcategory(21)
    # crawler.create_subcategories()
    
    # start = time.time()
    # crawler.get_products(url, 21)
    # print(time.time() - start)


if __name__ == "__main__":
    main()
