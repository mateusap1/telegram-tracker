import mysql.connector
import configparser
import datetime
import time
import random
import os

config = configparser.ConfigParser()
config.read("./config.ini")

DB_HOST = config.get("DATABASE", "host")
DB_USER = config.get("DATABASE", "user")
DB_PASSWORD = config.get("DATABASE", "password")

if DB_PASSWORD[0] == "$":
    DB_PASSWORD = os.getenv(DB_PASSWORD[1:])

db = mysql.connector.connect(
    host = DB_HOST,
    user = DB_USER,
    password = DB_PASSWORD,
    database = "telegram_tracker"
)
c = db.cursor()

rd = str(random.randint(1, 1000))
product_id = "<product_id>" + rd
product_name = 'Teste'
product_url = "https://www.hepsiburada.com/lenovo-v14-ill-intel-core-i5-1035g1-8gb-1tb-256gb-ssd-windows-10-home-14-fhd-tasinabilir-bilgisayar-82c400a8txr3-p-HBV00001C8DV3?magaza=Bisistem"
url_id = 1

date = str(datetime.datetime.now())

c.execute("INSERT INTO urls VALUES (%s, %s, %s);", (1, "<url>", 7))

c.execute(
    "INSERT INTO temp_products VALUES (%s, %s, %s, %s, %s, %s, %s, %s);", (
        random.randint(1, 1000),
        date,
        "<listing_id1>" + rd,
        product_id,
        product_name,
        3000,
        product_url,
        url_id
    )
)

c.close()
db.commit()

time.sleep(31)
date = str(datetime.datetime.now())

db = mysql.connector.connect(
    host = DB_HOST,
    user = DB_USER,
    password = DB_PASSWORD,
    database = "telegram_tracker"
)
c = db.cursor()

c.execute(
    "INSERT INTO temp_products VALUES (%s, %s, %s, %s, %s, %s, %s, %s);", (
        random.randint(1, 1000),
        date,
        "<listing_id1>" + rd,
        product_id,
        product_name,
        3000,
        product_url,
        url_id
    )
)

c.execute(
    "INSERT INTO temp_products VALUES (%s, %s, %s, %s, %s, %s, %s, %s);", (
        random.randint(1, 1000),
        date,
        "<listing_id2>" + rd,
        product_id,
        product_name,
        2000,
        product_url,
        url_id
    )
)

c.close()
db.commit()
db.close()