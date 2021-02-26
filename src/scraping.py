import random
import sqlite3
import csv
import ast
import time
import grequests
import concurrent.futures

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

    def get_requests(self):
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

        with sqlite3.connect(self.database) as conn:
            c = conn.cursor()

            for name, url in self.get_categories().items():
                self.add_request(url)
                c.execute("INSERT INTO categories VALUES (?, ?)", (name, url))

            # Gets all requests previously added asynchronously
            responses = self.get_requests()
            index = 1
            for response in responses:
                html = HTML(html=response.content)

                a_elements = html.xpath("//div[@class='categories']/div/div/ul[@class='items']/li/a")
                for a_el in a_elements:
                    sub_name = a_el.text
                    sub_url = MAIN_URL[:-1] + a_el.attrs["href"]

                    c.execute("INSERT INTO subcategories VALUES (?, ?, ?, ?)", (sub_name, sub_url, index, 0))
                
                index += 1
                
            conn.commit()

    def get_seller_products(self, seller, p_names, a_els, subcategory_id):
        for a_el, p_name in zip(a_els, p_names):
            if bool(a_el.attrs["data-isinstock"]) is True:
                product_id = a_el.attrs["data-productid"]
                product_name = p_name.attrs["title"]
                product_price = float(a_el.attrs["data-price"].replace(",", "."))
                product_url = MAIN_URL + a_el.attrs["href"]

                return (
                    product_id.lower(), 
                    product_name, 
                    product_price, 
                    product_url, 
                    seller, 
                    subcategory_id
                )
            else:
                return

    def subcategory_scraping(self, args):
        response = args[0]
        row = args[1]
        required_brands = args[2]

        subcategory_name = row[1]
        subcategory_url = row[2]
        subcategory_id = row[0]

        products = []

        if response is not None:
            if response.status_code == 200:
                html = HTML(html=response.content)
            else:
                print(f"[Scraper] HTTP error {response.status_code} in subcategory {subcategory_name}")
                return
        else:
            print("[Scraper] ERROR -> Response is None")
            return

        seller_els = html.xpath("//li[@class='box-container satici']/ol/li")

        sellers = []
        for el in seller_els:
            # Get sellers names
            if "title" in el.attrs:
                sellers.append(el.attrs["title"])

        brands = []
        if len(required_brands) > 0:
            brand_els = html.xpath("//li[@class='box-container brand']/ol/li")
            for el in brand_els:
                # Get brand names
                if "title" in el.attrs:
                    brand = el.attrs["title"]
                    if brand in required_brands:
                        brands.append(brand)

        # Is the URL with the selected brands added
        brand_url = MAIN_URL + "-".join(brands) + "/" + subcategory_url.split("/")[-1]
        
        if len(sellers) == 0:
            print("[Scraping] ERROR -> There are no sellers in this page")
            return

        for seller in sellers:
            seller_url = brand_url + "?filtreler=satici:" + seller
            self.add_request(seller_url)
        
        responses = self.get_requests()

        sellers_ext = []
        for seller, response in zip(sellers, responses):
            seller_url = brand_url + "?filtreler=satici:" + seller

            if response is not None:
                if response.status_code == 200:
                    html = HTML(html=response.content)
                else:
                    print(f"[Scraper] HTTP error {response.status_code} in subcategory {subcategory_name}")
                    continue
            else:
                print("[Scraper] ERROR -> Response is None")

            a_els = html.xpath("//div[@id='pagination']/ul/li/a")
            if len(a_els) > 0:
                max_pages = int(a_els[-1].attrs["class"][0].lstrip("page-"))
            else:
                max_pages = 1

            for i in range(1, min(max_pages, LIMIT)+1):
                current_url = f"{seller_url}&sayfa={i}"
                self.add_request(current_url)
                sellers_ext.append(seller)

        responses = self.get_requests()

        a_els_group = []
        p_names = []
        for response, seller in zip(sellers_ext, responses):
            if not responses[i] is None:
                if responses[i].status_code == 200:
                    html = HTML(html=responses[i].content)
                else:
                    print(f"[Scraper] HTTP error {responses[i].status_code} in subcategory {subcategory_name}")
                    continue
            else:
                print("[Scraper] ERROR -> Response is None")

            p_names.append(html.xpath("//h3[@class='product-title title']"))
            a_els_group.append(html.xpath("//div[@class='box product hb-placeholder']/a"))
        
        for seller, p_name, a_els in zip(sellers_ext, p_names, a_els_group):
            products.append(self.get_seller_products(seller, p_name, a_els, subcategory_id))
        
        return products

    def get_products(self, subcategory_ids: list, required_brands: list=[]) -> None:
        """Add products from a subcategory to the db"""

        with sqlite3.connect(self.database) as conn:
            # Gets the subcategory based on the rowid
            c = conn.cursor()
            q_marks = ", ".join(["?" for _ in range(len(subcategory_ids))])
            c.execute(f"SELECT rowid, * FROM subcategories WHERE rowid IN ({q_marks});", subcategory_ids)
            rows = c.fetchall()

            if len(rows) == 0:
                print("[Scraping] Subcategory IDs don't exist")
                return
        
        for row in rows:
            # Adding a request for each URL from the subcategories
            self.add_request(row[2])
        
        responses = self.get_requests()

        pool = Pool(processes=4)
        product_lists = pool.map(self.subcategory_scraping, zip(responses, rows, [required_brands for _ in range(len(rows))]))
        pool.close()
        pool.join()

        # with concurrent.futures.ThreadPoolExecutor() as executor:
        #     product_lists = executor.map(self.subcategory_scraping, zip(responses, rows, [required_brands for _ in range(len(rows))]))

        for product_list in product_lists:
            for product in product_list:
                if not product is None:
                    self.products.append(product)

        self.execute_queries()
        self.add_products()

    def delete_subcategories(self, subcategory_ids: list) -> None:
        with sqlite3.connect(self.database) as conn:
            c = conn.cursor()

            q_marks = ", ".join(["?" for _ in range(len(subcategory_ids))])
            c.execute(f"DELETE FROM products WHERE subcategory_id IN ({q_marks});", subcategory_ids)

            conn.commit()


def main():
    scraper = Scraper("./data/database.db")

    scraper.get_products([i for i in range(1, 8)])


if __name__ == "__main__":
    main()