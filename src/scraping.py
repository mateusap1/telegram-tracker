import random
import sqlite3
import csv
import ast
import time
import grequests

from requests_html import HTML
from bs4 import BeautifulSoup


MAIN_URL = "https://www.hepsiburada.com/"
MAX_REQUESTS = 25
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

        self.requests = []
        self.queries = []
        self.products = []
    
    def execute_queries(self) -> None:
        """Executes the queries added to the queue in order."""

        with sqlite3.connect(self.database) as conn:
            c = conn.cursor()
            for query in self.queries:
                c.execute(*query)
            conn.commit()
    
    def add_products(self) -> None:
        """Adds product if it is not already in the table"""

        with sqlite3.connect(self.database) as conn:
            c = conn.cursor()
            for product in self.products:
                product_id, product_name, product_price, product_url, seller, subcategory_id = product

                c.execute("SELECT * FROM products WHERE product_id = ? AND merchant = ?", (product_id, seller))
                if len(c.fetchall()) > 0:
                    c.execute(
                        "UPDATE products SET current_price = ? WHERE product_id = ? AND merchant = ?", 
                        (product_price, product_id, seller)
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
                            subcategory_id
                    ))
            
            conn.commit()

    def make_request(self, url: str):
        rs = (grequests.get(url, headers=HEADERS), )

        r = grequests.map(rs, size=1)

        return r[0]

    def make_requests(self):
        r = grequests.map(self.requests, size=MAX_REQUESTS)
        self.requests = []

        return r

    def add_request(self, url: str) -> None:
        self.requests.append(grequests.get(url, headers=HEADERS))

    def get_categories(self) -> dict:
        """Gets the possible categories in the main url"""

        response = self.make_request(MAIN_URL)
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

        index = 1
        for name, url in self.get_categories().items():
            with sqlite3.connect(self.database) as conn:
                c = conn.cursor()
                c.execute("INSERT INTO categories VALUES (?, ?)", (name, url))

                response = self.make_request(url)
                html = HTML(html=response.content)

                a_elements = html.xpath("//div[@class='categories']/div/div/ul[@class='items']/li/a")
                for a_el in a_elements:
                    sub_name = a_el.text
                    sub_url = MAIN_URL[:-1] + a_el.attrs["href"]

                    c.execute("INSERT INTO subcategories VALUES (?, ?, ?, ?)", (sub_name, sub_url, index, 0))
                
                conn.commit()

            index += 1

    def get_products(self, subcategory_id: int, required_brands: list=[]) -> None:
        """Add products from a subcategory to the db"""

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

        response = self.make_request(subcategory_url)
        html = HTML(html=response.content)
        seller_els = html.xpath("//li[@class='box-container satici']/ol/li")

        sellers = []
        for el in seller_els:
            if "title" in el.attrs:
                sellers.append(el.attrs["title"])

        brand_els = html.xpath("//li[@class='box-container brand']/ol/li")
        brands = []
        for el in brand_els:
            if "title" in el.attrs:
                brand = el.attrs["title"]
                if brand in required_brands:
                    brands.append(brand)

        # Is the URL with the selected brands added
        brand_url = MAIN_URL + "-".join(brands) + "/" + subcategory_url.split("/")[-1]

        def get_seller_products(seller, p_names, a_els):
            for a_el, p_name in zip(a_els, p_names):
                if bool(a_el.attrs["data-isinstock"]) is True:
                    product_id = a_el.attrs["data-productid"]
                    product_name = p_name.attrs["title"]
                    product_price = float(a_el.attrs["data-price"])
                    product_url = MAIN_URL + a_el.attrs["href"]

                    # TODO: Maybe the problem was commiting to the db every time
                    self.products.append((
                        product_id.lower(), 
                        product_name, 
                        product_price, 
                        product_url, 
                        seller, 
                        subcategory_id
                    ))
                else:
                    print("ERROR")
        
        if len(sellers) == 0:
            print("ERROR")
            return

        for seller in sellers:
            seller_url = brand_url + "?filtreler=satici:" + seller
            self.add_request(seller_url)
        
        responses = self.make_requests()

        sellers_ext = []
        for seller, response in zip(sellers, responses):
            seller_url = brand_url + "?filtreler=satici:" + seller

            html = HTML(html=response.content)

            a_els = html.xpath("//div[@id='pagination']/ul/li/a")
            if len(a_els) > 0:
                max_pages = int(a_els[-1].attrs["class"][0].lstrip("page-"))
            else:
                max_pages = 1

            for i in range(1, min(max_pages, LIMIT)+1):
                current_url = f"{seller_url}&sayfa={i}"
                self.add_request(current_url)
                sellers_ext.append(seller)

        responses = self.make_requests()

        with sqlite3.connect(self.database) as conn:
            a_els_group = []
            p_names = []
            for i, seller in enumerate(sellers_ext):
                html = HTML(html=responses[i].content)

                p_names.append(html.xpath("//h3[@class='product-title title']"))
                a_els_group.append(html.xpath("//div[@class='box product hb-placeholder']/a"))
            
            for seller, p_name, a_els in zip(sellers_ext, p_names, a_els_group):
                get_seller_products(seller, p_name, a_els)
            
        self.execute_queries()
        self.add_products()

    def delete_subcategory(self, subcategory_id: int) -> None:
        with sqlite3.connect(self.database) as conn:
            c = conn.cursor()

            c.execute("DELETE FROM products WHERE subcategory_id = ?;", (subcategory_id,))

            conn.commit()