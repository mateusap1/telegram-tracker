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
    [2279, 2279, 2279, 2279, 2279, 2279, 2279, 2279, 2279, 2279, 2279, 2279],
    [None, None, None, None, None, None, None, None, None, None, 1519, 1519],
    [None, None, None, None, None, None, None, None, None, None, None, None]
]

rd = str(random.randint(1, 100))
product_id = "<product_id>" + rd
product_name = 'Teste'
product_url = "https://www.hepsiburada.com/lenovo-v14-ill-intel-core-i5-1035g1-8gb-1tb-256gb-ssd-windows-10-home-14-fhd-tasinabilir-bilgisayar-82c400a8txr3-p-HBV00001C8DV3?magaza=Bisistem"
url_id = 1

date = str(datetime.datetime.now())
for price1, price2, price3 in zip(*prices):
    if price1 is not None:
        c.execute(
            "INSERT INTO products VALUES (%s, %s, %s, %s, %s, %s, %s, %s);", (
                date + " |X| " + "Product1",
                date,
                "Product1" + rd, 
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
                "Product2" + rd, 
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
                "Product3" + rd, 
                product_id, 
                product_name, 
                price3, 
                product_url, 
                url_id
            )
        )
    
    date = str(datetime.datetime.strptime(date, "%Y-%m-%d %H:%M:%S.%f") + datetime.timedelta(seconds = 61))

c.close()
db.commit()
db.close()