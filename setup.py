import mysql.connector
import configparser
import sys

config = configparser.ConfigParser()
config.read("./config.ini")

DB_HOST = config.get("DATABASE", "host")
DB_USER = config.get("DATABASE", "user")
DB_PASSWORD = config.get("DATABASE", "password")

if any([i.strip() == "" for i in (DB_HOST, DB_PASSWORD, DB_USER)]):
    print("[Error] You must fill the database blank spaces")
    sys.exit(1)

mydb = mysql.connector.connect(
    host=DB_HOST,
    user=DB_USER,
    password=DB_PASSWORD
)

mycursor = mydb.cursor()

mycursor.execute("DROP DATABASE IF EXISTS telegram_tracker;")

mycursor.execute("CREATE DATABASE telegram_tracker;")

mydb = mysql.connector.connect(
    host=DB_HOST,
    user=DB_USER,
    password=DB_PASSWORD,
    database="telegram_tracker"
)

mycursor = mydb.cursor()

mycursor.execute("""CREATE TABLE products (
    rowid TEXT,
    date TEXT,
    listing_id TEXT,
    product_id TEXT,
    product_name TEXT,
    price REAL,
    url TEXT,
    url_id INTEGER
);
""")

mycursor.execute("""CREATE TABLE temp_products (
    rowid TEXT,
    date TEXT,
    listing_id TEXT,
    product_id TEXT,
    product_name TEXT,
    price REAL,
    url TEXT,
    url_id INTEGER
);
""")

mycursor.execute("""CREATE TABLE deleted (
    product_rowid TEXT
);
""")

mycursor.execute("""CREATE TABLE urls (
    rowid INTEGER,
    url TEXT,
    cycle INTEGER
);
""")

mycursor.execute("SET GLOBAL max_allowed_packet=1073741824;")
mycursor.execute(
    "SET sql_mode=(SELECT REPLACE(@@sql_mode,'ONLY_FULL_GROUP_BY',''));")

mydb.commit()
