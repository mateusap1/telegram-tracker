import ast
import time

from requests_html import HTMLSession


class Scraper(object):

    def __init__(self):
        self.url = "https://www.hepsiburada.com/"
    
    def get_categories(self):
        try:
            session = HTMLSession()
            response = session.get(self.url)
        except requests.exceptions.RequestException as e:
            print(e)
            return None

        if response.status_code != 200:
            return None

        section_elements = response.html.find("section")

        if len(section_elements) == 0:
            return None
        
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
                        if "href" in a_element.attrs:
                            categories[a_element.attrs["title"]] = a_element.attrs["href"]

        
        return categories
    
    def get_products(self, product_url, limit=10):
        products = {}
        for i in range(1, limit+1):
            url = product_url + f"?sayfa={i}"

            try:
                session = HTMLSession()
                response = session.get(url)
            except requests.exceptions.RequestException as e:
                print(e)
                return None

            if response.status_code != 200:
                return None

            xpath = '//button[@class="add-to-basket button small"]'
            basket_button_elements = response.html.xpath(xpath)

            if len(basket_button_elements) == 0:
                break
                
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

                urls[element.attrs["data-productid"].upper()] = self.url + element.attrs["href"][1:]
            
            for element in basket_button_elements:
                if not "data-product" in element.attrs:
                    print("data-product not found")
                    continue

                product = ast.literal_eval(element.attrs["data-product"])
                
                if not product["productId"] in urls:
                    # print("productId not found")
                    continue
                    
                if not "productName" in product:
                    print("productName not found")
                    continue

                if not "merchantName" in product:
                    print("merchantName not found")
                    continue

                if not "price" in product:
                    print("price not found")
                    continue
                    
                products[product["productId"]] = {
                    "product_name": product["productName"],
                    "merchant": product["merchantName"],
                    "price": product["price"],
                    "url": urls[product["productId"]]
                }
            
        return products
    
    def get_current_price(self, url):
        try:
            session = HTMLSession()
            response = session.get(url)
        except requests.exceptions.RequestException as e:
            print(e)
            return None

        if response.status_code != 200:
            return None
        
        # It gets the lyrics
        current_price_element = response.html.xpath('//span[@id="offering-price"]')
        if len(current_price_element) != 0:
            current_price = current_price_element[0].attrs["content"]
        else:
            return None

        self.last_price = current_price
        return float(current_price)
    
if __name__ == "__main__":
    start = time.time()

    scraper = Scraper()
    # https://www.hepsiburada.com/ev-elektronik-urunleri-c-2147483638
    print(scraper.get_products("https://www.hepsiburada.com/pet-shop-c-2147483616", 1))

    end = time.time()
    print(end - start)