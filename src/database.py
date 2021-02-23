import sqlite3

conn = sqlite3.connect("./data/data.db")
c = conn.cursor()

c.execute("""CREATE TABLE products (
    product_id TEXT,
    last_price REAL,
    current_price REAL,
    title TEXT,
    merchant TEXT,
    variant TEXT,
    url TEXT,
    subcategory_id INTEGER,
    brand_id INTEGER
)""")

c.execute("""CREATE TABLE categories (
    name TEXT,
    url TEXT
)""")

c.execute("""CREATE TABLE subcategories (
    name TEXT,
    url TEXT,
    category_id INTEGER
)""")

c.execute("""CREATE TABLE brands (
    name TEXT,
    url TEXT
)""")

conn.commit()
conn.close()