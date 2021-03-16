import mysql.connector
import configparser
import datetime
import time
import random

config = configparser.ConfigParser()
config.read("./config.ini")

DB_HOST = config.get("DATABASE", "host")
DB_USER = config.get("DATABASE", "user")
DB_PASSWORD = config.get("DATABASE", "password")

db = mysql.connector.connect(
    host = DB_HOST,
    user = DB_USER,
    password = DB_PASSWORD,
    database = "telegram_tracker"
)
c = db.cursor()

prices = [
    [3000, 2700, 2200],
    [None, 2800, 2000],
    [3700, 3300, 3000]
]

# product_id = "<product_id>" + str(random.randint(1, 1000))
product_id = "<product_id>"
product_name = 'Lenovo V14 Ill Intel Core i5 1035G1 8GB 1TB + 256GB SSD Windows 10 Home 14" FHD Taşınabilir Bilgisayar 82C400A8TXR3'
product_url = "https://www.hepsiburada.com/lenovo-v14-ill-intel-core-i5-1035g1-8gb-1tb-256gb-ssd-windows-10-home-14-fhd-tasinabilir-bilgisayar-82c400a8txr3-p-HBV00001C8DV3?magaza=Bisistem"
url_id = 1


date = "2021-03-16 16:09:29.421038"
for price1, price2, price3 in zip(*prices):
    # date = str(datetime.datetime.now())

    if price1 is not None:
        c.execute(
            "INSERT INTO products VALUES (%s, %s, %s, %s, %s, %s, %s, %s);", (
                date + " |X| " + "Product1",
                date,
                "Product1", 
                product_id, 
                product_name, 
                price1, 
                product_url, 
                url_id
            )
        )
    
    if price2 is not None:
        c.execute(
            "INSERT INTO products VALUES (%s, %s, %s, %s, %s, %s, %s, %s);", (
                date + " |X| " + "Product2",
                date,
                "Product2", 
                product_id, 
                product_name, 
                price2, 
                product_url, 
                url_id
            )
        )

    if price3 is not None:
        c.execute(
            "INSERT INTO products VALUES (%s, %s, %s, %s, %s, %s, %s, %s);", (
                date + " |X| " + "Product3",
                date,
                "Product3", 
                product_id, 
                product_name, 
                price3, 
                product_url, 
                url_id
            )
        )
    
    date = str(datetime.datetime.strptime(date, "%Y-%m-%d %H:%M:%S.%f") + datetime.timedelta(minutes = 1))

c.close()
db.commit()
db.close()